from dataclasses import dataclass

from app.database import db_session


@dataclass(frozen=True)
class ConsultaType:
    id: str
    nome: str
    descricao: str
    icone: str
    custo_creditos: int
    campo_label: str
    campo_placeholder: str
    disponivel: bool = True
    campos_incluidos: str = ""

    @property
    def lista_campos_incluidos(self) -> list[str]:
        return [c.strip() for c in self.campos_incluidos.splitlines() if c.strip()]


def _row_to_type(row) -> ConsultaType:
    return ConsultaType(
        id=row["id"],
        nome=row["nome"],
        descricao=row["descricao"],
        icone=row["icone"],
        custo_creditos=row["custo_creditos"],
        campo_label=row["campo_label"],
        campo_placeholder=row["campo_placeholder"],
        disponivel=bool(row["disponivel"]),
        campos_incluidos=row["campos_incluidos"] if "campos_incluidos" in row.keys() else "",
    )


def get_consulta_type(tipo_id: str) -> ConsultaType | None:
    with db_session() as conn:
        row = conn.execute("SELECT * FROM tipos_consulta WHERE id = ?", (tipo_id,)).fetchone()
        return _row_to_type(row) if row else None


def listar_consulta_types(apenas_disponiveis: bool = False) -> list[ConsultaType]:
    with db_session() as conn:
        query = "SELECT * FROM tipos_consulta"
        if apenas_disponiveis:
            query += " WHERE disponivel = 1"
        query += " ORDER BY created_at ASC"
        rows = conn.execute(query).fetchall()
        return [_row_to_type(row) for row in rows]


def criar_consulta_type(
    id: str,
    nome: str,
    descricao: str,
    icone: str,
    custo_creditos: int,
    campo_label: str = "Placa",
    campo_placeholder: str = "Ex: ABC1234",
    disponivel: bool = True,
    campos_incluidos: str = "",
) -> ConsultaType:
    with db_session() as conn:
        conn.execute(
            """
            INSERT INTO tipos_consulta
                (id, nome, descricao, icone, custo_creditos, campo_label, campo_placeholder, disponivel, campos_incluidos)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (id, nome, descricao, icone, custo_creditos, campo_label, campo_placeholder, int(disponivel), campos_incluidos),
        )
    return get_consulta_type(id)


def atualizar_consulta_type(
    tipo_id: str,
    nome: str,
    descricao: str,
    icone: str,
    custo_creditos: int,
    campo_label: str,
    campo_placeholder: str,
    campos_incluidos: str = "",
) -> None:
    with db_session() as conn:
        conn.execute(
            """
            UPDATE tipos_consulta
            SET nome = ?, descricao = ?, icone = ?, custo_creditos = ?,
                campo_label = ?, campo_placeholder = ?, campos_incluidos = ?
            WHERE id = ?
            """,
            (nome, descricao, icone, custo_creditos, campo_label, campo_placeholder, campos_incluidos, tipo_id),
        )


def alternar_disponibilidade(tipo_id: str) -> None:
    with db_session() as conn:
        conn.execute(
            "UPDATE tipos_consulta SET disponivel = 1 - disponivel WHERE id = ?",
            (tipo_id,),
        )


def excluir_consulta_type(tipo_id: str) -> None:
    with db_session() as conn:
        conn.execute("DELETE FROM tipos_consulta WHERE id = ?", (tipo_id,))
