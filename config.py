from pathlib import Path

# Raíz del proyecto (donde está este fichero)
ROOT = Path(__file__).parent

# Rutas de datos y prompts
STATS_PATH = ROOT / "data" / "stats.json"
RESUMEN_PATH = ROOT / "data" / "resumen.txt"
NARRADOR_PROMPT_PATH = ROOT / "prompts" / "narrador.txt"
COMBATE_PROMPT_PATH = ROOT / "prompts" / "combate.txt"
DIRECTOR_PROMPT_PATH = ROOT / "prompts" / "director.txt"
CAMPAIGN_PATH = ROOT / "data" / "campaign.json"

# Configuración del modelo
MODEL_NAME = "gpt-4o"
TEMPERATURE_NARRADOR = 0.9
TEMPERATURE_LOGICA = 0.0

# Umbrales de combate
UMBRAL_ATAQUE = 12
UMBRAL_HUIDA = 10
