from __future__ import annotations

from typing import Optional, TypedDict

import requests

from apibrasil.base_nacional_v2 import APIBrasilConfig, APIBrasilError, APIBrasilTimeoutError

AnaliticoVeicularExtra = TypedDict(
    "AnaliticoVeicularExtra",
    {
        "fipe": bool,
        "proprietario-atual": bool,
        "historico-km": bool,
        "renajud": bool,
        "renainf": bool,
        "roubo-furto": bool,
        "recall": bool,
    },
    total=False,
)

AnaliticoVeicularWhitelabel = TypedDict(
    "AnaliticoVeicularWhitelabel",
    {
        "empresa": str,
        "logo": str,
        "font-size": str,
        "font-color": str,
        "header-color": str,
        "font-header-color": str,
    },
    total=False,
)


class AnaliticoVeicularPayload(TypedDict, total=False):
    tipo: str
    placa: str
    homolog: bool
    extra: AnaliticoVeicularExtra
    whitelabel: AnaliticoVeicularWhitelabel


class AnaliticoVeicularResponse(TypedDict, total=False):
    status: bool
    message: str
    dados: dict


DEFAULT_EXTRA: AnaliticoVeicularExtra = {
    "fipe": True,
    "proprietario-atual": True,
    "historico-km": True,
    "renajud": True,
    "renainf": True,
    "roubo-furto": True,
    "recall": True,
}

DEFAULT_WHITELABEL: AnaliticoVeicularWhitelabel = {
    "empresa": "DataPainel",
    "logo": "",
    "font-size": "14px",
    "font-color": "#0F172A",
    "header-color": "#000000",
    "font-header-color": "#FFFFFF",
}


class AnaliticoVeicularService:
    ENDPOINT = "/consulta/veiculos/credits"

    def __init__(
        self,
        config: APIBrasilConfig,
        http_client: Optional[requests.Session] = None,
    ) -> None:
        self._config = config
        self._http = http_client or requests.Session()

    def consultar_placa(
        self,
        placa: str,
        homolog: bool = False,
        extra: Optional[AnaliticoVeicularExtra] = None,
        whitelabel: Optional[AnaliticoVeicularWhitelabel] = None,
    ) -> AnaliticoVeicularResponse:
        payload: AnaliticoVeicularPayload = {
            "tipo": "analitico-veicular",
            "placa": placa,
            "homolog": homolog,
            "extra": extra if extra is not None else DEFAULT_EXTRA,
            "whitelabel": whitelabel if whitelabel is not None else DEFAULT_WHITELABEL,
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
                "Timeout ao consultar Analítico Veicular", status_code=408
            ) from exc
        except requests.RequestException as exc:
            raise APIBrasilError(
                f"Falha de conexão com APIBrasil: {exc}", status_code=0
            ) from exc

        return self._handle_response(response)

    @staticmethod
    def _handle_response(response: requests.Response) -> AnaliticoVeicularResponse:
        try:
            body = response.json()
        except ValueError:
            body = {}

        if not response.ok:
            message = body.get("message") or response.reason or "Erro desconhecido"
            error_code = body.get("error") or body.get("error_code")
            raise APIBrasilError(message, status_code=response.status_code, error_code=error_code)

        return body
