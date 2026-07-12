from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from app.templates import templates

from app.auth import alternar_admin, alternar_operador, get_current_user, listar_usuarios
from app.config_sistema import atualizar_favicon, atualizar_logo_login, atualizar_nome_sistema, get_configuracoes
from app.consulta_types import (
    alternar_disponibilidade,
    atualizar_consulta_type,
    criar_consulta_type,
    excluir_consulta_type,
    get_consulta_type,
    listar_consulta_types,
)
from app.credits import relatorio_operadores
from app.pricing import (
    definir_preco_cliente,
    definir_preco_segmento,
    excluir_preco_cliente,
    excluir_preco_segmento,
    listar_precos_clientes,
    listar_precos_segmento,
)

TAMANHO_MAX_LOGO = 2 * 1024 * 1024  # 2MB

router = APIRouter()


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
    documentos_exigidos: str = Form(""),
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
        documentos_exigidos=documentos_exigidos,
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
    documentos_exigidos: str = Form(""),
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
        documentos_exigidos=documentos_exigidos,
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


@router.get("/admin/config", response_class=HTMLResponse)
def admin_config_page(request: Request, erro: str | None = None, sucesso: str | None = None):
    user, redirect = _exigir_admin(request)
    if redirect:
        return redirect

    return templates.TemplateResponse(
        request,
        "admin_config.html",
        {"user": user, "config": get_configuracoes(), "erro": erro, "sucesso": sucesso},
    )


@router.post("/admin/config")
async def admin_config_salvar(
    request: Request,
    nome_sistema: str = Form(...),
    logo_login: UploadFile | None = File(None),
    favicon: UploadFile | None = File(None),
):
    user, redirect = _exigir_admin(request)
    if redirect:
        return redirect

    if nome_sistema.strip():
        atualizar_nome_sistema(nome_sistema.strip())

    if logo_login is not None and logo_login.filename:
        conteudo = await logo_login.read()
        if len(conteudo) > TAMANHO_MAX_LOGO:
            return RedirectResponse(
                url="/admin/config?erro=Logo+muito+grande+(m%C3%A1ximo+2MB)", status_code=303
            )
        atualizar_logo_login(conteudo, logo_login.content_type or "image/png")

    if favicon is not None and favicon.filename:
        conteudo = await favicon.read()
        if len(conteudo) > TAMANHO_MAX_LOGO:
            return RedirectResponse(
                url="/admin/config?erro=Favicon+muito+grande+(m%C3%A1ximo+2MB)", status_code=303
            )
        atualizar_favicon(conteudo, favicon.content_type or "image/png")

    return RedirectResponse(url="/admin/config?sucesso=Personaliza%C3%A7%C3%A3o+atualizada", status_code=303)


@router.get("/admin/precos", response_class=HTMLResponse)
def admin_precos_page(request: Request):
    user, redirect = _exigir_admin(request)
    if redirect:
        return redirect

    return templates.TemplateResponse(
        request,
        "admin_precos.html",
        {
            "user": user,
            "tipos": listar_consulta_types(),
            "usuarios": [u for u in listar_usuarios() if not u["is_admin"] and not u["is_operador"]],
            "precos_segmento": listar_precos_segmento(),
            "precos_clientes": listar_precos_clientes(),
        },
    )


@router.post("/admin/precos/segmento")
def admin_precos_segmento_criar(
    request: Request,
    tipo_profissional: str = Form(...),
    tipo_consulta_id: str = Form(...),
    custo_creditos: int = Form(...),
):
    user, redirect = _exigir_admin(request)
    if redirect:
        return redirect

    definir_preco_segmento(tipo_profissional, tipo_consulta_id, max(0, custo_creditos))
    return RedirectResponse(url="/admin/precos", status_code=303)


@router.post("/admin/precos/segmento/excluir")
def admin_precos_segmento_excluir(
    request: Request,
    tipo_profissional: str = Form(...),
    tipo_consulta_id: str = Form(...),
):
    user, redirect = _exigir_admin(request)
    if redirect:
        return redirect

    excluir_preco_segmento(tipo_profissional, tipo_consulta_id)
    return RedirectResponse(url="/admin/precos", status_code=303)


@router.post("/admin/precos/clientes")
def admin_precos_cliente_criar(
    request: Request,
    user_id: int = Form(...),
    tipo_consulta_id: str = Form(...),
    custo_creditos: int = Form(...),
):
    user, redirect = _exigir_admin(request)
    if redirect:
        return redirect

    definir_preco_cliente(user_id, tipo_consulta_id, max(0, custo_creditos))
    return RedirectResponse(url="/admin/precos", status_code=303)


@router.post("/admin/precos/clientes/excluir")
def admin_precos_cliente_excluir(
    request: Request,
    user_id: int = Form(...),
    tipo_consulta_id: str = Form(...),
):
    user, redirect = _exigir_admin(request)
    if redirect:
        return redirect

    excluir_preco_cliente(user_id, tipo_consulta_id)
    return RedirectResponse(url="/admin/precos", status_code=303)
