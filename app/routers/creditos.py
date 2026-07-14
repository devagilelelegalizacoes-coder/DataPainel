from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from app.templates import templates

from app.auth import get_current_user, get_user_by_id
from app.payments import (
    MercadoPagoConfig,
    PagamentoError,
    PagamentoService,
    confirmar_pagamento_aprovado,
    get_pagamento,
    listar_pagamentos,
    marcar_pagamento_status,
    registrar_pagamento_pendente,
)

router = APIRouter()

CREDITOS_MIN = 1
CREDITOS_MAX = 10000


@router.get("/creditos", response_class=HTMLResponse)
def creditos_page(request: Request, erro: str | None = None):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    pagamentos = listar_pagamentos(user["id"], limit=15)
    return templates.TemplateResponse(
        request,
        "creditos.html",
        {
            "user": user,
            "pagamentos": pagamentos,
            "erro": erro,
        },
    )


@router.post("/creditos/comprar")
def creditos_comprar(request: Request, quantidade: int = Form(...)):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    if quantidade < CREDITOS_MIN or quantidade > CREDITOS_MAX:
        return RedirectResponse(
            url=f"/creditos?erro=Informe+uma+quantidade+entre+{CREDITOS_MIN}+e+{CREDITOS_MAX}+créditos",
            status_code=303,
        )

    pagamento_id = registrar_pagamento_pendente(user["id"], quantidade)

    try:
        config = MercadoPagoConfig.from_env()
        service = PagamentoService(config)
        checkout_url = service.criar_preferencia(pagamento_id, quantidade, user["email"])
    except (PagamentoError, RuntimeError) as exc:
        marcar_pagamento_status(pagamento_id, "erro")
        return RedirectResponse(
            url=f"/creditos?erro=Falha+ao+iniciar+pagamento:+{exc}",
            status_code=303,
        )

    return RedirectResponse(url=checkout_url, status_code=303)


@router.get("/creditos/retorno", response_class=HTMLResponse)
def creditos_retorno(request: Request, payment_id: str | None = None, status: str | None = None, external_reference: str | None = None):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    mensagem = None
    sucesso = False

    if external_reference:
        pagamento = get_pagamento(int(external_reference))
        if pagamento and pagamento["user_id"] == user["id"]:
            if payment_id:
                try:
                    config = MercadoPagoConfig.from_env()
                    service = PagamentoService(config)
                    detalhe = service.consultar_pagamento(payment_id)
                    status_real = detalhe.get("status")
                except (PagamentoError, RuntimeError):
                    status_real = status
            else:
                status_real = status

            if status_real == "approved":
                confirmar_pagamento_aprovado(pagamento["id"], payment_id or "")
                sucesso = True
                mensagem = f"Pagamento aprovado! {pagamento['creditos']} créditos adicionados à sua conta."
            elif status_real == "pending":
                marcar_pagamento_status(pagamento["id"], "pendente", payment_id)
                mensagem = "Pagamento pendente de confirmação. Assim que aprovado, os créditos serão adicionados."
            else:
                marcar_pagamento_status(pagamento["id"], "recusado", payment_id)
                mensagem = "Pagamento não foi aprovado. Tente novamente ou use outro método."

    user = get_user_by_id(user["id"])
    return templates.TemplateResponse(
        request,
        "creditos_retorno.html",
        {"user": user, "mensagem": mensagem, "sucesso": sucesso},
    )


@router.post("/creditos/webhook")
async def creditos_webhook(request: Request):
    body = await request.json()
    data_id = body.get("data", {}).get("id")
    tipo = body.get("type")

    if tipo == "payment" and data_id:
        try:
            config = MercadoPagoConfig.from_env()
            service = PagamentoService(config)
            detalhe = service.consultar_pagamento(data_id)
        except (PagamentoError, RuntimeError):
            return {"status": "erro ao consultar pagamento"}

        external_reference = detalhe.get("external_reference")
        if external_reference and detalhe.get("status") == "approved":
            confirmar_pagamento_aprovado(int(external_reference), str(data_id))

    return {"status": "ok"}
