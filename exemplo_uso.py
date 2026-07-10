from dotenv import load_dotenv

from apibrasil.base_nacional_v2 import (
    APIBrasilConfig,
    APIBrasilError,
    BaseNacionalV2Service,
)

load_dotenv()

config = APIBrasilConfig.from_env()
service = BaseNacionalV2Service(config)

try:
    resultado = service.consultar_placa(placa="ABC1234", homolog=False)
    print(resultado)
except APIBrasilError as erro:
    print(f"Erro ao consultar placa: {erro.message} (status={erro.status_code}, code={erro.error_code})")
