from datetime import datetime, timezone

import gzip
from app.templates import templates

from fastapi import APIRouter, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse

from app.auth import (
    criar_pre_cadastro,
    get_current_user,
    get_user_by_email,
    login_user,
    logout_user,
    verify_password,
)
from app.config_sistema import get_favicon, get_logo_login

router = APIRouter()

TAMANHO_MAX_DOCUMENTO = 8 * 1024 * 1024  # 8MB antes de comprimir

MENSAGENS_STATUS = {
    "pendente": "Seu cadastro ainda está em análise. Você será avisado assim que for aprovado.",
    "rejeitado": "Seu cadastro não foi aprovado.",
}


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html", {"error": None})


@router.post("/login", response_class=HTMLResponse)
def login_submit(request: Request, email: str = Form(...), password: str = Form(...)):
    user = get_user_by_email(email)
    if not user or not verify_password(password, user["password_hash"]):
        return templates.TemplateResponse(
            request,
            "login.html",
            {"error": "E-mail ou senha inválidos"},
            status_code=401,
        )
    if user["status"] != "aprovado":
        mensagem = MENSAGENS_STATUS.get(user["status"], "Seu cadastro não está liberado.")
        if user["status"] == "rejeitado" and user["motivo_rejeicao"]:
            mensagem += f" Motivo: {user['motivo_rejeicao']}"
        return templates.TemplateResponse(
            request,
            "login.html",
            {"error": mensagem},
            status_code=403,
        )
    login_user(request, user["id"])
    return RedirectResponse(url="/dashboard", status_code=303)


@router.get("/registro", response_class=HTMLResponse)
def registro_page(request: Request):
    return templates.TemplateResponse(request, "registro.html", {"error": None})


@router.post("/registro", response_class=HTMLResponse)
async def registro_submit(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    tipo_profissional: str = Form(...),
    cnpj_ou_carteirinha: str = Form(...),
    documento: UploadFile = File(...),
    aceite_termos: bool = Form(False),
):
    if not aceite_termos:
        return templates.TemplateResponse(
            request,
            "registro.html",
            {"error": "É preciso aceitar os Termos de Responsabilidade e a Política de Privacidade."},
            status_code=400,
        )
    if get_user_by_email(email):
        return templates.TemplateResponse(
            request,
            "registro.html",
            {"error": "Este e-mail já está cadastrado"},
            status_code=400,
        )

    conteudo = await documento.read()
    if not conteudo:
        return templates.TemplateResponse(
            request,
            "registro.html",
            {"error": "Envie o documento comprobatório (carteirinha ou CNPJ)."},
            status_code=400,
        )
    if len(conteudo) > TAMANHO_MAX_DOCUMENTO:
        return templates.TemplateResponse(
            request,
            "registro.html",
            {"error": "Documento muito grande (máximo 8MB)."},
            status_code=400,
        )

    criar_pre_cadastro(
        name=name,
        email=email,
        password=password,
        tipo_profissional=tipo_profissional,
        cnpj_ou_carteirinha=cnpj_ou_carteirinha,
        documento_blob=gzip.compress(conteudo, compresslevel=6),
        documento_nome=documento.filename,
        documento_tipo=documento.content_type,
        aceite_termos_em=datetime.now(timezone.utc).isoformat(),
    )
    return templates.TemplateResponse(request, "registro_enviado.html", {})


@router.get("/termos", response_class=HTMLResponse)
def termos_page(request: Request):
    return templates.TemplateResponse(
        request,
        "termos.html",
        {"user": get_current_user(request), "hoje": datetime.now().strftime("%d/%m/%Y")},
    )


@router.get("/privacidade", response_class=HTMLResponse)
def privacidade_page(request: Request):
    return templates.TemplateResponse(
        request,
        "privacidade.html",
        {"user": get_current_user(request), "hoje": datetime.now().strftime("%d/%m/%Y")},
    )


@router.get("/logout")
def logout(request: Request):
    logout_user(request)
    return RedirectResponse(url="/login", status_code=303)


@router.get("/config/logo-login")
def config_logo_login():
    logo = get_logo_login()
    if logo is None:
        raise HTTPException(status_code=404)
    return Response(content=logo["conteudo"], media_type=logo["tipo"] or "image/png")


@router.get("/config/favicon")
def config_favicon():
    favicon = get_favicon()
    if favicon is None:
        raise HTTPException(status_code=404)
    return Response(content=favicon["conteudo"], media_type=favicon["tipo"] or "image/png")
