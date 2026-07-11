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
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
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
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
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
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users (id)
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
        "debitos-multas",
        "Débitos e Multas",
        "Consulta de multas, IPVA e débitos em aberto vinculados ao veículo.",
        "💰",
        6,
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
        0,
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


def _ensure_admin_exists(conn: sqlite3.Connection) -> None:
    has_admin = conn.execute("SELECT COUNT(*) AS n FROM users WHERE is_admin = 1").fetchone()["n"]
    if has_admin:
        return
    primeiro = conn.execute("SELECT id FROM users ORDER BY id ASC LIMIT 1").fetchone()
    if primeiro:
        conn.execute("UPDATE users SET is_admin = 1 WHERE id = ?", (primeiro["id"],))


def init_db() -> None:
    with db_session() as conn:
        conn.executescript(SCHEMA)
        _ensure_column(conn, "consultas", "tipo", "tipo TEXT NOT NULL DEFAULT 'base-nacional-v2'")
        _ensure_column(conn, "consultas", "resultado_json", "resultado_json TEXT")
        _ensure_column(conn, "users", "is_admin", "is_admin INTEGER NOT NULL DEFAULT 0")
        _seed_tipos_consulta(conn)
        _ensure_seed_row(conn, "nacional")
        _ensure_seed_row(conn, "estadual")
        _ensure_admin_exists(conn)
