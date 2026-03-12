import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
from langchain_core.tools import tool
from config import CAMPAIGN_PATH


@tool
def get_progreso_campaña() -> str:
    """Devuelve el acto actual, beats completados y el siguiente beat pendiente.
    Útil para saber en qué punto de la historia estamos."""
    with open(CAMPAIGN_PATH, 'r', encoding='utf-8') as f:
        campaña = json.load(f)

    completados = []
    pendientes = []

    for acto in campaña["actos"]:
        for beat in acto["beats"]:
            if beat["completado"]:
                completados.append(beat["id"])
            else:
                pendientes.append({
                    "acto": acto["numero"],
                    "titulo_acto": acto["titulo"],
                    "beat": beat
                })

    siguiente = pendientes[0] if pendientes else None

    return json.dumps({
        "titulo_campaña": campaña["titulo"],
        "beats_completados": len(completados),
        "beats_totales": len(completados) + len(pendientes),
        "acto_actual": siguiente["acto"] if siguiente else "CAMPAÑA COMPLETADA",
        "siguiente_beat": siguiente["beat"] if siguiente else None
    }, ensure_ascii=False)


@tool
def get_siguiente_beat() -> str:
    """Devuelve el siguiente punto de historia pendiente para guiar la narrativa."""
    with open(CAMPAIGN_PATH, 'r', encoding='utf-8') as f:
        campaña = json.load(f)

    for acto in campaña["actos"]:
        for beat in acto["beats"]:
            if not beat["completado"]:
                return json.dumps({
                    "acto": acto["numero"],
                    "titulo_acto": acto["titulo"],
                    "objetivo_acto": acto["objetivo"],
                    "beat": beat
                }, ensure_ascii=False)

    return "CAMPAÑA COMPLETADA"


@tool
def marcar_beat_completado(beat_id: str) -> str:
    """Marca un punto de historia como completado cuando el jugador lo supera.
    Recibe el id del beat (ej: 'b1', 'b2')."""
    with open(CAMPAIGN_PATH, 'r', encoding='utf-8') as f:
        campaña = json.load(f)

    encontrado = False
    for acto in campaña["actos"]:
        for beat in acto["beats"]:
            if beat["id"] == beat_id:
                beat["completado"] = True
                encontrado = True
                break

    if not encontrado:
        return f"Error: beat '{beat_id}' no encontrado"

    with open(CAMPAIGN_PATH, 'w', encoding='utf-8') as f:
        json.dump(campaña, f, indent=2, ensure_ascii=False)

    # Comprobar si la campaña ha terminado
    ultimo_beat = campaña["actos"][-1]["beats"][-1]
    if ultimo_beat["completado"]:
        return f"Beat '{beat_id}' completado. ¡LA CAMPAÑA HA TERMINADO!"

    return f"Beat '{beat_id}' completado. Avanzando en la historia."


@tool
def get_info_npc(nombre_npc: str) -> str:
    """Devuelve la información de un NPC de la campaña por su nombre."""
    with open(CAMPAIGN_PATH, 'r', encoding='utf-8') as f:
        campaña = json.load(f)

    for npc in campaña.get("npcs", []):
        if npc["nombre"].lower() == nombre_npc.lower():
            return json.dumps(npc, ensure_ascii=False)

    return f"NPC '{nombre_npc}' no encontrado en la campaña"


