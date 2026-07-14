from __future__ import annotations

import os
from dataclasses import dataclass

import mercadopago

from app.credit_packages import PacoteCredito
from app.database import db_session


class PagamentoError(Exception):
    pass


@dataclass(frozen=True)
class MercadoPagoConfig:
    access_token: str
    app_base_url: str

    @classmethod
    def from_env(cls) -> "MercadoPagoConfig":
        token = os.getenv("MERCADOPAGO_ACCESS_TOKEN")
        if not token:
            raise RuntimeError("MERCADOPAGO_ACCESS_TOKEN não configurado no ambiente (.env)")
        base_url = os.getenv("APP_BASE_URL", "http://127.0.0.1:8000")
        return cls(access_token=token, app_base_url=base_url.rstrip("/"))


class PagamentoService:
    def __init__(self, config: MercadoPagoConfig) -> None:
        self._config = config
        self._sdk = mercadopago.SDK(config.access_token)

    def criar_preferencia(self, pagamento_id: int, pacote: PacoteCredito, user_email: str) -> str:
        preference_data = {
            "items": [
                {
                    "title": f"{pacote.nome} - {pacote.creditos} créditos APIBrasil",
                    "quantity": 1,
                    "unit_price": pacote.valor_reais,
                    "currency_id": "BRL",
                }
            ],
            "payer": {"email": user_email},
            "external_reference": str(pagamento_id),
            "back_urls": {
                "success": f"{self._config.app_base_url}/creditos/retorno",
                "failure": f"{self._config.app_base_url}/creditos/retorno",
                "pending": f"{self._config.app_base_url}/creditos/retorno",
            },
        }

        if self._config.app_base_url.startswith("https://"):
            preference_data["auto_return"] = "approved"
            preference_data["notification_url"] = f"{self._config.app_base_url}/creditos/webhook"

        resultado = self._sdk.preference().create(preference_data)
        if resultado.get("status") not in (200, 201):
            raise PagamentoError(f"Falha ao criar preferência de pagamento: {resultado}")

        response = resultado["response"]
        atualizar_preference_id(pagamento_id, response["id"])
        return response["init_point"]

    def consultar_pagamento(self, mp_payment_id: str) -> dict:
        resultado = self._sdk.payment().get(mp_payment_id)
        if resultado.get("status") != 200:
            raise PagamentoError(f"Falha ao consultar pagamento: {resultado}")
        return resultado["response"]


def registrar_pagamento_pendente(user_id: int, pacote: PacoteCredito) -> int:
    with db_session() as conn:
        cursor = conn.execute(
            """
            INSERT INTO pagamentos (user_id, pacote_id, creditos, valor_centavos, status)
            VALUES (?, ?, ?, ?, 'pendente')
            """,
            (user_id, pacote.id, pacote.creditos, pacote.valor_centavos),
        )
        return cursor.lastrowid


def atualizar_preference_id(pagamento_id: int, preference_id: str) -> None:
    with db_session() as conn:
        conn.execute(
            "UPDATE pagamentos SET mp_preference_id = ? WHERE id = ?",
            (preference_id, pagamento_id),
        )


def get_pagamento(pagamento_id: int) -> dict | None:
    with db_session() as conn:
        row = conn.execute("SELECT * FROM pagamentos WHERE id = ?", (pagamento_id,)).fetchone()
        return dict(row) if row else None


def listar_pagamentos(user_id: int, limit: int = 20) -> list[dict]:
    with db_session() as conn:
        rows = conn.execute(
            """
            SELECT * FROM pagamentos
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()
        return [dict(row) for row in rows]


def confirmar_pagamento_aprovado(pagamento_id: int, mp_payment_id: str) -> bool:
    """Credita o usuário e marca o pagamento como aprovado. Idempotente: retorna False se já processado."""
    with db_session() as conn:
        pagamento = conn.execute("SELECT * FROM pagamentos WHERE id = ?", (pagamento_id,)).fetchone()
        if pagamento is None or pagamento["status"] == "aprovado":
            return False

        conn.execute(
            "UPDATE pagamentos SET status = 'aprovado', mp_payment_id = ? WHERE id = ?",
            (mp_payment_id, pagamento_id),
        )
        conn.execute(
            "UPDATE users SET credits = credits + ? WHERE id = ?",
            (pagamento["creditos"], pagamento["user_id"]),
        )
        return True


def marcar_pagamento_status(pagamento_id: int, status: str, mp_payment_id: str | None = None) -> None:
    with db_session() as conn:
        conn.execute(
            "UPDATE pagamentos SET status = ?, mp_payment_id = COALESCE(?, mp_payment_id) WHERE id = ?",
            (status, mp_payment_id, pagamento_id),
        )
