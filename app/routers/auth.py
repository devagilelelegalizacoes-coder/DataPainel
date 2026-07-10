from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.auth import (
    create_user,
    get_user_by_email,
    login_user,
    logout_user,
    verify_password,
)

router = APIRouter()
templates = Jinja2Templates(directory="templates")


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
    login_user(request, user["id"])
    return RedirectResponse(url="/dashboard", status_code=303)


@router.get("/registro", response_class=HTMLResponse)
def registro_page(request: Request):
    return templates.TemplateResponse(request, "registro.html", {"error": None})


@router.post("/registro", response_class=HTMLResponse)
def registro_submit(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
):
    if get_user_by_email(email):
        return templates.TemplateResponse(
            request,
            "registro.html",
            {"error": "Este e-mail já está cadastrado"},
            status_code=400,
        )
    user = create_user(name=name, email=email, password=password, initial_credits=10)
    login_user(request, user["id"])
    return RedirectResponse(url="/dashboard", status_code=303)


@router.get("/logout")
def logout(request: Request):
    logout_user(request)
    return RedirectResponse(url="/login", status_code=303)
