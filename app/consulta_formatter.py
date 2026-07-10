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


def montar_view(resultado: dict | None) -> ConsultaView:
    if not resultado:
        return ConsultaView(campos_principais=[], secoes=[])

    dados = resultado.get("data", resultado) if isinstance(resultado, dict) else {}
    if not isinstance(dados, dict):
        return ConsultaView(campos_principais=[], secoes=[])

    campos_principais: list[tuple[str, str]] = []
    secoes: list[Secao] = []

    for chave, valor in dados.items():
        if _valor_vazio(valor):
            continue

        if isinstance(valor, dict):
            sub_campos = [
                (humanizar_chave(k), str(v))
                for k, v in valor.items()
                if not _valor_vazio(v) and not isinstance(v, (dict, list))
            ]
            if sub_campos:
                secoes.append(Secao(titulo=humanizar_chave(chave), campos=sub_campos))
        elif isinstance(valor, list):
            itens = [str(v) for v in valor if not _valor_vazio(v)]
            if itens:
                secoes.append(Secao(titulo=humanizar_chave(chave), itens=itens))
        else:
            campos_principais.append((humanizar_chave(chave), str(valor)))

    return ConsultaView(campos_principais=campos_principais, secoes=secoes)
