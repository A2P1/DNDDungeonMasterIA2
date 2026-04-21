import sys # Para manipular el path de Python
from pathlib import Path # Para manejar rutas de forma cómoda
sys.path.insert(0, str(Path(__file__).parent.parent)) # Añadimos la raíz al path para que los imports del proyecto funcionen

import json # Para leer y escribir el archivo de entidades
from langchain_core.tools import tool # Decorador que convierte funciones en tools para el LLM
from config import ENTIDADES_PATH # Ruta al archivo entidades.json


@tool
def get_enemigos_beat(beat_id: str) -> str:
    """Devuelve la lista de enemigos vivos en un beat concreto.
    Útil al iniciar un combate para saber a qué se enfrenta el jugador.
    Recibe el id del beat (ej: 'b2', 'b5')."""
    with open(ENTIDADES_PATH, 'r', encoding='utf-8') as f: # Leemos todas las entidades del archivo
        entidades = json.load(f)

    enemigos = [ # Filtramos los enemigos del beat indicado que todavía estén vivos
        e for e in entidades.get("enemigos", [])
        if e["beat_origen"] == beat_id and e["estado"] == "vivo"
    ]

    if not enemigos: # Si no hay enemigos vivos en ese beat, avisamos al LLM
        return f"No hay enemigos vivos en el beat '{beat_id}'"

    return json.dumps(enemigos, ensure_ascii=False) # Devolvemos la lista de enemigos vivos como JSON


@tool
def dañar_enemigo(enemigo_id: str, daño: int) -> str:
    """Aplica daño a un enemigo específico. Resta vida_actual y lo marca como muerto si llega a 0.
    Recibe el id del enemigo (ej: 'b3_goblin_1') y la cantidad de daño."""
    with open(ENTIDADES_PATH, 'r', encoding='utf-8') as f: # Leemos las entidades del archivo
        entidades = json.load(f)

    for enemigo in entidades.get("enemigos", []): # Buscamos el enemigo por su id
        if enemigo["id"] == enemigo_id:
            enemigo["vida_actual"] = max(0, enemigo["vida_actual"] - daño) # Restamos el daño sin bajar de 0

            if enemigo["vida_actual"] <= 0: # Si se queda sin vida, lo marcamos como muerto
                enemigo["estado"] = "muerto"
                with open(ENTIDADES_PATH, 'w', encoding='utf-8') as f: # Guardamos el cambio en el disco
                    json.dump(entidades, f, indent=2, ensure_ascii=False)
                return json.dumps({ # Devolvemos el mensaje de muerte con el XP ganado
                    "mensaje": f"{enemigo['nombre']} ha sido derrotado. +{enemigo['xp']} XP",
                    "enemigo": enemigo
                }, ensure_ascii=False)

            with open(ENTIDADES_PATH, 'w', encoding='utf-8') as f: # Si sigue vivo, guardamos la vida actualizada
                json.dump(entidades, f, indent=2, ensure_ascii=False)
            return json.dumps({ # Devolvemos el mensaje de daño con la vida restante
                "mensaje": f"{enemigo['nombre']} recibe {daño} de daño. Vida: {enemigo['vida_actual']}/{enemigo['vida_max']}",
                "enemigo": enemigo
            }, ensure_ascii=False)

    return f"Error: enemigo '{enemigo_id}' no encontrado" # Si no existe el id, avisamos al LLM


@tool
def get_estado_combate(beat_id: str) -> str:
    """Devuelve un resumen del estado del combate en un beat: enemigos vivos, muertos y HP restante.
    Recibe el id del beat (ej: 'b3')."""
    with open(ENTIDADES_PATH, 'r', encoding='utf-8') as f: # Leemos todas las entidades
        entidades = json.load(f)

    enemigos_beat = [ # Filtramos todos los enemigos de ese beat, vivos o muertos
        e for e in entidades.get("enemigos", [])
        if e["beat_origen"] == beat_id
    ]

    if not enemigos_beat: # Si no hay ninguno registrado para ese beat, avisamos
        return f"No hay enemigos registrados en el beat '{beat_id}'"

    vivos = [e for e in enemigos_beat if e["estado"] == "vivo"] # Separamos vivos y muertos
    muertos = [e for e in enemigos_beat if e["estado"] == "muerto"]

    resumen = { # Construimos el resumen del combate
        "beat_id": beat_id,
        "total": len(enemigos_beat),
        "vivos": len(vivos),
        "muertos": len(muertos),
        "combate_terminado": len(vivos) == 0, # Si no quedan vivos, el combate está terminado
        "enemigos_vivos": [ # Lista de enemigos vivos con su vida actual para que el LLM sepa el estado
            {"id": e["id"], "nombre": e["nombre"], "vida": f"{e['vida_actual']}/{e['vida_max']}"}
            for e in vivos
        ]
    }

    return json.dumps(resumen, ensure_ascii=False) # Devolvemos el resumen como JSON


@tool
def get_info_entidad(entidad_id: str) -> str:
    """Devuelve la ficha completa de un enemigo o NPC por su id.
    Busca primero en enemigos y luego en NPCs."""
    with open(ENTIDADES_PATH, 'r', encoding='utf-8') as f: # Leemos todas las entidades
        entidades = json.load(f)

    for enemigo in entidades.get("enemigos", []): # Primero buscamos entre los enemigos
        if enemigo["id"] == entidad_id:
            return json.dumps(enemigo, ensure_ascii=False) # Si lo encontramos, devolvemos su ficha

    for npc in entidades.get("npcs", []): # Si no está en enemigos, buscamos entre los NPCs
        if npc["id"] == entidad_id:
            return json.dumps(npc, ensure_ascii=False) # Devolvemos la ficha del NPC

    return f"Error: entidad '{entidad_id}' no encontrada" # Si no está en ninguna lista, avisamos


@tool
def dañar_npc(npc_id: str, daño: int) -> str:
    """Aplica daño a un NPC específico. Resta vida_actual y lo marca como muerto si llega a 0.
    Recibe el id del NPC (ej: 'npc_elara') y la cantidad de daño."""
    with open(ENTIDADES_PATH, 'r', encoding='utf-8') as f: # Leemos las entidades del archivo
        entidades = json.load(f)

    for npc in entidades.get("npcs", []): # Buscamos el NPC por su id
        if npc["id"] == npc_id:
            npc["vida_actual"] = max(0, npc["vida_actual"] - daño) # Restamos el daño sin bajar de 0

            if npc["vida_actual"] <= 0: # Si se queda sin vida, lo marcamos como muerto
                npc["estado"] = "muerto"
                with open(ENTIDADES_PATH, 'w', encoding='utf-8') as f: # Guardamos el cambio en el disco
                    json.dump(entidades, f, indent=2, ensure_ascii=False)
                return json.dumps({ # Devolvemos el mensaje de muerte
                    "mensaje": f"{npc['nombre']} ha muerto.",
                    "npc": npc
                }, ensure_ascii=False)

            with open(ENTIDADES_PATH, 'w', encoding='utf-8') as f: # Si sigue vivo, guardamos la vida actualizada
                json.dump(entidades, f, indent=2, ensure_ascii=False)
            return json.dumps({ # Devolvemos el mensaje de daño con la vida restante
                "mensaje": f"{npc['nombre']} recibe {daño} de daño. Vida: {npc['vida_actual']}/{npc['vida_max']}",
                "npc": npc
            }, ensure_ascii=False)

    return f"Error: NPC '{npc_id}' no encontrado" # Si no existe el id, avisamos al LLM
