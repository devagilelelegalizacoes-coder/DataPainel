---
name: continuar-projeto
description: Use ao adicionar/alterar funcionalidades neste projeto APIBrasil (FastAPI + SQLite) — novo tipo de consulta, telas, créditos, PDF, etc. Garante que a arquitetura e os padrões já estabelecidos sejam mantidos, sem reinventar ou quebrar o que já funciona. Acionar sempre que o pedido envolver "consulta", "crédito", "dashboard", "login", "PDF" ou qualquer arquivo em app/ ou apibrasil/ deste projeto.
---

# Continuar o projeto APIBrasil sem alterar a base

Este é um sistema web (FastAPI + Jinja2 + SQLite) que consome a API da APIBrasil para consultas
veiculares, com login, sistema de créditos internos e histórico com página de detalhe + PDF.
A arquitetura já está definida e testada — **siga os padrões abaixo em vez de criar uma abordagem nova**.

## Stack e estrutura (não mudar)

- **Framework**: FastAPI (async), templates Jinja2 server-side (sem SPA/JS framework), sessão via
  `SessionMiddleware` (cookie assinado, `SESSION_SECRET_KEY` no `.env`).
- **Banco**: SQLite puro (`sqlite3` da stdlib, sem ORM) em `data/app.db`. Migrações são feitas com
  `_ensure_column()` em [app/database.py](../../../app/database.py) — idempotente, roda no `startup`.
- **Ambiente**: `venv/` local. Ative com `./venv/Scripts/python.exe` (Windows). Rode o servidor com:
  ```
  ./venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
  ```
  Sempre em `run_in_background: true` — processos em foreground morrem ao fim da tool call.
- **Segredos**: tokens e chaves só em `.env` (nunca hardcode). `.env` está no `.gitignore`.

## Onde cada coisa vive

| Camada | Arquivo |
|---|---|
| Integração HTTP com a APIBrasil (por endpoint) | `apibrasil/<nome>.py` |
| Config/erros compartilhados da API | `apibrasil/base_nacional_v2.py` (`APIBrasilConfig`, `APIBrasilError`, `APIBrasilTimeoutError`) — reaproveitar, não duplicar |
| Registro dos tipos de consulta (**SQLite**, não dict fixo) | `app/consulta_types.py` (tabela `tipos_consulta`: nome, descrição, ícone, custo, `disponivel`, `campos_incluidos`) |
| Dispatcher que decide qual service chamar | `_executar_consulta()` em `app/routers/consultas.py` |
| Créditos (débito/estorno/histórico) | `app/credits.py` |
| Auth (bcrypt direto, **não passlib** — tem bug de compat com bcrypt 5.x) | `app/auth.py` |
| Formatação genérica de resultado (detalhe + PDF) | `app/consulta_formatter.py` |
| Geração de PDF | `app/pdf_report.py` |
| Schema SQLite + seeds/migrações de `tipos_consulta` | `app/database.py` |
| Templates | `templates/*.html`, estende `base.html` |
| CSS único, tema claro/moderno, responsivo | `static/style.css` (variáveis em `:root`; paleta azul/verde/branco/cinza — `--primary` azul, `--secondary` verde, `--bg`/`--surface`/`--border` cinza/branco; breakpoints `@media (max-width: 900px)` tablet e `(max-width: 560px)` celular no final do arquivo — **todo componente novo precisa caber nesses dois breakpoints**, não só desktop) |
| Painel admin de consultas (ativar/desativar/editar/criar/excluir cards) | `app/routers/admin.py`, `templates/admin_consultas.html` — restrito a `user.is_admin` |
| Painel admin de usuários (promover operador/admin) + relatório de operadores | `app/routers/admin.py` (`/admin/usuarios`, `/admin/operadores`), `app/auth.py` (`listar_usuarios`, `alternar_operador`, `alternar_admin`) |
| Fila de atendimento manual (consultas sem API) | `app/routers/operador.py`, `templates/operador.html`/`operador_atender.html` — restrito a `user.is_operador` ou `is_admin` |
| Chat interno cliente ↔ operador | `app/chat.py`, `app/routers/chat.py` (`/chat`, cliente), `app/routers/operador.py` (`/operador/chat`, inbox e conversa) |
| Pré-cadastro e aprovação de clientes | `app/auth.py` (`criar_pre_cadastro`, `aprovar_cadastro`, `rejeitar_cadastro`), `app/routers/auth.py` (`/registro`), `app/routers/operador.py` (`/operador/cadastros`) |
| Personalização (nome do sistema, logo login, favicon) | `app/config_sistema.py`, `app/routers/admin.py` (`/admin/config`), `templates/admin_config.html` |
| Templates Jinja2 compartilhados (registra `get_config()` como global) | `app/templates.py` — **todo router importa `templates` daqui, nunca instancia `Jinja2Templates` de novo** |
| Páginas legais estáticas | `templates/termos.html`, `templates/privacidade.html`, rotas em `app/routers/auth.py` |
| Preços diferenciados por segmento/cliente | `app/pricing.py` (`resolver_custo`), `app/routers/admin.py` (`/admin/precos`), `templates/admin_precos.html` |
| Pacotes de crédito (venda) | `app/credit_packages.py` (dict fixo em código, não em DB) |
| Pagamento (Mercado Pago Checkout Pro) | `app/payments.py`, `app/routers/creditos.py`, tabela `pagamentos` |

## Padrão obrigatório: adicionar um novo tipo de consulta

Este é o fluxo **padrão do projeto** — qualquer nova consulta da APIBrasil deve seguir exatamente isto,
sem criar template ou lógica de exibição nova:

1. Criar `apibrasil/<nome_do_endpoint>.py` com uma classe `<Nome>Service`, reaproveitando
   `APIBrasilConfig`/`APIBrasilError`/`APIBrasilTimeoutError` de `apibrasil/base_nacional_v2.py`
   (não recriar essas classes). Seguir a mesma estrutura de `AgregadosPropriaService` como referência.
   Se o payload tiver campos aninhados (`extra`, `whitelabel`, `agrupados`...), tipar com
   `TypedDict(..., total=False)` na forma funcional quando as chaves do JSON tiverem hífen
   (`"proprietario-atual"` não é identificador Python válido).
2. **Testar primeiro em homolog** (`homolog=True`) antes de assumir o formato da resposta — o shape
   varia bastante entre endpoints (ver "Pegadinhas de resposta" abaixo) e só dá pra saber rodando de
   verdade.
3. Registrar o card em `app/database.py`: adicionar a entrada em `SEED_TIPOS_CONSULTA` (novas
   instalações) **e** uma chamada `_ensure_seed_row(conn, "<tipo_id>")` em `init_db()` (bancos já
   existentes) — sem isso o card não aparece pra quem já rodou o projeto antes. Preencher também
   `CAMPOS_INCLUIDOS["<tipo_id>"]` com um resumo em texto (uma linha por item, `\n` separado) do que a
   resposta real traz — isso vira a checklist visível no card em `/consultas`, então **precisa ser
   escrito depois do teste em homolog**, não antes (não adivinhar campos).
4. Adicionar um `if tipo_id == "...":` em `_executar_consulta()` (`app/routers/consultas.py`)
   chamando o novo service.
5. **Não criar template de detalhe nem lógica de PDF nova.** A página de detalhe
   (`templates/consulta_detalhe.html`) e o PDF (`app/pdf_report.py`) são genéricos — funcionam para
   qualquer JSON de resposta via `montar_view()` em `app/consulta_formatter.py` (recursivo, qualquer
   profundidade de aninhamento). Isso é padrão do projeto, confirmado explicitamente pelo usuário:
   **"todas as consultas precisa de uma página para mostrar a consulta, isso é padrão para o
   projeto"**.

### Pegadinhas de resposta já encontradas (conferir em todo endpoint novo)

- **Chave dos dados nem sempre é `"data"`.** O endpoint `veicular-agrupados` devolve os resultados
  numa chave literal com o nome do `tipo` (`body["veicular-agrupados"]`), não em `"data"`. Sem
  normalizar isso dentro do próprio service (`_handle_response` promovendo a chave certa para
  `"data"`), o formatador genérico cai no fallback e **vaza campos internos da resposta** (saldo,
  e-mail da conta) na tela e no PDF do cliente. Sempre conferir `list(resultado.keys())` no teste em
  homolog antes de dar como pronto.
- **`whitelabel` às vezes é obrigatório mesmo "opcional" na doc.** `analitico-veicular` e
  `relatorio-veicular` retornam `400 "whitelabel deve ser objeto"` se o campo vier ausente ou `{}`.
  Sempre mandar um `DEFAULT_WHITELABEL` preenchido (empresa, cores, etc.) quando o caller não
  especificar um customizado — ver `apibrasil/analitico_veicular.py` como referência.
- Vários endpoints (`analitico-veicular`, `relatorio-veicular`) retornam `content` (JSON aninhado) +
  `pdf` (link do relatório hospedado pela própria APIBrasil) em vez de campos estruturados soltos —
  isso é normal e o formatador genérico já lida bem.

## Consultas manuais (sem API — atendidas por operador humano)

Nem toda consulta tem endpoint na APIBrasil (ex: "Score Veicular"). Para essas, o card em
`tipos_consulta` tem `manual=1` — nesse caso `consultas_submit()` **não chama nenhum service**, só
debita os créditos e grava a consulta com `status="pendente"`. O cliente vê "aguardando um operador"
na mesma `consulta_detalhe.html` de sempre (branch por status, não template novo).

- Fila em `/operador`: lista pedidos `status='pendente' AND operador_id IS NULL`. "Puxar" é um
  `UPDATE ... WHERE status='pendente' AND operador_id IS NULL` com checagem de `rowcount == 1`
  (`reivindicar_consulta()` em `app/credits.py`) — é assim que se evita dois operadores pegando o
  mesmo pedido; não trocar por um `SELECT` seguido de `UPDATE` separado (condição de corrida).
- Aviso sonoro é só Web Audio API (`OscillatorNode` gerado em JS, sem arquivo de áudio) + polling a
  cada 6s em `/operador/api/pendentes-ids` comparando IDs conhecidos — não precisa de
  websocket/SSE pra esse volume.
- Conclusão aceita observação em texto e/ou upload de arquivo. **Arquivo é comprimido com
  `gzip.compress()` antes de virar BLOB no SQLite** (colunas `anexo_blob`/`anexo_nome`/`anexo_tipo`/
  `anexo_tamanho_original` em `consultas`) e descomprimido só na hora do download
  (`/consultas/historico/{id}/anexo`) — manter essa compressão em qualquer novo tipo de anexo, é o
  que evita o banco inchar.
- Resultado do atendimento manual vira `resultado_json = {"data": {...}}` como qualquer outro tipo
  (`observacao_operador`, `documento_anexado`), então cai automaticamente no formatador/PDF genérico
  sem código extra.
- Se o operador não conseguir atender, `marcar_consulta_manual_erro()` **estorna os créditos do
  cliente automaticamente** (mesma regra do fluxo automático) — nunca deixar o cliente pagar por um
  pedido não atendido.
- Promover usuário a operador é em `/admin/usuarios` (`is_operador`, coluna separada de `is_admin`
  — um admin já acessa `/operador` por bypass, mas só aparece no relatório de
  `/admin/operadores` quem tem `is_operador=1` de verdade).

## Documentos exigidos do cliente por tipo de consulta

Além dos `campos_incluidos` (o que a consulta *traz*), o admin pode configurar
`tipos_consulta.documentos_exigidos` (texto separado por vírgula, ex: `"RG, CPF, Comprovante de
residência"`) — o que o cliente *precisa enviar* antes de confirmar a consulta. Limite de
**5 documentos** (`MAX_DOCUMENTOS_EXIGIDOS` em `app/consulta_types.py`); `_limitar_documentos_exigidos()`
corta silenciosamente qualquer item além do 5º ao salvar — não remover esse corte.

- No modal de `/consultas` (`templates/consultas.html`), `abrirModal()` recebe
  `tipo.lista_documentos_exigidos` (lista Jinja serializada com `|tojson`) e gera dinamicamente um
  `<input type="file" name="documento_1">` … `documento_5` — um por documento exigido, na mesma
  ordem da lista. **A ordem importa**: o back-end faz `zip(tipo.lista_documentos_exigidos,
  [documento_1..5])` para casar nome do documento com arquivo enviado.
- `consultas_submit()` em `app/routers/consultas.py` é `async` só por causa disso (precisa `await
  arquivo.read()`). Valida que todos os documentos exigidos foram enviados **antes** de debitar
  créditos — se faltar algum, nem debita nem chama a API. Isso vale tanto para consultas manuais
  quanto automáticas (o requisito de documento não depende de `tipo.manual`).
- Arquivos vão para a tabela `consulta_documentos` (não nas colunas `anexo_*` de `consultas`, que são
  do *resultado* do operador) — comprimidos com gzip igual a todo outro anexo do projeto.
  `listar_documentos_consulta()`/`salvar_documento_consulta()`/`get_documento_consulta()` em
  `app/credits.py`.
- Cliente baixa em `/consultas/historico/{id}/documentos/{doc_id}` (dono da consulta), operador baixa
  em `/operador/{id}/documentos/{doc_id}` (só o operador dono do atendimento) — para imprimir antes
  de executar o serviço. Mesma exibição em `consulta_detalhe.html` e `operador_atender.html`
  (`documentos-lista`).

## Pré-cadastro e aprovação de clientes (agências/despachantes)

Serviço é fechado: só agências de veículos e despachantes usam. `/registro` **não cria conta ativa**
— cria um usuário com `status='pendente'`, 0 créditos, exige `tipo_profissional`
(despachante/agência), `cnpj_ou_carteirinha` e upload de um documento comprobatório (gzip-compresso
igual ao anexo de consulta manual, mesma lógica de `TAMANHO_MAX_*` + decompressão sob demanda). O
usuário só consegue logar depois que um operador ou admin aprova (`aprovar_cadastro()` credita 10
créditos iniciais e muda status para `'aprovado'`) em `/operador/cadastros`. `login_submit()` checa
`user["status"]` e bloqueia com mensagem específica se `pendente` ou `rejeitado` (`motivo_rejeicao`
é exibido). **Exceção**: o primeiro usuário do sistema (bootstrap) sempre nasce `is_admin=1` e
`status='aprovado'`, senão ninguém consegue logar para aprovar os demais — não remover esse caso
especial em `criar_pre_cadastro()`/`create_user()`.

Aceite de termos é obrigatório no cadastro (`aceite_termos` checkbox, salvo como timestamp em
`aceite_termos_em`) — página não deixa passar sem marcar. `/termos` e `/privacidade` são páginas
estáticas públicas (sem exigir login), linkadas no rodapé de `base.html` e no formulário de
registro.

**Cuidado com ordem de rotas**: `/operador/cadastros` e as sub-rotas precisam estar declaradas
**antes** de `/operador/{consulta_id}` em `app/routers/operador.py`, senão o FastAPI casa
`"cadastros"` como `consulta_id` e quebra com 422 — já aconteceu uma vez, não mover as rotas
estáticas para depois das rotas com path param.

## Personalização (nome do sistema, logo, favicon)

Nome do sistema, logo da tela de login e favicon ficam em `configuracoes_sistema` (linha única,
`id=1`), editáveis pelo admin em `/admin/config`. Imagens são gzip-comprimidas antes de virar BLOB
(mesmo padrão dos anexos) e servidas via `/config/logo-login` e `/config/favicon` (rotas **públicas**,
sem autenticação — precisam carregar antes do login).

Todo template usa `{{ get_config().nome_sistema }}` no `<title>` e na navbar, e
`{% if get_config().tem_favicon %}` para o `<link rel="icon">`. Isso só funciona porque
`app/templates.py` registra `get_config` como global do Jinja (`templates.env.globals["get_config"]
= get_configuracoes`) — **todo router deve importar `templates` de `app.templates`, nunca criar sua
própria instância `Jinja2Templates(directory="templates")`**, senão o global não existe e o template
quebra com `UndefinedError`.

## Chat interno (cliente ↔ operadores)

Um canal de suporte **por cliente**, não por consulta — é uma conversa contínua entre aquele
cliente e "a equipe" (qualquer operador pode ler/responder, não é 1:1 fixo com um operador
específico). Tabela `mensagens_chat` (`cliente_id`, `autor_id`, `autor_tipo` 'cliente'/'operador',
`lida_pelo_cliente`, `lida_pelo_operador`).

- Cliente: `/chat` (ver + enviar, `app/routers/chat.py`). Ao abrir a página, `marcar_lidas(user_id,
  "cliente")` já zera o contador — não precisa de botão "marcar como lida".
- Operador: `/operador/chat` lista uma conversa por cliente que já trocou mensagem
  (`listar_conversas()`, com contagem de não lidas e ordenada pela mais recente), `/operador/chat/{
  cliente_id}` abre a conversa e marca como lida pelo operador. **Qualquer** operador/admin pode
  responder qualquer cliente — não existe atribuição fixa tipo `operador_id` como nas consultas
  manuais, é por design (é suporte geral, não uma fila com "puxar").
- Atualização é só polling (6s, mesmo padrão do resto do projeto — não usar websocket/SSE):
  `/chat/api/status` e `/operador/chat/api/nao-lidas` / `/operador/chat/{cliente_id}/api/status`
  retornam contagens; JS recarrega a página se o total mudou. Operador ganha o mesmo bipe
  (`OscillatorNode`) da fila de consultas manuais quando chega mensagem nova não lida.
- Badge de não lidas na navbar (`base.html`) vem de `get_chat_nao_lidas(user)`, registrado como
  global do Jinja em `app/templates.py` — mesma técnica do `get_config()`. Calcula diferente por
  papel: cliente vê não lidas só dele, operador/admin vê `contar_conversas_nao_lidas()` (conversas
  com pelo menos 1 mensagem de cliente não lida), não soma de mensagens.
- **Cuidado com ordem de rotas** (mesma pegadinha das consultas manuais): `/operador/chat`,
  `/operador/chat/api/nao-lidas` e `/operador/chat/{cliente_id}/api/status` estão todas registradas
  **antes** de `/operador/{consulta_id}` em `operador.py` — segmentos com contagem diferente não
  colidem entre si, mas todas precisam continuar antes da rota genérica de path param único.

## Cards visíveis por segmento (despachante x agência)

Além do preço, o admin pode restringir **quais cards aparecem** para cada segmento profissional em
`tipos_consulta.segmentos_visiveis` (texto separado por vírgula: `"despachante"`, `"agencia"` ou
ambos). **Vazio = visível para todos** (comportamento padrão, não quebra cards já existentes).
`ConsultaType.visivel_para(tipo_profissional)` faz a checagem — usar sempre esse método, não
comparar `segmentos_visiveis` na mão.

- `/consultas` (GET e o re-render de erro no POST) filtra `listar_consulta_types()` com
  `t.visivel_para(user["tipo_profissional"])` **antes** de passar `tipos` pro template — o card nem
  aparece pra quem não pode ver.
- `consultas_submit()` faz a mesma checagem no servidor e responde `403` se o segmento não bate —
  **necessário mesmo com o filtro na listagem**, porque o cliente pode montar o POST direto pra
  `/consultas/{tipo_id}` sem passar pela tela (o formulário escondido não é proteção suficiente).
- Formulário de admin usa checkboxes `name="segmentos"` (lista, `Form(list[str])`) — junta com
  `",".join(segmentos)` antes de salvar. Editar um card e desmarcar os dois libera de novo pra todos.

## Preços diferenciados por segmento e por cliente

`tipo.custo_creditos` é só o preço **padrão** do card. O preço real cobrado de um usuário vem de
`resolver_custo(user, tipo)` em `app/pricing.py`, com prioridade:
**contrato individual do cliente (`precos_clientes`) > preço do segmento (`precos_segmento`,
por `tipo_profissional`) > `tipo.custo_creditos` padrão**. `consultas_submit()` já usa
`resolver_custo()` para o débito real — **nunca voltar a usar `tipo.custo_creditos` direto no
débito**, senão contratos especiais deixam de valer. A tela de `/consultas` também precisa exibir
o preço resolvido (`resolver_custos(user, tipos)`, passado como dict `precos` para o template) para
o cliente ver o valor que ele realmente paga, não o padrão do card.

Gerenciado em `/admin/precos` (dois formulários independentes: segmento e cliente, cada um com
tabela de overrides existentes + botão remover). `definir_preco_segmento()`/`definir_preco_cliente()`
usam `INSERT ... ON CONFLICT ... DO UPDATE` (upsert) nas chaves primárias compostas
`(tipo_profissional, tipo_consulta_id)` / `(user_id, tipo_consulta_id)` — reaproveitar esse padrão
para qualquer tabela de override futura em vez de fazer SELECT-then-INSERT/UPDATE separado.

## Sistema de créditos (não mudar o fluxo)

- Custo é definido por tipo em `ConsultaType.custo_creditos` (não existe mais constante global fixa) —
  mas o valor efetivamente cobrado de um usuário específico passa por `resolver_custo()` (ver acima).
- Fluxo em `consultas_submit`: debita créditos **antes** de chamar a API → se a API falhar
  (`APIBrasilError`), estorna automaticamente e grava a consulta como `status="erro"` com
  `custo_creditos=0`. Se `debitar_creditos` já falhar por saldo insuficiente, não chama a API e não
  grava nada. Manter esse comportamento em qualquer novo tipo.
- Todo `registrar_consulta()` de sucesso deve salvar `resultado_json` (JSON completo) — é o que
  alimenta a página de detalhe e o PDF depois.

## Coisas já resolvidas — não reintroduzir o bug

- `passlib` com `bcrypt` 5.x quebra (`ValueError: password cannot be longer than 72 bytes` por bug de
  detecção de versão). Usar `bcrypt` diretamente (já está assim em `app/auth.py`).
- `Jinja2Templates.TemplateResponse()` nesta versão do Starlette exige `request` como **primeiro
  argumento posicional**: `templates.TemplateResponse(request, "nome.html", {...})`. A forma antiga
  (`{"request": request, ...}` como dict único) quebra com `TypeError: unhashable type: 'dict'`.
- Servidor uvicorn iniciado com `&` numa Bash tool call morre quando a tool call termina — sempre usar
  `run_in_background: true` no Bash tool, não `&` manual.

## Testando sem gastar créditos reais da APIBrasil

A conta tem saldo real limitado — já foi zerada mais de uma vez testando a mesma placa repetidamente.
Para validar UI/PDF sem chamar a API de verdade, inserir um resultado de exemplo direto no SQLite
(`resultado_json` com um payload plausível) em vez de repetir consultas reais. Só chamar a API de
verdade quando o teste exigir validar a integração em si. **Para testar fluxos que não são sobre a
API em si** (créditos, preços, permissões, upload de documento) — usar sempre um tipo `manual=1`
(ex: `score-veicular`) no teste ponta a ponta, nunca um tipo automático (`base-nacional-v2`, etc.):
já aconteceu de um teste de preços acabar chamando a API de verdade sem querer e gastando 1 crédito
real, só porque o tipo escolhido para o teste tinha `manual=0`.
