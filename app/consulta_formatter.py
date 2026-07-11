import re
from dataclasses import dataclass, field


def humanizar_chave(chave: str) -> str:
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", chave)
    s = s.replace("_", " ")
    return s.strip().title()


@dataclass
class Secao:
    titulo: str
    campos: list[tuple[str, str]] = field(default_factory=list)
    itens: list[str] = field(default_factory=list)


@dataclass
class ConsultaView:
    campos_principais: list[tuple[str, str]]
    secoes: list[Secao]


def _valor_vazio(valor) -> bool:
    return valor is None or valor == "" or valor == {} or valor == []


def _percorrer(
    dados: dict,
    secoes: list[Secao],
    campos_principais: list[tuple[str, str]],
    topo: bool,
    prefixo: str,
) -> None:
    campos_aqui: list[tuple[str, str]] = []

    for chave, valor in dados.items():
        if _valor_vazio(valor):
            continue

        label = humanizar_chave(chave)

        if isinstance(valor, dict):
            novo_prefixo = label if not prefixo else f"{prefixo} · {label}"
            _percorrer(valor, secoes, campos_principais, topo=False, prefixo=novo_prefixo)
        elif isinstance(valor, list):
            itens = [str(v) for v in valor if not _valor_vazio(v)]
            if itens:
                titulo = label if not prefixo else f"{prefixo} · {label}"
                secoes.append(Secao(titulo=titulo, itens=itens))
        else:
            campos_aqui.append((label, str(valor)))

    if campos_aqui:
        if topo:
            campos_principais.extend(campos_aqui)
        else:
            secoes.append(Secao(titulo=prefixo or "Detalhes", campos=campos_aqui))


def montar_view(resultado: dict | None) -> ConsultaView:
    if not resultado:
        return ConsultaView(campos_principais=[], secoes=[])

    dados = resultado.get("data", resultado) if isinstance(resultado, dict) else {}
    if not isinstance(dados, dict):
        return ConsultaView(campos_principais=[], secoes=[])

    campos_principais: list[tuple[str, str]] = []
    secoes: list[Secao] = []
    _percorrer(dados, secoes, campos_principais, topo=True, prefixo="")

    return ConsultaView(campos_principais=campos_principais, secoes=secoes)
