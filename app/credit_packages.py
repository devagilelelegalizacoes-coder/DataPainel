from dataclasses import dataclass


@dataclass(frozen=True)
class PacoteCredito:
    id: str
    nome: str
    creditos: int
    valor_centavos: int

    @property
    def valor_reais(self) -> float:
        return self.valor_centavos / 100


PACOTES_CREDITO: dict[str, PacoteCredito] = {
    "p10": PacoteCredito(id="p10", nome="Pacote Inicial", creditos=10, valor_centavos=1000),
    "p50": PacoteCredito(id="p50", nome="Pacote Padrão", creditos=50, valor_centavos=4500),
    "p100": PacoteCredito(id="p100", nome="Pacote Profissional", creditos=100, valor_centavos=8000),
    "p500": PacoteCredito(id="p500", nome="Pacote Avançado", creditos=500, valor_centavos=35000),
}


def get_pacote(pacote_id: str) -> PacoteCredito | None:
    return PACOTES_CREDITO.get(pacote_id)


def listar_pacotes() -> list[PacoteCredito]:
    return list(PACOTES_CREDITO.values())
