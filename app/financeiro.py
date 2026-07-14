from app.database import db_session


def total_faturado_centavos() -> int:
    with db_session() as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(valor_centavos), 0) AS total FROM pagamentos WHERE status = 'aprovado'"
        ).fetchone()
        return row["total"]


def total_custo_apibrasil_centavos() -> int:
    with db_session() as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(custo_apibrasil_centavos), 0) AS total FROM consultas WHERE status = 'sucesso'"
        ).fetchone()
        return row["total"]


def total_creditos_em_aberto() -> int:
    with db_session() as conn:
        row = conn.execute("SELECT COALESCE(SUM(credits), 0) AS total FROM users").fetchone()
        return row["total"]


def resumo_por_tipo() -> list[dict]:
    with db_session() as conn:
        rows = conn.execute(
            """
            SELECT
                t.id AS tipo_id,
                t.nome AS tipo_nome,
                COUNT(c.id) AS execucoes,
                COALESCE(SUM(c.custo_creditos), 0) AS receita_centavos,
                COALESCE(SUM(c.custo_apibrasil_centavos), 0) AS custo_centavos
            FROM tipos_consulta t
            LEFT JOIN consultas c ON c.tipo = t.id AND c.status = 'sucesso'
            GROUP BY t.id
            HAVING execucoes > 0
            ORDER BY receita_centavos DESC
            """
        ).fetchall()
        resultado = []
        for row in rows:
            item = dict(row)
            # custo_creditos = créditos, e 1 crédito = R$1 = 100 centavos
            item["receita_centavos"] = item["receita_centavos"] * 100
            item["margem_centavos"] = item["receita_centavos"] - item["custo_centavos"]
            resultado.append(item)
        return resultado
