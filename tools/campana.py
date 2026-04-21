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

    completados = [] # Acumulamos los ids de los beats ya superados
    pendientes = [] # Acumulamos los beats que faltan por completar con su contexto de acto

    for acto in campaña["actos"]: # Recorremos todos los actos de la campaña
        for beat in acto["beats"]: # Y cada beat dentro del acto
            if beat["completado"]: # Si el beat ya está superado, lo añadimos a completados
                completados.append(beat["id"])
            else: # Si está pendiente, guardamos también el contexto del acto para saber en qué punto estamos
                pendientes.append({
                    "acto": acto["numero"],
                    "titulo_acto": acto["titulo"],
                    "beat": beat
                })

    siguiente = pendientes[0] if pendientes else None # El siguiente beat es el primero de la lista de pendientes

    return json.dumps({ # Devolvemos el resumen del progreso como JSON
        "titulo_campaña": campaña["titulo"],
        "beats_completados": len(completados),
        "beats_totales": len(completados) + len(pendientes),
        "acto_actual": siguiente["acto"] if siguiente else "CAMPAÑA COMPLETADA", # Si no hay pendientes, la campaña terminó
        "siguiente_beat": siguiente["beat"] if siguiente else None
    }, ensure_ascii=False)


@tool
def get_siguiente_beat() -> str:
    """Devuelve el siguiente punto de historia pendiente para guiar la narrativa."""
    with open(CAMPAIGN_PATH, 'r', encoding='utf-8') as f: # Leemos la campaña del disco
        campaña = json.load(f)

    for acto in campaña["actos"]: # Recorremos los actos en orden
        for beat in acto["beats"]: # Y los beats dentro de cada acto
            if not beat["completado"]: # El primer beat que no esté completado es el siguiente
                return json.dumps({ # Devolvemos el beat con el contexto de su acto
                    "acto": acto["numero"],
                    "titulo_acto": acto["titulo"],
                    "objetivo_acto": acto["objetivo"],
                    "beat": beat
                }, ensure_ascii=False)

    return "CAMPAÑA COMPLETADA" # Si todos los beats están completados, la campaña ha terminado


@tool
def marcar_beat_completado(beat_id: str) -> str:
    """Marca un punto de historia como completado cuando el jugador lo supera.
    Recibe el id del beat (ej: 'b1', 'b2')."""
    with open(CAMPAIGN_PATH, 'r', encoding='utf-8') as f: # Leemos la campaña actual
        campaña = json.load(f)

    encontrado = False # Flag para detectar si hemos encontrado el beat
    for acto in campaña["actos"]: # Buscamos el beat en todos los actos
        for beat in acto["beats"]:
            if beat["id"] == beat_id: # Cuando lo encontramos, lo marcamos como completado
                beat["completado"] = True
                encontrado = True
                break

    if not encontrado: # Si no existe el beat, devolvemos un error
        return f"Error: beat '{beat_id}' no encontrado"

    with open(CAMPAIGN_PATH, 'w', encoding='utf-8') as f: # Guardamos la campaña actualizada en el disco
        json.dump(campaña, f, indent=2, ensure_ascii=False)

    ultimo_beat = campaña["actos"][-1]["beats"][-1] # Comprobamos si era el último beat de la campaña
    if ultimo_beat["completado"]: # Si el último beat está completado, la campaña ha terminado
        return f"Beat '{beat_id}' completado. ¡LA CAMPAÑA HA TERMINADO!"

    return f"Beat '{beat_id}' completado. Avanzando en la historia." # Si no, simplemente confirmamos el progreso


@tool
def get_info_npc(nombre_npc: str) -> str:
    """Devuelve la información de un NPC de la campaña por su nombre."""
    with open(CAMPAIGN_PATH, 'r', encoding='utf-8') as f: # Leemos la campaña del disco
        campaña = json.load(f)

    for npc in campaña.get("npcs", []): # Buscamos el NPC por nombre entre todos los NPCs de la campaña
        if npc["nombre"].lower() == nombre_npc.lower(): # Comparamos en minúsculas para evitar problemas de capitalización
            return json.dumps(npc, ensure_ascii=False) # Devolvemos la ficha del NPC como JSON

    return f"NPC '{nombre_npc}' no encontrado en la campaña" # Si no existe, avisamos al LLM
