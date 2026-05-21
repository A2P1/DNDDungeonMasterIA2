from pathlib import Path # Para construir rutas de forma cómoda sin hardcodear separadores

ROOT = Path(__file__).parent # La raíz del proyecto es la carpeta donde está este archivo

# Rutas a los archivos de datos que se van generando durante la partida
STATS_PATH = ROOT / "data" / "stats.json" # Ficha del jugador
RESUMEN_PATH = ROOT / "data" / "resumen.txt" # Resumen narrativo acumulado de la partida
CAMPAIGN_PATH = ROOT / "data" / "campaign.json" # La campaña generada por el director
ENTIDADES_PATH = ROOT / "data" / "entidades.json" # Fichas de enemigos y NPCs generadas por el enriquecedor
DIARIO_PATH = ROOT / "data" / "diario.json" # Memoria estructurada del narrador a largo plazo

# Rutas a los prompts de cada agente (se leen al arrancar cada agente)
NARRADOR_PROMPT_PATH = ROOT / "prompts" / "narrador.txt"
COMBATE_PROMPT_PATH = ROOT / "prompts" / "combate.txt"
DIRECTOR_PROMPT_PATH = ROOT / "prompts" / "director.txt"
ENRIQUECEDOR_PROMPT_PATH = ROOT / "prompts" / "enriquecedor.txt"
CREADOR_PERSONAJE_PROMPT_PATH = ROOT / "prompts" / "creador_personaje.txt"
SECRETARIO_PROMPT_PATH = ROOT / "prompts" / "secretario.txt"

# Modelo global por defecto (fallback si algún agente no especifica)
MODEL_NAME = "gpt-4o"

# Modelos por agente. Cambia uno solo sin tocar el resto. FIX-15.
NARRADOR_MODEL = "gpt-5" # Visible al jugador, calidad alta de prosa + tool calling
COMBATE_MODEL = "gpt-4o" # Narrador de combate: prosa visceral + reglas
EVALUADOR_COMBATE_MODEL = "gpt-4o" # Structured output: viabilidad/DC/dado_daño
DECISOR_NPC_MODEL = "gpt-4o" # FIX-13: decisiones de NPC con personalidad
DETECTOR_MODEL = "gpt-4o-mini" # FIX-11: detección de ataque (lógica simple, alto volumen)
SECRETARIO_MODEL = "gpt-4o-mini" # Extracción de diario por turno (alta frecuencia)
DIRECTOR_MODEL = "gpt-4o" # Genera la campaña entera (una sola llamada al inicio)
ENRIQUECEDOR_MODEL = "gpt-4o-mini" # Fichas de entidades (structured output)
CREADOR_PERSONAJE_MODEL = "gpt-4o-mini" # Crear personaje, una sola vez

# Temperaturas: alta para creatividad, baja para lógica y coherencia
TEMPERATURE_NARRADOR = 0.7 # Equilibrio: creativo pero menos verboso/decorativo que con 0.9
TEMPERATURE_LOGICA = 0.0 # Cero para detectores y decisiones lógicas (sin inventarse cosas)
TEMPERATURE_ENRIQUECEDOR = 0.3 # Media-baja para fichas coherentes pero con algo de variedad

# Umbrales de dificultad para las tiradas de combate
UMBRAL_ATAQUE = 12 # El jugador necesita sacar 12+ en d20 para acertar
UMBRAL_HUIDA = 10 # El jugador necesita sacar 10+ en d20 para huir con éxito
