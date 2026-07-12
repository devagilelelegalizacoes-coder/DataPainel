import gzip
import json
from app.templates import templates

from fastapi import APIRouter, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from app.auth import (
    aprovar_cadastro,
    get_current_user,
    get_documento_cadastro,
    listar_cadastros_pendentes,
    rejeitar_cadastro,
)
from app.consulta_types import get_consulta_type
from app.credits import (
    concluir_consulta_manual,
    estornar_creditos,
    get_consulta_por_id,
    get_documento_consulta,
    listar_documentos_consulta,
    listar_em_atendimento,
    listar_pendentes_manuais,
    marcar_consulta_manual_erro,
    reivindicar_consulta,
)

router = APIRouter()

TAMANHO_MAX_ANEXO = 8 * 1024 * 1024  # 8MB antes de comprimir


def _exigir_operador(request: Request):
    user = get_current_user(request)
    if not user:
        return None, RedirectResponse(url="/login", status_code=303)
    if not user["is_operador"] and not user["is_admin"]:
        raise HTTPException(status_code=403, detail="Acesso restrito a operadores")
    return user, None


@router.get("/operador", response_class=HTMLResponse)
def operador_fila(request: Request):
    user, redirect = _exigir_operador(request)
    if redirect:
        return redirect

    pendentes = listar_pendentes_manuais()
    meus = listar_em_atendimento(user["id"])
    return templates.TemplateResponse(
        request,
        "operador.html",
        {"user": user, "pendentes": pendentes, "meus": meus},
    )


@router.get("/operador/api/pendentes-ids")
def operador_pendentes_ids(request: Request):
    user, redirect = _exigir_operador(request)
    if redirect:
        return redirect

    ids = [p["id"] for p in listar_pendentes_manuais()]
    return JSONResponse({"ids": ids})


@router.get("/operador/cadastros", response_class=HTMLResponse)
def operador_cadastros(request: Request, erro: str | None = None):
    user, redirect = _exigir_operador(request)
    if redirect:
        return redirect

    pendentes = listar_cadastros_pendentes()
    return templates.TemplateResponse(
        request,
        "operador_cadastros.html",
        {"user": user, "pendentes": pendentes, "erro": erro},
    )


@router.get("/operador/cadastros/{user_id}/documento")
def operador_cadastro_documento(request: Request, user_id: int):
    user, redirect = _exigir_operador(request)
    if redirect:
        return redirect

    documento = get_documento_cadastro(user_id)
    if documento is None:
        raise HTTPException(status_code=404, detail="Documento não encontrado")

    conteudo = gzip.decompress(documento["documento_blob"])
    return Response(
        content=conteudo,
        media_type=documento["documento_tipo"] or "application/octet-stream",
        headers={"Content-Disposition": f'inline; filename="{documento["documento_nome"]}"'},
    )


@router.post("/operador/cadastros/{user_id}/aprovar")
def operador_cadastro_aprovar(request: Request, user_id: int):
    user, redirect = _exigir_operador(request)
    if redirect:
        return redirect

    aprovar_cadastro(user_id)
    return RedirectResponse(url="/operador/cadastros", status_code=303)


@router.post("/operador/cadastros/{user_id}/rejeitar")
def operador_cadastro_rejeitar(request: Request, user_id: int, motivo: str = Form(...)):
    user, redirect = _exigir_operador(request)
    if redirect:
        return redirect

    rejeitar_cadastro(user_id, motivo)
    return RedirectResponse(url="/operador/cadastros", status_code=303)


@router.post("/operador/{consulta_id}/puxar")
def operador_puxar(request: Request, consulta_id: int):
    user, redirect = _exigir_operador(request)
    if redirect:
        return redirect

    sucesso = reivindicar_consulta(consulta_id, user["id"])
    if not sucesso:
        return RedirectResponse(
            url="/operador?erro=Esse+pedido+ja+foi+puxado+por+outro+operador", status_code=303
        )
    return RedirectResponse(url=f"/operador/{consulta_id}", status_code=303)


@router.get("/operador/{consulta_id}", response_class=HTMLResponse)
def operador_atender_form(request: Request, consulta_id: int):
    user, redirect = _exigir_operador(request)
    if redirect:
        return redirect

    consulta = get_consulta_por_id(consulta_id)
    if consulta is None:
        raise HTTPException(status_code=404, detail="Consulta não encontrada")
    if consulta["operador_id"] != user["id"] or consulta["status"] != "em_atendimento":
        raise HTTPException(status_code=403, detail="Este pedido não está atribuído a você")

    tipo = get_consulta_type(consulta["tipo"])
    documentos = listar_documentos_consulta(consulta_id)
    return templates.TemplateResponse(
        request,
        "operador_atender.html",
        {"user": user, "consulta": consulta, "tipo": tipo, "documentos": documentos, "erro": None},
    )


@router.get("/operador/{consulta_id}/documentos/{doc_id}")
def operador_documento_download(request: Request, consulta_id: int, doc_id: int):
    user, redirect = _exigir_operador(request)
    if redirect:
        return redirect

    consulta = get_consulta_por_id(consulta_id)
    if consulta is None:
        raise HTTPException(status_code=404, detail="Consulta não encontrada")
    if consulta["operador_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Este pedido não está atribuído a você")

    documento = get_documento_consulta(doc_id)
    if documento is None or documento["consulta_id"] != consulta_id:
        raise HTTPException(status_code=404, detail="Documento não encontrado")

    conteudo = gzip.decompress(documento["arquivo_blob"])
    return Response(
        content=conteudo,
        media_type=documento["arquivo_tipo"] or "application/octet-stream",
        headers={"Content-Disposition": f'inline; filename="{documento["arquivo_nome"]}"'},
    )


@router.post("/operador/{consulta_id}/concluir")
async def operador_concluir(
    request: Request,
    consulta_id: int,
    observacao: str = Form(""),
    arquivo: UploadFile | None = File(None),
):
    user, redirect = _exigir_operador(request)
    if redirect:
        return redirect

    consulta = get_consulta_por_id(consulta_id)
    if consulta is None:
        raise HTTPException(status_code=404, detail="Consulta não encontrada")
    if consulta["operador_id"] != user["id"] or consulta["status"] != "em_atendimento":
        raise HTTPException(status_code=403, detail="Este pedido não está atribuído a você")

    anexo_blob = None
    anexo_nome = None
    anexo_tipo = None
    anexo_tamanho_original = None

    if arquivo is not None and arquivo.filename:
        conteudo = await arquivo.read()
        if len(conteudo) > TAMANHO_MAX_ANEXO:
            tipo = get_consulta_type(consulta["tipo"])
            return templates.TemplateResponse(
                request,
                "operador_atender.html",
                {
                    "user": user,
                    "consulta": consulta,
                    "tipo": tipo,
                    "erro": "Arquivo muito grande (máximo 8MB).",
                },
                status_code=400,
            )
        anexo_tamanho_original = len(conteudo)
        anexo_blob = gzip.compress(conteudo, compresslevel=6)
        anexo_nome = arquivo.filename
        anexo_tipo = arquivo.content_type

    dados_resultado = {"observacao_operador": observacao.strip()} if observacao.strip() else {}
    if anexo_nome:
        dados_resultado["documento_anexado"] = anexo_nome

    resumo = observacao.strip()[:120] if observacao.strip() else (
        f"Documento anexado: {anexo_nome}" if anexo_nome else "Atendimento concluído"
    )

    concluir_consulta_manual(
        consulta_id=consulta_id,
        resultado_resumo=resumo,
        resultado_json=json.dumps({"data": dados_resultado}, ensure_ascii=False) if dados_resultado else None,
        anexo_blob=anexo_blob,
        anexo_nome=anexo_nome,
        anexo_tipo=anexo_tipo,
        anexo_tamanho_original=anexo_tamanho_original,
    )
    return RedirectResponse(url="/operador", status_code=303)


@router.post("/operador/{consulta_id}/erro")
def operador_marcar_erro(request: Request, consulta_id: int, mensagem: str = Form(...)):
    user, redirect = _exigir_operador(request)
    if redirect:
        return redirect

    consulta = get_consulta_por_id(consulta_id)
    if consulta is None:
        raise HTTPException(status_code=404, detail="Consulta não encontrada")
    if consulta["operador_id"] != user["id"] or consulta["status"] != "em_atendimento":
        raise HTTPException(status_code=403, detail="Este pedido não está atribuído a você")

    if consulta["custo_creditos"]:
        estornar_creditos(consulta["user_id"], consulta["custo_creditos"])
    marcar_consulta_manual_erro(consulta_id, mensagem)
    return RedirectResponse(url="/operador", status_code=303)
