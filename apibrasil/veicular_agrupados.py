from __future__ import annotations

from typing import Optional, TypedDict

import requests

from apibrasil.base_nacional_v2 import APIBrasilConfig, APIBrasilError, APIBrasilTimeoutError

VeicularAgrupadosOpcoes = TypedDict(
    "VeicularAgrupadosOpcoes",
    {
        "agregados-propria": bool,
        "fipe": bool,
        "proprietario-atual": bool,
    },
    total=False,
)


class VeicularAgrupadosPayload(TypedDict, total=False):
    tipo: str
    placa: str
    homolog: bool
    agrupados: VeicularAgrupadosOpcoes


class VeicularAgrupadosResponse(TypedDict, total=False):
    status: bool
    message: str
    dados: dict


DEFAULT_AGRUPADOS: VeicularAgrupadosOpcoes = {
    "agregados-propria": True,
    "fipe": True,
    "proprietario-atual": True,
}


class VeicularAgrupadosService:
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
        agrupados: Optional[VeicularAgrupadosOpcoes] = None,
    ) -> VeicularAgrupadosResponse:
        payload: VeicularAgrupadosPayload = {
            "tipo": "veicular-agrupados",
            "placa": placa,
            "homolog": homolog,
            "agrupados": agrupados if agrupados is not None else DEFAULT_AGRUPADOS,
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
                "Timeout ao consultar Veicular Agrupados", status_code=408
            ) from exc
        except requests.RequestException as exc:
            raise APIBrasilError(
                f"Falha de conexão com APIBrasil: {exc}", status_code=0
            ) from exc

        return self._handle_response(response)

    @staticmethod
    def _handle_response(response: requests.Response) -> VeicularAgrupadosResponse:
        try:
            body = response.json()
        except ValueError:
            body = {}

        if not response.ok:
            message = body.get("message") or response.reason or "Erro desconhecido"
            error_code = body.get("error") or body.get("error_code")
            raise APIBrasilError(message, status_code=response.status_code, error_code=error_code)

        if "data" not in body and "veicular-agrupados" in body:
            body["data"] = body.pop("veicular-agrupados")

        return body
