from dataclasses import dataclass

from app.database import db_session

MAX_DOCUMENTOS_EXIGIDOS = 5


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
    manual: bool = False
    documentos_exigidos: str = ""
    segmentos_visiveis: str = ""
    custo_apibrasil_centavos: int = 0

    @property
    def custo_apibrasil_reais(self) -> float:
        return self.custo_apibrasil_centavos / 100

    @property
    def lista_campos_incluidos(self) -> list[str]:
        return [c.strip() for c in self.campos_incluidos.splitlines() if c.strip()]

    @property
    def lista_documentos_exigidos(self) -> list[str]:
        itens = [d.strip() for d in self.documentos_exigidos.split(",") if d.strip()]
        return itens[:MAX_DOCUMENTOS_EXIGIDOS]

    @property
    def lista_segmentos_visiveis(self) -> list[str]:
        return [s.strip() for s in self.segmentos_visiveis.split(",") if s.strip()]

    def visivel_para(self, tipo_profissional: str | None) -> bool:
        segmentos = self.lista_segmentos_visiveis
        if not segmentos:
            return True
        return tipo_profissional in segmentos


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
        manual=bool(row["manual"]) if "manual" in row.keys() else False,
        documentos_exigidos=row["documentos_exigidos"] if "documentos_exigidos" in row.keys() else "",
        segmentos_visiveis=row["segmentos_visiveis"] if "segmentos_visiveis" in row.keys() else "",
        custo_apibrasil_centavos=row["custo_apibrasil_centavos"] if "custo_apibrasil_centavos" in row.keys() else 0,
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
    manual: bool = False,
    documentos_exigidos: str = "",
    segmentos_visiveis: str = "",
    custo_apibrasil_centavos: int = 0,
) -> ConsultaType:
    documentos_exigidos = _limitar_documentos_exigidos(documentos_exigidos)
    with db_session() as conn:
        conn.execute(
            """
            INSERT INTO tipos_consulta
                (id, nome, descricao, icone, custo_creditos, campo_label, campo_placeholder, disponivel, campos_incluidos, manual, documentos_exigidos, segmentos_visiveis, custo_apibrasil_centavos)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (id, nome, descricao, icone, custo_creditos, campo_label, campo_placeholder, int(disponivel), campos_incluidos, int(manual), documentos_exigidos, segmentos_visiveis, custo_apibrasil_centavos),
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
    manual: bool = False,
    documentos_exigidos: str = "",
    segmentos_visiveis: str = "",
    custo_apibrasil_centavos: int = 0,
) -> None:
    documentos_exigidos = _limitar_documentos_exigidos(documentos_exigidos)
    with db_session() as conn:
        conn.execute(
            """
            UPDATE tipos_consulta
            SET nome = ?, descricao = ?, icone = ?, custo_creditos = ?,
                campo_label = ?, campo_placeholder = ?, campos_incluidos = ?, manual = ?,
                documentos_exigidos = ?, segmentos_visiveis = ?, custo_apibrasil_centavos = ?
            WHERE id = ?
            """,
            (nome, descricao, icone, custo_creditos, campo_label, campo_placeholder, campos_incluidos, int(manual), documentos_exigidos, segmentos_visiveis, custo_apibrasil_centavos, tipo_id),
        )


def _limitar_documentos_exigidos(documentos_exigidos: str) -> str:
    itens = [d.strip() for d in documentos_exigidos.split(",") if d.strip()]
    return ", ".join(itens[:MAX_DOCUMENTOS_EXIGIDOS])


def alternar_disponibilidade(tipo_id: str) -> None:
    with db_session() as conn:
        conn.execute(
            "UPDATE tipos_consulta SET disponivel = 1 - disponivel WHERE id = ?",
            (tipo_id,),
        )


def excluir_consulta_type(tipo_id: str) -> None:
    with db_session() as conn:
        conn.execute("DELETE FROM tipos_consulta WHERE id = ?", (tipo_id,))
