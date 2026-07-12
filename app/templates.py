from fastapi.templating import Jinja2Templates

from app.chat import contar_conversas_nao_lidas, contar_nao_lidas_cliente
from app.config_sistema import get_configuracoes

templates = Jinja2Templates(directory="templates")
templates.env.globals["get_config"] = get_configuracoes


def get_chat_nao_lidas(user: dict) -> int:
    if user["is_operador"] or user["is_admin"]:
        return contar_conversas_nao_lidas()
    return contar_nao_lidas_cliente(user["id"])


templates.env.globals["get_chat_nao_lidas"] = get_chat_nao_lidas
