import sys # Para manipular el path de Python
from pathlib import Path # Para manejar rutas de forma cómoda
sys.path.insert(0, str(Path(__file__).parent.parent)) # Añadimos la raíz al path para que los imports del proyecto funcionen

import json # Para leer y escribir los archivos JSON de la campaña
from langchain_core.tools import tool # Decorador que convierte funciones en tools para el LLM
from config import CAMPAIGN_PATH # Ruta al archivo campaign.json


@tool
def get_progreso_campana() -> str:
    """Devuelve el acto actual, beats completados y el siguiente beat pendiente.
    Útil para saber en qué punto de la historia estamos."""
    with open(CAMPAIGN_PATH, 'r', encoding='utf-8') as f: # Leemos la campaña del disco
        campaña = json.load(f)

    progreso = 0
    beatsTotales = 0
    actoActual = ""
    for acto in campaña["actos"]:
        beatsCompletados = sum(beat["completado"] for beat in acto["beats"]) # Acumulamos los beats completados
        progreso += beatsCompletados
        beatPendiente = next((beat for beat in acto["beats"] if not beat["completado"]), None) # Buscamos el siguiente beat pendiente
        beatsTotales += len(acto["beats"])
        actoActual = acto["titulo"]
        if beatPendiente:
            break

    resumen = {
        "titulo_campaña": campaña["titulo"],
        "beats_completados": progreso,
        "Beats_totales": beatsTotales,
        "siguiente_beat": beatPendiente if beatPendiente else "Todos los beats completados",
        "acto_actual": actoActual
    }
    return json.dumps(resumen, ensure_ascii=False)



@tool
def get_siguiente_beat() -> str:
    """Devuelve el siguiente punto de historia pendiente para guiar la narrativa."""
    with open(CAMPAIGN_PATH, 'r', encoding='utf-8') as f:
        campaña = json.load(f)

    for actos in campaña["actos"]:
        for beats in actos["beats"]:
            if not beats["completado"]:
                resumen = {
                    "titulo_campaña": campaña["titulo"],
                    "siguiente_beat": beats,
                    "acto_actual": actos["titulo"]
                }
                return json.dumps(resumen, ensure_ascii=False)
    return "Todos los beats de la campaña están completados"

@tool
def marcar_beat_completado(beat_id: str) -> str:
    """Marca un punto de historia como completado cuando el jugador lo supera.
    Recibe el id del beat (ej: 'b1', 'b2')."""
    with open(CAMPAIGN_PATH, 'r', encoding='utf-8') as f:
        campaña = json.load(f)
    for acto in campaña["actos"]:
        for beat in acto["beats"]:
            if beat["id"] == beat_id:
                beat["completado"] = True
                with open(CAMPAIGN_PATH, 'w', encoding='utf-8') as f: # Guardamos el cambio en el disco
                    json.dump(campaña, f, indent=2, ensure_ascii=False)
                return f"Beat '{beat_id}' marcado como completado"
    
    return f"Beat '{beat_id}' no encontrado en la campaña"



@tool
def get_info_npc(nombre_npc: str) -> str:
    """Devuelve la información de un NPC de la campaña por su nombre."""
    with open(CAMPAIGN_PATH, 'r', encoding='utf-8') as f:
        campaña = json.load(f)
    for npc in campaña["npcs"]:
        if npc["nombre"].lower() == nombre_npc.lower():
            return json.dumps(npc, ensure_ascii=False)
    return f"NPC '{nombre_npc}' no encontrado en la campaña"
