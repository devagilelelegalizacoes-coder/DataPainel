from typing import Optional

import bcrypt
from fastapi import Request

from app.database import db_session

SESSION_USER_KEY = "user_id"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def get_user_by_email(email: str) -> Optional[dict]:
    with db_session() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE email = ?", (email,)
        ).fetchone()
        return dict(row) if row else None


def get_user_by_id(user_id: int) -> Optional[dict]:
    with db_session() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        return dict(row) if row else None


def create_user(name: str, email: str, password: str, initial_credits: int = 10) -> dict:
    with db_session() as conn:
        total_usuarios = conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]
        is_admin = 1 if total_usuarios == 0 else 0
        status = "aprovado" if is_admin else "pendente"
        cursor = conn.execute(
            "INSERT INTO users (name, email, password_hash, credits, is_admin, status) VALUES (?, ?, ?, ?, ?, ?)",
            (name, email, hash_password(password), initial_credits, is_admin, status),
        )
        user_id = cursor.lastrowid
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row)


def criar_pre_cadastro(
    name: str,
    email: str,
    password: str,
    tipo_profissional: str,
    cnpj_ou_carteirinha: str,
    documento_blob: bytes,
    documento_nome: str,
    documento_tipo: str,
    aceite_termos_em: str,
) -> dict:
    """Cria conta de cliente (agência/despachante) pendente de aprovação por operador/admin."""
    with db_session() as conn:
        total_usuarios = conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]
        is_admin = 1 if total_usuarios == 0 else 0
        status = "aprovado" if is_admin else "pendente"
        cursor = conn.execute(
            """
            INSERT INTO users
                (name, email, password_hash, credits, is_admin, status, tipo_profissional,
                 cnpj_ou_carteirinha, documento_blob, documento_nome, documento_tipo, aceite_termos_em)
            VALUES (?, ?, ?, 0, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                name,
                email,
                hash_password(password),
                is_admin,
                status,
                tipo_profissional,
                cnpj_ou_carteirinha,
                documento_blob,
                documento_nome,
                documento_tipo,
                aceite_termos_em,
            ),
        )
        user_id = cursor.lastrowid
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row)


def listar_cadastros_pendentes() -> list[dict]:
    with db_session() as conn:
        rows = conn.execute(
            "SELECT * FROM users WHERE status = 'pendente' ORDER BY created_at ASC"
        ).fetchall()
        return [dict(row) for row in rows]


def aprovar_cadastro(user_id: int, creditos_iniciais: int = 10) -> None:
    with db_session() as conn:
        conn.execute(
            "UPDATE users SET status = 'aprovado', credits = credits + ?, motivo_rejeicao = NULL WHERE id = ?",
            (creditos_iniciais, user_id),
        )


def rejeitar_cadastro(user_id: int, motivo: str) -> None:
    with db_session() as conn:
        conn.execute(
            "UPDATE users SET status = 'rejeitado', motivo_rejeicao = ? WHERE id = ?",
            (motivo, user_id),
        )


def get_documento_cadastro(user_id: int) -> Optional[dict]:
    with db_session() as conn:
        row = conn.execute(
            "SELECT documento_blob, documento_nome, documento_tipo FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        if not row or not row["documento_blob"]:
            return None
        return dict(row)


def login_user(request: Request, user_id: int) -> None:
    request.session[SESSION_USER_KEY] = user_id


def logout_user(request: Request) -> None:
    request.session.pop(SESSION_USER_KEY, None)


def get_current_user(request: Request) -> Optional[dict]:
    user_id = request.session.get(SESSION_USER_KEY)
    if not user_id:
        return None
    return get_user_by_id(user_id)


def listar_usuarios() -> list[dict]:
    with db_session() as conn:
        rows = conn.execute("SELECT * FROM users ORDER BY created_at ASC").fetchall()
        return [dict(row) for row in rows]


def alternar_operador(user_id: int) -> None:
    with db_session() as conn:
        conn.execute("UPDATE users SET is_operador = 1 - is_operador WHERE id = ?", (user_id,))


def alternar_admin(user_id: int) -> None:
    with db_session() as conn:
        conn.execute("UPDATE users SET is_admin = 1 - is_admin WHERE id = ?", (user_id,))
