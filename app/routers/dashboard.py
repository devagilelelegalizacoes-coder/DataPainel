from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.auth import get_current_user
from app.credits import listar_consultas

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    consultas = listar_consultas(user["id"], limit=5)
    total_consultas = len(listar_consultas(user["id"], limit=1000))

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "user": user,
            "consultas": consultas,
            "total_consultas": total_consultas,
        },
    )
