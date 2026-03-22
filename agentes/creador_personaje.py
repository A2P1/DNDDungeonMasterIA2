import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.output_parsers import JsonOutputParser
from config import STATS_PATH, MODEL_NAME

load_dotenv()

_llm = ChatOpenAI(model=MODEL_NAME, temperature=0.3)
_parser = JsonOutputParser()

_PROMPT = """Eres un generador de fichas de personaje para un juego de rol estilo D&D.
El jugador ha descrito su personaje con sus propias palabras. Tu tarea es generar una ficha
de estadísticas coherente con esa descripción.

Usa la escala de atributos 0-5 donde:
  0 = muy bajo, 2 = promedio, 3 = bueno, 4 = muy bueno, 5 = excepcional

Clases y sus puntos fuertes típicos:
- Guerrero/Bárbaro: fue alto (4-5), con alto, des medio
- Ladrón/Pícaro: des alto (4-5), car medio, fue bajo-medio
- Mago/Hechicero: int alto (4-5), sab alto, fue bajo
- Clérigo/Druida: sab alto (4-5), con medio, fue medio
- Bardo: car alto (4-5), des medio, int medio
- Paladín: fue alto (3-4), car alto, con alto

Responde SOLO con JSON válido, sin texto extra, con esta estructura exacta:
{
  "nombre": "<nombre del personaje>",
  "clase": "<clase principal en una palabra>",
  "raza": "<raza del personaje>",
  "vida_max": <número entre 10 y 20 según constitución y clase>,
  "vida_actual": <igual a vida_max>,
  "ac": <número entre 10 y 16 según raza/clase/equipo descrito>,
  "atributos": {
    "fue": <0-5>,
    "des": <0-5>,
    "con": <0-5>,
    "int": <0-5>,
    "sab": <0-5>,
    "car": <0-5>
  },
  "arma": {
    "nombre": "<arma principal coherente con la clase>",
    "dado_daño": "<dado estándar: 1d4, 1d6, 1d8, 1d10>"
  },
  "inventario": [
    {
      "nombre": "<arma principal>",
      "tipo": "arma",
      "dado_daño": "<dado estándar>",
      "descripcion": "<descripción breve>"
    },
    {
      "nombre": "<arma secundaria coherente con la clase>",
      "tipo": "arma",
      "dado_daño": "<dado estándar>",
      "descripcion": "<descripción breve>"
    },
    {
      "nombre": "poción de cura",
      "tipo": "objeto",
      "efecto": "recupera 2d4 HP",
      "descripcion": "Líquido rojizo que restaura vitalidad"
    }
  ]
}

El inventario debe tener al menos 2 armas y 1 objeto. Las armas deben ser coherentes con
la clase y raza del personaje (ej: un guerrero lleva espada larga y daga; un mago lleva
bastón y daga; un pícaro lleva daga y arco corto)."""


def crear_personaje(descripcion: str) -> dict:
    """Genera la ficha de stats del jugador a partir de su descripción libre.

    Guarda el resultado en data/stats.json y lo devuelve como dict.
    """
    respuesta = _llm.invoke([
        SystemMessage(content=_PROMPT),
        HumanMessage(content=f"Descripción del personaje: {descripcion}")
    ])

    import re
    contenido = respuesta.content
    match = re.search(r'```(?:json)?\s*([\s\S]*?)```', contenido)
    if match:
        contenido = match.group(1).strip()
    stats = json.loads(contenido)

    # Asegurar que vida_actual == vida_max al crear
    stats["vida_actual"] = stats.get("vida_max", 12)

    STATS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(STATS_PATH, 'w', encoding='utf-8') as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)

    return stats


def personaje_existe() -> bool:
    return STATS_PATH.exists() and STATS_PATH.stat().st_size > 0
