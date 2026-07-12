from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from app.auth import get_current_user
from app.chat import contar_nao_lidas_cliente, enviar_mensagem, listar_mensagens, marcar_lidas
from app.templates import templates

router = APIRouter()


@router.get("/chat", response_class=HTMLResponse)
def chat_page(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    mensagens = listar_mensagens(user["id"])
    marcar_lidas(user["id"], "cliente")
    return templates.TemplateResponse(
        request,
        "chat.html",
        {"user": user, "mensagens": mensagens},
    )


@router.post("/chat/enviar")
def chat_enviar(request: Request, mensagem: str = Form(...)):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    if mensagem.strip():
        enviar_mensagem(cliente_id=user["id"], autor_id=user["id"], autor_tipo="cliente", mensagem=mensagem.strip())
    return RedirectResponse(url="/chat", status_code=303)


@router.get("/chat/api/status")
def chat_status(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    mensagens = listar_mensagens(user["id"])
    return JSONResponse({"total": len(mensagens), "nao_lidas": contar_nao_lidas_cliente(user["id"])})
