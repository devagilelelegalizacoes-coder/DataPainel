from dataclasses import dataclass

from app.database import db_session


class SaldoInsuficienteError(Exception):
    pass


@dataclass
class ConsultaRegistro:
    id: int
    user_id: int
    placa: str
    custo_creditos: int
    status: str


def debitar_creditos(user_id: int, valor: int) -> int:
    with db_session() as conn:
        row = conn.execute("SELECT credits FROM users WHERE id = ?", (user_id,)).fetchone()
        if row is None or row["credits"] < valor:
            raise SaldoInsuficienteError("Saldo de créditos insuficiente para realizar a consulta")
        novo_saldo = row["credits"] - valor
        conn.execute("UPDATE users SET credits = ? WHERE id = ?", (novo_saldo, user_id))
        return novo_saldo


def estornar_creditos(user_id: int, valor: int) -> int:
    with db_session() as conn:
        row = conn.execute("SELECT credits FROM users WHERE id = ?", (user_id,)).fetchone()
        novo_saldo = row["credits"] + valor
        conn.execute("UPDATE users SET credits = ? WHERE id = ?", (novo_saldo, user_id))
        return novo_saldo


def registrar_consulta(
    user_id: int,
    tipo: str,
    placa: str,
    custo_creditos: int,
    status: str,
    resultado_resumo: str | None = None,
    resultado_json: str | None = None,
    erro_mensagem: str | None = None,
) -> int:
    with db_session() as conn:
        cursor = conn.execute(
            """
            INSERT INTO consultas (user_id, tipo, placa, custo_creditos, status, resultado_resumo, resultado_json, erro_mensagem)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, tipo, placa, custo_creditos, status, resultado_resumo, resultado_json, erro_mensagem),
        )
        return cursor.lastrowid


def listar_consultas(user_id: int, limit: int = 20) -> list[dict]:
    with db_session() as conn:
        rows = conn.execute(
            """
            SELECT * FROM consultas
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()
        return [dict(row) for row in rows]


def get_consulta(consulta_id: int, user_id: int) -> dict | None:
    with db_session() as conn:
        row = conn.execute(
            "SELECT * FROM consultas WHERE id = ? AND user_id = ?",
            (consulta_id, user_id),
        ).fetchone()
        return dict(row) if row else None
