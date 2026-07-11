import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.database import init_db
from app.routers import admin, auth, consultas, creditos, dashboard

load_dotenv()

app = FastAPI(title="APIBrasil - Consulta de Veículos")

secret_key = os.getenv("SESSION_SECRET_KEY")
if not secret_key:
    raise RuntimeError("SESSION_SECRET_KEY não configurado no ambiente (.env)")

app.add_middleware(SessionMiddleware, secret_key=secret_key)
app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(consultas.router)
app.include_router(admin.router)
app.include_router(creditos.router)


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
def root():
    return """<!doctype html>
<html lang="pt-br"><head><meta charset="utf-8">
<meta http-equiv="refresh" content="0; url=/login"></head>
<body>Redirecionando para <a href="/login">/login</a>...</body></html>"""
