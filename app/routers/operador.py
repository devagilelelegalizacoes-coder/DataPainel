import gzip
import json

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.auth import get_current_user
from app.consulta_types import get_consulta_type
from app.credits import (
    concluir_consulta_manual,
    estornar_creditos,
    get_consulta_por_id,
    listar_em_atendimento,
    listar_pendentes_manuais,
    marcar_consulta_manual_erro,
    reivindicar_consulta,
)

router = APIRouter()
templates = Jinja2Templates(directory="templates")

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
    return templates.TemplateResponse(
        request,
        "operador_atender.html",
        {"user": user, "consulta": consulta, "tipo": tipo, "erro": None},
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
