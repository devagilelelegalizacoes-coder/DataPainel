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
| CSS único, tema claro/moderno | `static/style.css` (variáveis em `:root`) |
| Painel admin (ativar/desativar/editar/criar/excluir cards) | `app/routers/admin.py`, `templates/admin_consultas.html` — restrito a `user.is_admin` |
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

## Sistema de créditos (não mudar o fluxo)

- Custo é definido por tipo em `ConsultaType.custo_creditos` (não existe mais constante global fixa).
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
verdade quando o teste exigir validar a integração em si.
