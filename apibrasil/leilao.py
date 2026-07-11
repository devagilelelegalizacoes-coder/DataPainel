from __future__ import annotations

from typing import Optional, TypedDict

import requests

from apibrasil.base_nacional_v2 import APIBrasilConfig, APIBrasilError, APIBrasilTimeoutError


class LeilaoPayload(TypedDict):
    tipo: str
    placa: str
    homolog: bool


class LeilaoResponse(TypedDict, total=False):
    status: bool
    message: str
    dados: dict


class LeilaoService:
    ENDPOINT = "/consulta/veiculos/credits"

    def __init__(
        self,
        config: APIBrasilConfig,
        http_client: Optional[requests.Session] = None,
    ) -> None:
        self._config = config
        self._http = http_client or requests.Session()

    def consultar_placa(self, placa: str, homolog: bool = False) -> LeilaoResponse:
        payload: LeilaoPayload = {
            "tipo": "leilao",
            "placa": placa,
            "homolog": homolog,
        }
        url = f"{self._config.base_url}{self.ENDPOINT}"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._config.bearer_token}",
        }

        try:
            response = self._http.post(
                url,
                json=payload,
                headers=headers,
                timeout=self._config.timeout,
            )
        except requests.Timeout as exc:
            raise APIBrasilTimeoutError(
                "Timeout ao consultar Leilão", status_code=408
            ) from exc
        except requests.RequestException as exc:
            raise APIBrasilError(
                f"Falha de conexão com APIBrasil: {exc}", status_code=0
            ) from exc

        return self._handle_response(response)

    @staticmethod
    def _handle_response(response: requests.Response) -> LeilaoResponse:
        try:
            body = response.json()
        except ValueError:
            body = {}

        if not response.ok:
            message = body.get("message") or response.reason or "Erro desconhecido"
            error_code = body.get("error") or body.get("error_code")
            raise APIBrasilError(message, status_code=response.status_code, error_code=error_code)

        return body
