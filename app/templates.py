from fastapi.templating import Jinja2Templates

from app.config_sistema import get_configuracoes

templates = Jinja2Templates(directory="templates")
templates.env.globals["get_config"] = get_configuracoes
