import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "app.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    credits INTEGER NOT NULL DEFAULT 0,
    is_admin INTEGER NOT NULL DEFAULT 0,
    is_operador INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'aprovado',
    tipo_profissional TEXT,
    cnpj_ou_carteirinha TEXT,
    documento_blob BLOB,
    documento_nome TEXT,
    documento_tipo TEXT,
    aceite_termos_em TEXT,
    motivo_rejeicao TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS configuracoes_sistema (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    nome_sistema TEXT NOT NULL DEFAULT 'DataPainel',
    logo_login_blob BLOB,
    logo_login_tipo TEXT,
    favicon_blob BLOB,
    favicon_tipo TEXT
);

CREATE TABLE IF NOT EXISTS tipos_consulta (
    id TEXT PRIMARY KEY,
    nome TEXT NOT NULL,
    descricao TEXT NOT NULL DEFAULT '',
    icone TEXT NOT NULL DEFAULT '🔍',
    custo_creditos INTEGER NOT NULL DEFAULT 1,
    campo_label TEXT NOT NULL DEFAULT 'Placa',
    campo_placeholder TEXT NOT NULL DEFAULT 'Ex: ABC1234',
    disponivel INTEGER NOT NULL DEFAULT 1,
    campos_incluidos TEXT NOT NULL DEFAULT '',
    manual INTEGER NOT NULL DEFAULT 0,
    documentos_exigidos TEXT NOT NULL DEFAULT '',
    segmentos_visiveis TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS consulta_documentos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    consulta_id INTEGER NOT NULL,
    nome_documento TEXT NOT NULL,
    arquivo_nome TEXT NOT NULL,
    arquivo_tipo TEXT,
    arquivo_blob BLOB NOT NULL,
    tamanho_original INTEGER,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (consulta_id) REFERENCES consultas (id)
);

CREATE TABLE IF NOT EXISTS precos_segmento (
    tipo_profissional TEXT NOT NULL,
    tipo_consulta_id TEXT NOT NULL,
    custo_creditos INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (tipo_profissional, tipo_consulta_id),
    FOREIGN KEY (tipo_consulta_id) REFERENCES tipos_consulta (id)
);

CREATE TABLE IF NOT EXISTS precos_clientes (
    user_id INTEGER NOT NULL,
    tipo_consulta_id TEXT NOT NULL,
    custo_creditos INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (user_id, tipo_consulta_id),
    FOREIGN KEY (user_id) REFERENCES users (id),
    FOREIGN KEY (tipo_consulta_id) REFERENCES tipos_consulta (id)
);

CREATE TABLE IF NOT EXISTS mensagens_chat (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cliente_id INTEGER NOT NULL,
    autor_id INTEGER NOT NULL,
    autor_tipo TEXT NOT NULL,
    mensagem TEXT NOT NULL,
    lida_pelo_cliente INTEGER NOT NULL DEFAULT 0,
    lida_pelo_operador INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (cliente_id) REFERENCES users (id),
    FOREIGN KEY (autor_id) REFERENCES users (id)
);

CREATE TABLE IF NOT EXISTS ajustes_creditos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    admin_id INTEGER NOT NULL,
    valor INTEGER NOT NULL,
    motivo TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users (id),
    FOREIGN KEY (admin_id) REFERENCES users (id)
);

CREATE TABLE IF NOT EXISTS pagamentos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    pacote_id TEXT NOT NULL,
    creditos INTEGER NOT NULL,
    valor_centavos INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'pendente',
    mp_preference_id TEXT,
    mp_payment_id TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users (id)
);

CREATE TABLE IF NOT EXISTS consultas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    tipo TEXT NOT NULL DEFAULT 'base-nacional-v2',
    placa TEXT NOT NULL,
    custo_creditos INTEGER NOT NULL,
    status TEXT NOT NULL,
    resultado_resumo TEXT,
    resultado_json TEXT,
    erro_mensagem TEXT,
    operador_id INTEGER,
    atendido_em TEXT,
    concluido_em TEXT,
    anexo_blob BLOB,
    anexo_nome TEXT,
    anexo_tipo TEXT,
    anexo_tamanho_original INTEGER,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users (id),
    FOREIGN KEY (operador_id) REFERENCES users (id)
);
"""


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def db_session():
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
    existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
    if column not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")


SEED_TIPOS_CONSULTA = [
    (
        "base-nacional-v2",
        "Base Nacional V2",
        "Dados completos do veículo, restrições e histórico junto à base nacional.",
        "🚗",
        5,
        "Placa",
        "Ex: ABC1234",
        1,
    ),
    (
        "nacional",
        "Base Nacional",
        "Veículo, restrições, comunicação de venda e gravame comercial (financiamento).",
        "📋",
        5,
        "Placa",
        "Ex: ABC1234",
        1,
    ),
    (
        "estadual",
        "Base Estadual",
        "Dados do veículo junto à base estadual de trânsito.",
        "🏛️",
        5,
        "Placa",
        "Ex: ABC1234",
        1,
    ),
    (
        "gravame",
        "Gravame",
        "Consulta de gravame (financiamento/alienação) vinculado à placa.",
        "🔒",
        5,
        "Placa",
        "Ex: ABC1234",
        1,
    ),
    (
        "analitico-veicular",
        "Analítico Veicular",
        "Relatório completo: FIPE, proprietário atual, histórico de KM, RENAJUD, RENAINF, roubo/furto e recall.",
        "🧾",
        8,
        "Placa",
        "Ex: ABC1234",
        1,
    ),
    (
        "relatorio-veicular",
        "Veicular Relatório",
        "Relatório em PDF com dados do veículo, FIPE e proprietário atual, com identidade visual personalizável.",
        "📄",
        7,
        "Placa",
        "Ex: ABC1234",
        1,
    ),
    (
        "veicular-agrupados",
        "Veicular Agrupados",
        "Consulta combinada: agregados própria, FIPE e proprietário atual em uma única chamada.",
        "📦",
        6,
        "Placa",
        "Ex: ABC1234",
        1,
    ),
    (
        "agregados-propria",
        "Agregados Própria",
        "Consulta de veículos agregados à frota própria vinculados à placa.",
        "🚚",
        1,
        "Placa",
        "Ex: ABC1234",
        1,
    ),
    (
        "score-veicular",
        "Score Veicular",
        "Pontuação de risco do veículo com base em histórico de sinistros.",
        "📊",
        4,
        "Placa",
        "Ex: ABC1234",
        0,
    ),
    (
        "leilao",
        "Histórico de Leilão",
        "Verifica se o veículo já passou por leilão e detalhes do lote.",
        "🔨",
        4,
        "Placa",
        "Ex: ABC1234",
        1,
    ),
    (
        "debitos-v4",
        "Débitos e Multas",
        "Consulta de IPVA, licenciamento, multas e outros débitos em aberto vinculados à placa.",
        "💰",
        6,
        "Placa",
        "Ex: ABC1234",
        1,
    ),
]


def _seed_tipos_consulta(conn: sqlite3.Connection) -> None:
    total = conn.execute("SELECT COUNT(*) AS n FROM tipos_consulta").fetchone()["n"]
    if total > 0:
        return
    conn.executemany(
        """
        INSERT INTO tipos_consulta
            (id, nome, descricao, icone, custo_creditos, campo_label, campo_placeholder, disponivel)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        SEED_TIPOS_CONSULTA,
    )


def _ensure_seed_row(conn: sqlite3.Connection, tipo_id: str) -> None:
    existe = conn.execute("SELECT 1 FROM tipos_consulta WHERE id = ?", (tipo_id,)).fetchone()
    if existe:
        return
    row = next((t for t in SEED_TIPOS_CONSULTA if t[0] == tipo_id), None)
    if row:
        conn.execute(
            """
            INSERT INTO tipos_consulta
                (id, nome, descricao, icone, custo_creditos, campo_label, campo_placeholder, disponivel)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            row,
        )


def _ensure_tipo_ativo(conn: sqlite3.Connection, tipo_id: str) -> None:
    conn.execute("UPDATE tipos_consulta SET disponivel = 1 WHERE id = ?", (tipo_id,))


def _ensure_tipo_manual(conn: sqlite3.Connection, tipo_id: str) -> None:
    conn.execute(
        "UPDATE tipos_consulta SET disponivel = 1, manual = 1 WHERE id = ?", (tipo_id,)
    )


def _ensure_debitos_v4_migrado(conn: sqlite3.Connection) -> None:
    tem_novo = conn.execute("SELECT 1 FROM tipos_consulta WHERE id = 'debitos-v4'").fetchone()
    if tem_novo:
        return
    tem_antigo = conn.execute("SELECT 1 FROM tipos_consulta WHERE id = 'debitos-multas'").fetchone()
    if tem_antigo:
        conn.execute(
            "UPDATE tipos_consulta SET id = 'debitos-v4', disponivel = 1 WHERE id = 'debitos-multas'"
        )
    else:
        _ensure_seed_row(conn, "debitos-v4")


CAMPOS_INCLUIDOS = {
    "base-nacional-v2": "Dados do veículo\nMarca, modelo, ano, cor, chassi, motor, renavam\nRestrições (roubo/furto, judicial, tributária)\nSituação e município",
    "nacional": "Dados do veículo e proprietário\nRestrições gerais e RENAJUD\nComunicação de venda\nGravame comercial (financiadora, contrato, tipo de transação)",
    "estadual": "Dados do veículo (base estadual)\nProprietário\nRestrições (DPVAT, geral, roubo/furto, RENAJUD)",
    "gravame": "Financiadora e nº do contrato\nStatus de alienação fiduciária\nNome do financiado\nHistórico de movimentações do gravame",
    "analitico-veicular": "Relatório em PDF pronto\nFIPE\nProprietário atual\nHistórico de KM\nRENAJUD e RENAINF\nRoubo/furto\nRecall",
    "relatorio-veicular": "Relatório em PDF com identidade visual personalizável\nDados do veículo\nFIPE\nProprietário atual",
    "veicular-agrupados": "Dados do veículo (agregados própria)\nTabela FIPE com histórico de preços\nProprietário atual",
    "agregados-propria": "Placa, chassi, marca/modelo, versão\nAno fabricação/modelo\nCor, combustível, motor\nUF e cidade de emplacamento",
    "leilao": "Análise de risco do veículo\nDados básicos do veículo\nHistórico de registros de leilão (comitente, data, condição)",
    "debitos-v4": "IPVA em aberto\nLicenciamento em aberto\nMultas detalhadas (data, local, valor, artigo, pontos)\nOutros débitos e restrições",
    "score-veicular": "Pontuação de risco do veículo\nParecer elaborado por um operador\nDocumento anexo (quando aplicável)",
}


def _ensure_campos_incluidos(conn: sqlite3.Connection) -> None:
    for tipo_id, campos in CAMPOS_INCLUIDOS.items():
        atual = conn.execute(
            "SELECT campos_incluidos FROM tipos_consulta WHERE id = ?", (tipo_id,)
        ).fetchone()
        if atual is not None and not atual["campos_incluidos"]:
            conn.execute(
                "UPDATE tipos_consulta SET campos_incluidos = ? WHERE id = ?",
                (campos, tipo_id),
            )


def _ensure_admin_exists(conn: sqlite3.Connection) -> None:
    has_admin = conn.execute("SELECT COUNT(*) AS n FROM users WHERE is_admin = 1").fetchone()["n"]
    if has_admin:
        return
    primeiro = conn.execute("SELECT id FROM users ORDER BY id ASC LIMIT 1").fetchone()
    if primeiro:
        conn.execute(
            "UPDATE users SET is_admin = 1, status = 'aprovado' WHERE id = ?", (primeiro["id"],)
        )


def _ensure_configuracoes(conn: sqlite3.Connection) -> None:
    existe = conn.execute("SELECT 1 FROM configuracoes_sistema WHERE id = 1").fetchone()
    if not existe:
        conn.execute(
            "INSERT INTO configuracoes_sistema (id, nome_sistema) VALUES (1, 'DataPainel')"
        )


def init_db() -> None:
    with db_session() as conn:
        conn.executescript(SCHEMA)
        _ensure_column(conn, "consultas", "tipo", "tipo TEXT NOT NULL DEFAULT 'base-nacional-v2'")
        _ensure_column(conn, "consultas", "resultado_json", "resultado_json TEXT")
        _ensure_column(conn, "consultas", "operador_id", "operador_id INTEGER")
        _ensure_column(conn, "consultas", "atendido_em", "atendido_em TEXT")
        _ensure_column(conn, "consultas", "concluido_em", "concluido_em TEXT")
        _ensure_column(conn, "consultas", "anexo_blob", "anexo_blob BLOB")
        _ensure_column(conn, "consultas", "anexo_nome", "anexo_nome TEXT")
        _ensure_column(conn, "consultas", "anexo_tipo", "anexo_tipo TEXT")
        _ensure_column(conn, "consultas", "anexo_tamanho_original", "anexo_tamanho_original INTEGER")
        _ensure_column(conn, "users", "is_admin", "is_admin INTEGER NOT NULL DEFAULT 0")
        _ensure_column(conn, "users", "is_operador", "is_operador INTEGER NOT NULL DEFAULT 0")
        _ensure_column(conn, "users", "status", "status TEXT NOT NULL DEFAULT 'aprovado'")
        _ensure_column(conn, "users", "tipo_profissional", "tipo_profissional TEXT")
        _ensure_column(conn, "users", "cnpj_ou_carteirinha", "cnpj_ou_carteirinha TEXT")
        _ensure_column(conn, "users", "documento_blob", "documento_blob BLOB")
        _ensure_column(conn, "users", "documento_nome", "documento_nome TEXT")
        _ensure_column(conn, "users", "documento_tipo", "documento_tipo TEXT")
        _ensure_column(conn, "users", "aceite_termos_em", "aceite_termos_em TEXT")
        _ensure_column(conn, "users", "motivo_rejeicao", "motivo_rejeicao TEXT")
        _ensure_column(conn, "tipos_consulta", "campos_incluidos", "campos_incluidos TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "tipos_consulta", "manual", "manual INTEGER NOT NULL DEFAULT 0")
        _ensure_column(conn, "tipos_consulta", "documentos_exigidos", "documentos_exigidos TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "tipos_consulta", "segmentos_visiveis", "segmentos_visiveis TEXT NOT NULL DEFAULT ''")
        _seed_tipos_consulta(conn)
        _ensure_configuracoes(conn)
        _ensure_seed_row(conn, "nacional")
        _ensure_seed_row(conn, "estadual")
        _ensure_seed_row(conn, "gravame")
        _ensure_seed_row(conn, "analitico-veicular")
        _ensure_seed_row(conn, "veicular-agrupados")
        _ensure_seed_row(conn, "relatorio-veicular")
        _ensure_tipo_ativo(conn, "leilao")
        _ensure_debitos_v4_migrado(conn)
        _ensure_tipo_manual(conn, "score-veicular")
        _ensure_campos_incluidos(conn)
        _ensure_admin_exists(conn)
