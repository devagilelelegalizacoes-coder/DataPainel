import json

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from app.auth import get_current_user, get_user_by_id
from app.consulta_formatter import montar_view
from app.consulta_types import get_consulta_type, listar_consulta_types
from app.credits import (
    SaldoInsuficienteError,
    debitar_creditos,
    estornar_creditos,
    get_consulta,
    listar_consultas,
    registrar_consulta,
)
from app.pdf_report import gerar_pdf_consulta
from apibrasil.agregados_propria import AgregadosPropriaService
from apibrasil.base_nacional import BaseNacionalService
from apibrasil.base_nacional_v2 import (
    APIBrasilConfig,
    APIBrasilError,
    BaseNacionalV2Service,
)

router = APIRouter()
templates = Jinja2Templates(directory="templates")


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

    raise APIBrasilError("Tipo de consulta ainda não implementado", status_code=501)


@router.get("/consultas", response_class=HTMLResponse)
def consultas_page(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    consultas = listar_consultas(user["id"], limit=20)
    return templates.TemplateResponse(
        request,
        "consultas.html",
        {
            "user": user,
            "consultas": consultas,
            "tipos": listar_consulta_types(),
            "resultado": None,
            "erro": None,
        },
    )


@router.post("/consultas/{tipo_id}", response_class=HTMLResponse)
def consultas_submit(request: Request, tipo_id: str, placa: str = Form(...)):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    tipo = get_consulta_type(tipo_id)
    if tipo is None:
        raise HTTPException(status_code=404, detail="Tipo de consulta não encontrado")

    placa = placa.strip().upper()
    custo = tipo.custo_creditos
    resultado = None
    erro = None

    if not tipo.disponivel:
        erro = f"A consulta '{tipo.nome}' ainda não está disponível."
    else:
        try:
            debitar_creditos(user["id"], custo)
        except SaldoInsuficienteError as exc:
            erro = str(exc)

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

    return templates.TemplateResponse(
        request,
        "consultas.html",
        {
            "user": user,
            "consultas": consultas,
            "tipos": listar_consulta_types(),
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

    return templates.TemplateResponse(
        request,
        "consulta_detalhe.html",
        {
            "user": user,
            "consulta": consulta,
            "tipo": tipo,
            "campos_principais": view.campos_principais,
            "secoes": view.secoes,
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
