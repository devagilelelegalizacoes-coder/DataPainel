from app.database import db_session


def resolver_custo(user: dict, tipo) -> int:
    """Preço em créditos que este usuário paga por este tipo de consulta.

    Prioridade: contrato individual do cliente > preço padrão do segmento
    (despachante/agência) > custo_creditos padrão do card.
    """
    with db_session() as conn:
        individual = conn.execute(
            "SELECT custo_creditos FROM precos_clientes WHERE user_id = ? AND tipo_consulta_id = ?",
            (user["id"], tipo.id),
        ).fetchone()
        if individual is not None:
            return individual["custo_creditos"]

        tipo_profissional = user["tipo_profissional"] if "tipo_profissional" in user.keys() else None
        if tipo_profissional:
            segmento = conn.execute(
                "SELECT custo_creditos FROM precos_segmento WHERE tipo_profissional = ? AND tipo_consulta_id = ?",
                (tipo_profissional, tipo.id),
            ).fetchone()
            if segmento is not None:
                return segmento["custo_creditos"]

    return tipo.custo_creditos


def resolver_custos(user: dict, tipos: list) -> dict[str, int]:
    return {tipo.id: resolver_custo(user, tipo) for tipo in tipos}


def listar_precos_segmento() -> list[dict]:
    with db_session() as conn:
        rows = conn.execute(
            """
            SELECT ps.tipo_profissional, ps.tipo_consulta_id, ps.custo_creditos, t.nome AS tipo_nome
            FROM precos_segmento ps
            JOIN tipos_consulta t ON t.id = ps.tipo_consulta_id
            ORDER BY ps.tipo_profissional ASC, t.nome ASC
            """
        ).fetchall()
        return [dict(row) for row in rows]


def definir_preco_segmento(tipo_profissional: str, tipo_consulta_id: str, custo_creditos: int) -> None:
    with db_session() as conn:
        conn.execute(
            """
            INSERT INTO precos_segmento (tipo_profissional, tipo_consulta_id, custo_creditos)
            VALUES (?, ?, ?)
            ON CONFLICT (tipo_profissional, tipo_consulta_id)
            DO UPDATE SET custo_creditos = excluded.custo_creditos
            """,
            (tipo_profissional, tipo_consulta_id, custo_creditos),
        )


def excluir_preco_segmento(tipo_profissional: str, tipo_consulta_id: str) -> None:
    with db_session() as conn:
        conn.execute(
            "DELETE FROM precos_segmento WHERE tipo_profissional = ? AND tipo_consulta_id = ?",
            (tipo_profissional, tipo_consulta_id),
        )


def listar_precos_clientes() -> list[dict]:
    with db_session() as conn:
        rows = conn.execute(
            """
            SELECT pc.user_id, pc.tipo_consulta_id, pc.custo_creditos, u.name AS cliente_nome, t.nome AS tipo_nome
            FROM precos_clientes pc
            JOIN users u ON u.id = pc.user_id
            JOIN tipos_consulta t ON t.id = pc.tipo_consulta_id
            ORDER BY u.name ASC, t.nome ASC
            """
        ).fetchall()
        return [dict(row) for row in rows]


def definir_preco_cliente(user_id: int, tipo_consulta_id: str, custo_creditos: int) -> None:
    with db_session() as conn:
        conn.execute(
            """
            INSERT INTO precos_clientes (user_id, tipo_consulta_id, custo_creditos)
            VALUES (?, ?, ?)
            ON CONFLICT (user_id, tipo_consulta_id)
            DO UPDATE SET custo_creditos = excluded.custo_creditos
            """,
            (user_id, tipo_consulta_id, custo_creditos),
        )


def excluir_preco_cliente(user_id: int, tipo_consulta_id: str) -> None:
    with db_session() as conn:
        conn.execute(
            "DELETE FROM precos_clientes WHERE user_id = ? AND tipo_consulta_id = ?",
            (user_id, tipo_consulta_id),
        )
