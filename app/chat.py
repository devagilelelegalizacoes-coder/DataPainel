from app.database import db_session


def enviar_mensagem(cliente_id: int, autor_id: int, autor_tipo: str, mensagem: str) -> int:
    lida_pelo_cliente = 1 if autor_tipo == "cliente" else 0
    lida_pelo_operador = 1 if autor_tipo == "operador" else 0
    with db_session() as conn:
        cursor = conn.execute(
            """
            INSERT INTO mensagens_chat
                (cliente_id, autor_id, autor_tipo, mensagem, lida_pelo_cliente, lida_pelo_operador)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (cliente_id, autor_id, autor_tipo, mensagem, lida_pelo_cliente, lida_pelo_operador),
        )
        return cursor.lastrowid


def listar_mensagens(cliente_id: int) -> list[dict]:
    with db_session() as conn:
        rows = conn.execute(
            """
            SELECT m.*, u.name AS autor_nome
            FROM mensagens_chat m
            JOIN users u ON u.id = m.autor_id
            WHERE m.cliente_id = ?
            ORDER BY m.id ASC
            """,
            (cliente_id,),
        ).fetchall()
        return [dict(row) for row in rows]


def marcar_lidas(cliente_id: int, quem: str) -> None:
    coluna = "lida_pelo_cliente" if quem == "cliente" else "lida_pelo_operador"
    autor_oposto = "operador" if quem == "cliente" else "cliente"
    with db_session() as conn:
        conn.execute(
            f"UPDATE mensagens_chat SET {coluna} = 1 WHERE cliente_id = ? AND autor_tipo = ?",
            (cliente_id, autor_oposto),
        )


def contar_nao_lidas_cliente(cliente_id: int) -> int:
    with db_session() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM mensagens_chat WHERE cliente_id = ? AND autor_tipo = 'operador' AND lida_pelo_cliente = 0",
            (cliente_id,),
        ).fetchone()
        return row["n"]


def listar_conversas() -> list[dict]:
    """Um item por cliente que já trocou mensagem, com a última mensagem e não lidas pelo operador."""
    with db_session() as conn:
        rows = conn.execute(
            """
            SELECT
                u.id AS cliente_id,
                u.name AS cliente_nome,
                (SELECT mensagem FROM mensagens_chat WHERE cliente_id = u.id ORDER BY id DESC LIMIT 1) AS ultima_mensagem,
                (SELECT created_at FROM mensagens_chat WHERE cliente_id = u.id ORDER BY id DESC LIMIT 1) AS ultima_em,
                (SELECT COUNT(*) FROM mensagens_chat WHERE cliente_id = u.id AND autor_tipo = 'cliente' AND lida_pelo_operador = 0) AS nao_lidas
            FROM users u
            WHERE EXISTS (SELECT 1 FROM mensagens_chat WHERE cliente_id = u.id)
            ORDER BY ultima_em DESC
            """
        ).fetchall()
        return [dict(row) for row in rows]


def contar_conversas_nao_lidas() -> int:
    with db_session() as conn:
        row = conn.execute(
            """
            SELECT COUNT(DISTINCT cliente_id) AS n
            FROM mensagens_chat
            WHERE autor_tipo = 'cliente' AND lida_pelo_operador = 0
            """
        ).fetchone()
        return row["n"]
