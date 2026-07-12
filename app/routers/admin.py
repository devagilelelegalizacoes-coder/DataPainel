from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.auth import alternar_admin, alternar_operador, get_current_user, listar_usuarios
from app.consulta_types import (
    alternar_disponibilidade,
    atualizar_consulta_type,
    criar_consulta_type,
    excluir_consulta_type,
    get_consulta_type,
    listar_consulta_types,
)
from app.credits import relatorio_operadores

router = APIRouter()
templates = Jinja2Templates(directory="templates")


def _slugify(texto: str) -> str:
    import re
    import unicodedata

    normalizado = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", normalizado).strip("-").lower()
    return slug or "consulta"


def _exigir_admin(request: Request):
    user = get_current_user(request)
    if not user:
        return None, RedirectResponse(url="/login", status_code=303)
    if not user["is_admin"]:
        raise HTTPException(status_code=403, detail="Acesso restrito a administradores")
    return user, None


@router.get("/admin/consultas", response_class=HTMLResponse)
def admin_consultas_page(request: Request, erro: str | None = None):
    user, redirect = _exigir_admin(request)
    if redirect:
        return redirect

    tipos = listar_consulta_types()
    return templates.TemplateResponse(
        request,
        "admin_consultas.html",
        {"user": user, "tipos": tipos, "erro": erro, "editar": None},
    )


@router.get("/admin/consultas/{tipo_id}/editar", response_class=HTMLResponse)
def admin_consulta_editar_form(request: Request, tipo_id: str):
    user, redirect = _exigir_admin(request)
    if redirect:
        return redirect

    tipo_editar = get_consulta_type(tipo_id)
    if tipo_editar is None:
        raise HTTPException(status_code=404, detail="Consulta não encontrada")

    tipos = listar_consulta_types()
    return templates.TemplateResponse(
        request,
        "admin_consultas.html",
        {"user": user, "tipos": tipos, "erro": None, "editar": tipo_editar},
    )


@router.post("/admin/consultas", response_class=HTMLResponse)
def admin_consulta_criar(
    request: Request,
    nome: str = Form(...),
    descricao: str = Form(""),
    icone: str = Form("🔍"),
    custo_creditos: int = Form(...),
    campo_label: str = Form("Placa"),
    campo_placeholder: str = Form("Ex: ABC1234"),
    campos_incluidos: str = Form(""),
    manual: bool = Form(False),
):
    user, redirect = _exigir_admin(request)
    if redirect:
        return redirect

    tipo_id = _slugify(nome)
    if get_consulta_type(tipo_id) is not None:
        tipos = listar_consulta_types()
        return templates.TemplateResponse(
            request,
            "admin_consultas.html",
            {
                "user": user,
                "tipos": tipos,
                "erro": f"Já existe uma consulta com identificador '{tipo_id}'. Escolha outro nome.",
                "editar": None,
            },
            status_code=400,
        )

    criar_consulta_type(
        id=tipo_id,
        nome=nome,
        descricao=descricao,
        icone=icone or "🔍",
        custo_creditos=max(0, custo_creditos),
        campo_label=campo_label or "Placa",
        campo_placeholder=campo_placeholder or "Ex: ABC1234",
        disponivel=False,
        campos_incluidos=campos_incluidos,
        manual=manual,
    )
    return RedirectResponse(url="/admin/consultas", status_code=303)


@router.post("/admin/consultas/{tipo_id}/editar", response_class=HTMLResponse)
def admin_consulta_editar(
    request: Request,
    tipo_id: str,
    nome: str = Form(...),
    descricao: str = Form(""),
    icone: str = Form("🔍"),
    custo_creditos: int = Form(...),
    campo_label: str = Form("Placa"),
    campo_placeholder: str = Form("Ex: ABC1234"),
    campos_incluidos: str = Form(""),
    manual: bool = Form(False),
):
    user, redirect = _exigir_admin(request)
    if redirect:
        return redirect

    if get_consulta_type(tipo_id) is None:
        raise HTTPException(status_code=404, detail="Consulta não encontrada")

    atualizar_consulta_type(
        tipo_id=tipo_id,
        nome=nome,
        descricao=descricao,
        icone=icone or "🔍",
        custo_creditos=max(0, custo_creditos),
        campo_label=campo_label or "Placa",
        campo_placeholder=campo_placeholder or "Ex: ABC1234",
        campos_incluidos=campos_incluidos,
        manual=manual,
    )
    return RedirectResponse(url="/admin/consultas", status_code=303)


@router.post("/admin/consultas/{tipo_id}/toggle")
def admin_consulta_toggle(request: Request, tipo_id: str):
    user, redirect = _exigir_admin(request)
    if redirect:
        return redirect

    if get_consulta_type(tipo_id) is None:
        raise HTTPException(status_code=404, detail="Consulta não encontrada")

    alternar_disponibilidade(tipo_id)
    return RedirectResponse(url="/admin/consultas", status_code=303)


@router.post("/admin/consultas/{tipo_id}/excluir")
def admin_consulta_excluir(request: Request, tipo_id: str):
    user, redirect = _exigir_admin(request)
    if redirect:
        return redirect

    if get_consulta_type(tipo_id) is None:
        raise HTTPException(status_code=404, detail="Consulta não encontrada")

    excluir_consulta_type(tipo_id)
    return RedirectResponse(url="/admin/consultas", status_code=303)


@router.get("/admin/usuarios", response_class=HTMLResponse)
def admin_usuarios_page(request: Request):
    user, redirect = _exigir_admin(request)
    if redirect:
        return redirect

    usuarios = listar_usuarios()
    return templates.TemplateResponse(
        request,
        "admin_usuarios.html",
        {"user": user, "usuarios": usuarios},
    )


@router.post("/admin/usuarios/{user_id}/operador")
def admin_toggle_operador(request: Request, user_id: int):
    user, redirect = _exigir_admin(request)
    if redirect:
        return redirect

    alternar_operador(user_id)
    return RedirectResponse(url="/admin/usuarios", status_code=303)


@router.post("/admin/usuarios/{user_id}/admin")
def admin_toggle_admin(request: Request, user_id: int):
    user, redirect = _exigir_admin(request)
    if redirect:
        return redirect

    if user_id == user["id"]:
        return RedirectResponse(url="/admin/usuarios", status_code=303)

    alternar_admin(user_id)
    return RedirectResponse(url="/admin/usuarios", status_code=303)


@router.get("/admin/operadores", response_class=HTMLResponse)
def admin_operadores_page(request: Request):
    user, redirect = _exigir_admin(request)
    if redirect:
        return redirect

    relatorio = relatorio_operadores()
    return templates.TemplateResponse(
        request,
        "admin_operadores.html",
        {"user": user, "relatorio": relatorio},
    )
