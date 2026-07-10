from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional, TypedDict

import requests


class BaseNacionalV2Payload(TypedDict):
    tipo: str
    placa: str
    homolog: bool


class BaseNacionalV2Response(TypedDict, total=False):
    status: bool
    message: str
    dados: dict


class APIBrasilError(Exception):
    def __init__(self, message: str, status_code: int, error_code: Optional[str] = None) -> None:
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        super().__init__(f"[{status_code}] {message}")


class APIBrasilTimeoutError(APIBrasilError):
    pass


@dataclass(frozen=True)
class APIBrasilConfig:
    bearer_token: str
    base_url: str = "https://gateway.apibrasil.io/api/v2"
    timeout: int = 30

    @classmethod
    def from_env(cls) -> "APIBrasilConfig":
        token = os.getenv("APIBRASIL_BEARER_TOKEN")
        if not token:
            raise RuntimeError("APIBRASIL_BEARER_TOKEN não configurado no ambiente (.env)")
        base_url = os.getenv("APIBRASIL_BASE_URL", cls.base_url)
        timeout = int(os.getenv("APIBRASIL_TIMEOUT", cls.timeout))
        return cls(bearer_token=token, base_url=base_url, timeout=timeout)


class BaseNacionalV2Service:
    ENDPOINT = "/consulta/veiculos/credits"

    def __init__(
        self,
        config: APIBrasilConfig,
        http_client: Optional[requests.Session] = None,
    ) -> None:
        self._config = config
        self._http = http_client or requests.Session()

    def consultar_placa(self, placa: str, homolog: bool = False) -> BaseNacionalV2Response:
        payload: BaseNacionalV2Payload = {
            "tipo": "base-nacional-v2",
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
                "Timeout ao consultar Base Nacional V2", status_code=408
            ) from exc
        except requests.RequestException as exc:
            raise APIBrasilError(
                f"Falha de conexão com APIBrasil: {exc}", status_code=0
            ) from exc

        return self._handle_response(response)

    @staticmethod
    def _handle_response(response: requests.Response) -> BaseNacionalV2Response:
        try:
            body = response.json()
        except ValueError:
            body = {}

        if not response.ok:
            message = body.get("message") or response.reason or "Erro desconhecido"
            error_code = body.get("error") or body.get("error_code")
            raise APIBrasilError(message, status_code=response.status_code, error_code=error_code)

        return body
