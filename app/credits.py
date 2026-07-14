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


def ajustar_creditos_manual(user_id: int, admin_id: int, valor: int, motivo: str) -> int:
    """Ajuste manual feito pelo admin (positivo credita, negativo debita). Fica registrado para auditoria."""
    with db_session() as conn:
        row = conn.execute("SELECT credits FROM users WHERE id = ?", (user_id,)).fetchone()
        novo_saldo = max(0, row["credits"] + valor)
        conn.execute("UPDATE users SET credits = ? WHERE id = ?", (novo_saldo, user_id))
        conn.execute(
            "INSERT INTO ajustes_creditos (user_id, admin_id, valor, motivo) VALUES (?, ?, ?, ?)",
            (user_id, admin_id, valor, motivo),
        )
        return novo_saldo


def listar_ajustes_creditos(limit: int = 30) -> list[dict]:
    with db_session() as conn:
        rows = conn.execute(
            """
            SELECT a.*, u.name AS cliente_nome, ad.name AS admin_nome
            FROM ajustes_creditos a
            JOIN users u ON u.id = a.user_id
            JOIN users ad ON ad.id = a.admin_id
            ORDER BY a.id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]


def registrar_consulta(
    user_id: int,
    tipo: str,
    placa: str,
    custo_creditos: int,
    status: str,
    resultado_resumo: str | None = None,
    resultado_json: str | None = None,
    erro_mensagem: str | None = None,
    custo_apibrasil_centavos: int | None = None,
) -> int:
    with db_session() as conn:
        cursor = conn.execute(
            """
            INSERT INTO consultas (user_id, tipo, placa, custo_creditos, status, resultado_resumo, resultado_json, erro_mensagem, custo_apibrasil_centavos)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, tipo, placa, custo_creditos, status, resultado_resumo, resultado_json, erro_mensagem, custo_apibrasil_centavos),
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


def get_consulta_por_id(consulta_id: int) -> dict | None:
    with db_session() as conn:
        row = conn.execute("SELECT * FROM consultas WHERE id = ?", (consulta_id,)).fetchone()
        return dict(row) if row else None


def listar_pendentes_manuais() -> list[dict]:
    with db_session() as conn:
        rows = conn.execute(
            """
            SELECT c.*, u.name AS cliente_nome, t.nome AS tipo_nome, t.icone AS tipo_icone
            FROM consultas c
            JOIN users u ON u.id = c.user_id
            JOIN tipos_consulta t ON t.id = c.tipo
            WHERE c.status = 'pendente' AND c.operador_id IS NULL
            ORDER BY c.created_at ASC
            """
        ).fetchall()
        return [dict(row) for row in rows]


def contar_pendentes_manuais() -> int:
    with db_session() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM consultas WHERE status = 'pendente' AND operador_id IS NULL"
        ).fetchone()
        return row["n"]


def listar_em_atendimento(operador_id: int) -> list[dict]:
    with db_session() as conn:
        rows = conn.execute(
            """
            SELECT c.*, u.name AS cliente_nome, t.nome AS tipo_nome, t.icone AS tipo_icone
            FROM consultas c
            JOIN users u ON u.id = c.user_id
            JOIN tipos_consulta t ON t.id = c.tipo
            WHERE c.status = 'em_atendimento' AND c.operador_id = ?
            ORDER BY c.atendido_em ASC
            """,
            (operador_id,),
        ).fetchall()
        return [dict(row) for row in rows]


def reivindicar_consulta(consulta_id: int, operador_id: int) -> bool:
    """Tenta 'puxar' um pedido pendente para o operador. Atomico: so um operador ganha a corrida."""
    with db_session() as conn:
        cursor = conn.execute(
            """
            UPDATE consultas
            SET status = 'em_atendimento', operador_id = ?, atendido_em = datetime('now')
            WHERE id = ? AND status = 'pendente' AND operador_id IS NULL
            """,
            (operador_id, consulta_id),
        )
        return cursor.rowcount == 1


def concluir_consulta_manual(
    consulta_id: int,
    resultado_resumo: str,
    resultado_json: str | None,
    anexo_blob: bytes | None,
    anexo_nome: str | None,
    anexo_tipo: str | None,
    anexo_tamanho_original: int | None,
) -> None:
    with db_session() as conn:
        conn.execute(
            """
            UPDATE consultas
            SET status = 'sucesso', resultado_resumo = ?, resultado_json = ?,
                anexo_blob = ?, anexo_nome = ?, anexo_tipo = ?, anexo_tamanho_original = ?,
                concluido_em = datetime('now')
            WHERE id = ?
            """,
            (resultado_resumo, resultado_json, anexo_blob, anexo_nome, anexo_tipo, anexo_tamanho_original, consulta_id),
        )


def marcar_consulta_manual_erro(consulta_id: int, mensagem: str) -> None:
    with db_session() as conn:
        conn.execute(
            """
            UPDATE consultas
            SET status = 'erro', erro_mensagem = ?, custo_creditos = 0, concluido_em = datetime('now')
            WHERE id = ?
            """,
            (mensagem, consulta_id),
        )


def get_anexo(consulta_id: int) -> dict | None:
    with db_session() as conn:
        row = conn.execute(
            "SELECT anexo_blob, anexo_nome, anexo_tipo FROM consultas WHERE id = ?",
            (consulta_id,),
        ).fetchone()
        if row is None or row["anexo_blob"] is None:
            return None
        return dict(row)


def salvar_documento_consulta(
    consulta_id: int,
    nome_documento: str,
    arquivo_nome: str,
    arquivo_tipo: str | None,
    arquivo_blob: bytes,
    tamanho_original: int,
) -> None:
    with db_session() as conn:
        conn.execute(
            """
            INSERT INTO consulta_documentos
                (consulta_id, nome_documento, arquivo_nome, arquivo_tipo, arquivo_blob, tamanho_original)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (consulta_id, nome_documento, arquivo_nome, arquivo_tipo, arquivo_blob, tamanho_original),
        )


def listar_documentos_consulta(consulta_id: int) -> list[dict]:
    with db_session() as conn:
        rows = conn.execute(
            "SELECT id, nome_documento, arquivo_nome, arquivo_tipo, tamanho_original FROM consulta_documentos WHERE consulta_id = ? ORDER BY id ASC",
            (consulta_id,),
        ).fetchall()
        return [dict(row) for row in rows]


def get_documento_consulta(doc_id: int) -> dict | None:
    with db_session() as conn:
        row = conn.execute(
            "SELECT * FROM consulta_documentos WHERE id = ?", (doc_id,)
        ).fetchone()
        return dict(row) if row else None


def relatorio_operadores() -> list[dict]:
    with db_session() as conn:
        rows = conn.execute(
            """
            SELECT u.id, u.name, u.email,
                   COUNT(CASE WHEN c.status = 'sucesso' THEN 1 END) AS total_concluidas,
                   COUNT(CASE WHEN c.status = 'em_atendimento' THEN 1 END) AS total_em_andamento
            FROM users u
            LEFT JOIN consultas c ON c.operador_id = u.id
            WHERE u.is_operador = 1
            GROUP BY u.id
            ORDER BY total_concluidas DESC
            """
        ).fetchall()
        return [dict(row) for row in rows]
