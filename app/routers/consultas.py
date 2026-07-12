import gzip
import json
from app.templates import templates

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from app.auth import get_current_user, get_user_by_id
from app.consulta_formatter import montar_view
from app.consulta_types import MAX_DOCUMENTOS_EXIGIDOS, get_consulta_type, listar_consulta_types
from app.credits import (
    SaldoInsuficienteError,
    debitar_creditos,
    estornar_creditos,
    get_anexo,
    get_consulta,
    get_documento_consulta,
    listar_consultas,
    listar_documentos_consulta,
    registrar_consulta,
    salvar_documento_consulta,
)
from app.pdf_report import gerar_pdf_consulta
from app.pricing import resolver_custo, resolver_custos
from apibrasil.agregados_propria import AgregadosPropriaService
from apibrasil.analitico_veicular import AnaliticoVeicularService
from apibrasil.base_estadual import BaseEstadualService
from apibrasil.base_nacional import BaseNacionalService
from apibrasil.base_nacional_v2 import (
    APIBrasilConfig,
    APIBrasilError,
    BaseNacionalV2Service,
)
from apibrasil.debitos_v4 import DebitosV4Service
from apibrasil.gravame import GravameService
from apibrasil.leilao import LeilaoService
from apibrasil.veicular_agrupados import VeicularAgrupadosService
from apibrasil.veicular_relatorio import VeicularRelatorioService

router = APIRouter()


def _resumo_veiculo(resultado: dict) -> str:
    view = montar_view(resultado)
    if not view.campos_principais:
        return "Consulta concluída"
    return " · ".join(valor for _, valor in view.campos_principais[:3])


def _executar_consulta(tipo_id: str, valor: str) -> dict:
    config = APIBrasilConfig.from_env()

    if tipo_id == "base-nacional-v2":
        service = BaseNacionalV2Service(config)
        return service.consultar_placa(placa=valor, homolog=False)

    if tipo_id == "agregados-propria":
        service = AgregadosPropriaService(config)
        return service.consultar_placa(placa=valor, homolog=False)

    if tipo_id == "nacional":
        service = BaseNacionalService(config)
        return service.consultar_placa(placa=valor, homolog=False)

    if tipo_id == "estadual":
        service = BaseEstadualService(config)
        return service.consultar_placa(placa=valor, homolog=False)

    if tipo_id == "gravame":
        service = GravameService(config)
        return service.consultar_placa(placa=valor, homolog=False)

    if tipo_id == "analitico-veicular":
        service = AnaliticoVeicularService(config)
        return service.consultar_placa(placa=valor, homolog=False)

    if tipo_id == "veicular-agrupados":
        service = VeicularAgrupadosService(config)
        return service.consultar_placa(placa=valor, homolog=False)

    if tipo_id == "relatorio-veicular":
        service = VeicularRelatorioService(config)
        return service.consultar_placa(placa=valor, homolog=False)

    if tipo_id == "leilao":
        service = LeilaoService(config)
        return service.consultar_placa(placa=valor, homolog=False)

    if tipo_id == "debitos-v4":
        service = DebitosV4Service(config)
        return service.consultar_placa(placa=valor, homolog=False)

    raise APIBrasilError("Tipo de consulta ainda não implementado", status_code=501)


@router.get("/consultas", response_class=HTMLResponse)
def consultas_page(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    consultas = listar_consultas(user["id"], limit=20)
    tipos = listar_consulta_types()
    return templates.TemplateResponse(
        request,
        "consultas.html",
        {
            "user": user,
            "consultas": consultas,
            "tipos": tipos,
            "precos": resolver_custos(user, tipos),
            "resultado": None,
            "erro": None,
        },
    )


TAMANHO_MAX_DOCUMENTO = 8 * 1024 * 1024  # 8MB antes de comprimir


async def _salvar_documentos_consulta(consulta_id: int, tipo, arquivos: list) -> None:
    for nome_documento, arquivo in zip(tipo.lista_documentos_exigidos, arquivos):
        if arquivo is None or not arquivo.filename:
            continue
        conteudo = await arquivo.read()
        if not conteudo or len(conteudo) > TAMANHO_MAX_DOCUMENTO:
            continue
        salvar_documento_consulta(
            consulta_id=consulta_id,
            nome_documento=nome_documento,
            arquivo_nome=arquivo.filename,
            arquivo_tipo=arquivo.content_type,
            arquivo_blob=gzip.compress(conteudo, compresslevel=6),
            tamanho_original=len(conteudo),
        )


@router.post("/consultas/{tipo_id}", response_class=HTMLResponse)
async def consultas_submit(
    request: Request,
    tipo_id: str,
    placa: str = Form(...),
    documento_1: UploadFile | None = File(None),
    documento_2: UploadFile | None = File(None),
    documento_3: UploadFile | None = File(None),
    documento_4: UploadFile | None = File(None),
    documento_5: UploadFile | None = File(None),
):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    tipo = get_consulta_type(tipo_id)
    if tipo is None:
        raise HTTPException(status_code=404, detail="Tipo de consulta não encontrado")

    arquivos = [documento_1, documento_2, documento_3, documento_4, documento_5][:MAX_DOCUMENTOS_EXIGIDOS]
    placa = placa.strip().upper()
    custo = resolver_custo(user, tipo)
    resultado = None
    erro = None

    if not tipo.disponivel:
        erro = f"A consulta '{tipo.nome}' ainda não está disponível."
    elif any(
        arq is None or not arq.filename
        for _, arq in zip(tipo.lista_documentos_exigidos, arquivos)
    ):
        erro = "Envie todos os documentos exigidos para esta consulta."
    else:
        try:
            debitar_creditos(user["id"], custo)
        except SaldoInsuficienteError as exc:
            erro = str(exc)

        if erro is None and tipo.manual:
            consulta_id = registrar_consulta(
                user_id=user["id"],
                tipo=tipo.id,
                placa=placa,
                custo_creditos=custo,
                status="pendente",
                resultado_resumo="Aguardando atendimento de um operador",
            )
            await _salvar_documentos_consulta(consulta_id, tipo, arquivos)
            return RedirectResponse(url=f"/consultas/historico/{consulta_id}", status_code=303)

        if erro is None:
            try:
                resultado = _executar_consulta(tipo.id, placa)
                consulta_id = registrar_consulta(
                    user_id=user["id"],
                    tipo=tipo.id,
                    placa=placa,
                    custo_creditos=custo,
                    status="sucesso",
                    resultado_resumo=_resumo_veiculo(resultado),
                    resultado_json=json.dumps(resultado, ensure_ascii=False),
                )
                await _salvar_documentos_consulta(consulta_id, tipo, arquivos)
                return RedirectResponse(url=f"/consultas/historico/{consulta_id}", status_code=303)
            except APIBrasilError as exc:
                estornar_creditos(user["id"], custo)
                registrar_consulta(
                    user_id=user["id"],
                    tipo=tipo.id,
                    placa=placa,
                    custo_creditos=0,
                    status="erro",
                    erro_mensagem=exc.message,
                )
                erro = f"Erro na consulta: {exc.message} (créditos estornados)"

    user = get_user_by_id(user["id"])
    consultas = listar_consultas(user["id"], limit=20)
    tipos = listar_consulta_types()

    return templates.TemplateResponse(
        request,
        "consultas.html",
        {
            "user": user,
            "consultas": consultas,
            "tipos": tipos,
            "precos": resolver_custos(user, tipos),
            "tipo_ativo": tipo,
            "erro": erro,
        },
    )


@router.get("/consultas/historico/{consulta_id}", response_class=HTMLResponse)
def consulta_detalhe(request: Request, consulta_id: int):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    consulta = get_consulta(consulta_id, user["id"])
    if consulta is None:
        raise HTTPException(status_code=404, detail="Consulta não encontrada")

    resultado = json.loads(consulta["resultado_json"]) if consulta["resultado_json"] else None
    view = montar_view(resultado)
    tipo = get_consulta_type(consulta["tipo"])
    documentos = listar_documentos_consulta(consulta_id)

    return templates.TemplateResponse(
        request,
        "consulta_detalhe.html",
        {
            "user": user,
            "consulta": consulta,
            "tipo": tipo,
            "campos_principais": view.campos_principais,
            "secoes": view.secoes,
            "documentos": documentos,
        },
    )


@router.get("/consultas/historico/{consulta_id}/pdf")
def consulta_pdf(request: Request, consulta_id: int):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    consulta = get_consulta(consulta_id, user["id"])
    if consulta is None:
        raise HTTPException(status_code=404, detail="Consulta não encontrada")
    if not consulta["resultado_json"]:
        raise HTTPException(status_code=400, detail="Esta consulta não possui dados para gerar PDF")

    resultado = json.loads(consulta["resultado_json"])
    pdf_bytes = gerar_pdf_consulta(consulta, resultado)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="consulta-{consulta["placa"]}-{consulta["id"]}.pdf"'
        },
    )


@router.get("/consultas/historico/{consulta_id}/anexo")
def consulta_anexo(request: Request, consulta_id: int):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    consulta = get_consulta(consulta_id, user["id"])
    if consulta is None:
        raise HTTPException(status_code=404, detail="Consulta não encontrada")

    anexo = get_anexo(consulta_id)
    if anexo is None:
        raise HTTPException(status_code=404, detail="Esta consulta não possui anexo")

    conteudo = gzip.decompress(anexo["anexo_blob"])
    return Response(
        content=conteudo,
        media_type=anexo["anexo_tipo"] or "application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{anexo["anexo_nome"]}"'},
    )


@router.get("/consultas/historico/{consulta_id}/documentos/{doc_id}")
def consulta_documento_download(request: Request, consulta_id: int, doc_id: int):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    consulta = get_consulta(consulta_id, user["id"])
    if consulta is None:
        raise HTTPException(status_code=404, detail="Consulta não encontrada")

    documento = get_documento_consulta(doc_id)
    if documento is None or documento["consulta_id"] != consulta_id:
        raise HTTPException(status_code=404, detail="Documento não encontrado")

    conteudo = gzip.decompress(documento["arquivo_blob"])
    return Response(
        content=conteudo,
        media_type=documento["arquivo_tipo"] or "application/octet-stream",
        headers={"Content-Disposition": f'inline; filename="{documento["arquivo_nome"]}"'},
    )
