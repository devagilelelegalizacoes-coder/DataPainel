import gzip
from typing import Optional

from app.database import db_session


def get_configuracoes() -> dict:
    with db_session() as conn:
        row = conn.execute(
            "SELECT nome_sistema, logo_login_tipo, favicon_tipo FROM configuracoes_sistema WHERE id = 1"
        ).fetchone()
        if not row:
            return {"nome_sistema": "DataPainel", "tem_logo_login": False, "tem_favicon": False}
        return {
            "nome_sistema": row["nome_sistema"],
            "tem_logo_login": row["logo_login_tipo"] is not None,
            "tem_favicon": row["favicon_tipo"] is not None,
        }


def atualizar_nome_sistema(nome: str) -> None:
    with db_session() as conn:
        conn.execute("UPDATE configuracoes_sistema SET nome_sistema = ? WHERE id = 1", (nome,))


def atualizar_logo_login(conteudo: bytes, tipo: str) -> None:
    with db_session() as conn:
        conn.execute(
            "UPDATE configuracoes_sistema SET logo_login_blob = ?, logo_login_tipo = ? WHERE id = 1",
            (gzip.compress(conteudo, compresslevel=6), tipo),
        )


def atualizar_favicon(conteudo: bytes, tipo: str) -> None:
    with db_session() as conn:
        conn.execute(
            "UPDATE configuracoes_sistema SET favicon_blob = ?, favicon_tipo = ? WHERE id = 1",
            (gzip.compress(conteudo, compresslevel=6), tipo),
        )


def get_logo_login() -> Optional[dict]:
    with db_session() as conn:
        row = conn.execute(
            "SELECT logo_login_blob, logo_login_tipo FROM configuracoes_sistema WHERE id = 1"
        ).fetchone()
        if not row or not row["logo_login_blob"]:
            return None
        return {"conteudo": gzip.decompress(row["logo_login_blob"]), "tipo": row["logo_login_tipo"]}


def get_favicon() -> Optional[dict]:
    with db_session() as conn:
        row = conn.execute(
            "SELECT favicon_blob, favicon_tipo FROM configuracoes_sistema WHERE id = 1"
        ).fetchone()
        if not row or not row["favicon_blob"]:
            return None
        return {"conteudo": gzip.decompress(row["favicon_blob"]), "tipo": row["favicon_tipo"]}
