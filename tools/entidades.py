import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
from langchain_core.tools import tool
from config import ENTIDADES_PATH


@tool
def get_enemigos_beat(beat_id: str) -> str:
    """Devuelve la lista de enemigos vivos en un beat concreto.
    Útil al iniciar un combate para saber a qué se enfrenta el jugador.
    Recibe el id del beat (ej: 'b2', 'b5')."""
    with open(ENTIDADES_PATH, 'r', encoding='utf-8') as f:
        entidades = json.load(f)

    enemigos = [
        e for e in entidades.get("enemigos", [])
        if e["beat_origen"] == beat_id and e["estado"] == "vivo"
    ]

    if not enemigos:
        return f"No hay enemigos vivos en el beat '{beat_id}'"

    return json.dumps(enemigos, ensure_ascii=False)


@tool
def dañar_enemigo(enemigo_id: str, daño: int) -> str:
    """Aplica daño a un enemigo específico. Resta vida_actual y lo marca como muerto si llega a 0.
    Recibe el id del enemigo (ej: 'b3_goblin_1') y la cantidad de daño."""
    with open(ENTIDADES_PATH, 'r', encoding='utf-8') as f:
        entidades = json.load(f)

    for enemigo in entidades.get("enemigos", []):
        if enemigo["id"] == enemigo_id:
            enemigo["vida_actual"] = max(0, enemigo["vida_actual"] - daño)

            if enemigo["vida_actual"] <= 0:
                enemigo["estado"] = "muerto"
                with open(ENTIDADES_PATH, 'w', encoding='utf-8') as f:
                    json.dump(entidades, f, indent=2, ensure_ascii=False)
                return json.dumps({
                    "mensaje": f"{enemigo['nombre']} ha sido derrotado. +{enemigo['xp']} XP",
                    "enemigo": enemigo
                }, ensure_ascii=False)

            with open(ENTIDADES_PATH, 'w', encoding='utf-8') as f:
                json.dump(entidades, f, indent=2, ensure_ascii=False)
            return json.dumps({
                "mensaje": f"{enemigo['nombre']} recibe {daño} de daño. Vida: {enemigo['vida_actual']}/{enemigo['vida_max']}",
                "enemigo": enemigo
            }, ensure_ascii=False)

    return f"Error: enemigo '{enemigo_id}' no encontrado"


@tool
def get_estado_combate(beat_id: str) -> str:
    """Devuelve un resumen del estado del combate en un beat: enemigos vivos, muertos y HP restante.
    Recibe el id del beat (ej: 'b3')."""
    with open(ENTIDADES_PATH, 'r', encoding='utf-8') as f:
        entidades = json.load(f)

    enemigos_beat = [
        e for e in entidades.get("enemigos", [])
        if e["beat_origen"] == beat_id
    ]

    if not enemigos_beat:
        return f"No hay enemigos registrados en el beat '{beat_id}'"

    vivos = [e for e in enemigos_beat if e["estado"] == "vivo"]
    muertos = [e for e in enemigos_beat if e["estado"] == "muerto"]

    resumen = {
        "beat_id": beat_id,
        "total": len(enemigos_beat),
        "vivos": len(vivos),
        "muertos": len(muertos),
        "combate_terminado": len(vivos) == 0,
        "enemigos_vivos": [
            {"id": e["id"], "nombre": e["nombre"], "vida": f"{e['vida_actual']}/{e['vida_max']}"}
            for e in vivos
        ]
    }

    return json.dumps(resumen, ensure_ascii=False)


@tool
def get_info_entidad(entidad_id: str) -> str:
    """Devuelve la ficha completa de un enemigo o NPC por su id.
    Busca primero en enemigos y luego en NPCs."""
    with open(ENTIDADES_PATH, 'r', encoding='utf-8') as f:
        entidades = json.load(f)

    for enemigo in entidades.get("enemigos", []):
        if enemigo["id"] == entidad_id:
            return json.dumps(enemigo, ensure_ascii=False)

    for npc in entidades.get("npcs", []):
        if npc["id"] == entidad_id:
            return json.dumps(npc, ensure_ascii=False)

    return f"Error: entidad '{entidad_id}' no encontrada"


@tool
def dañar_npc(npc_id: str, daño: int) -> str:
    """Aplica daño a un NPC específico. Resta vida_actual y lo marca como muerto si llega a 0.
    Recibe el id del NPC (ej: 'npc_elara') y la cantidad de daño."""
    with open(ENTIDADES_PATH, 'r', encoding='utf-8') as f:
        entidades = json.load(f)

    for npc in entidades.get("npcs", []):
        if npc["id"] == npc_id:
            npc["vida_actual"] = max(0, npc["vida_actual"] - daño)

            if npc["vida_actual"] <= 0:
                npc["estado"] = "muerto"
                with open(ENTIDADES_PATH, 'w', encoding='utf-8') as f:
                    json.dump(entidades, f, indent=2, ensure_ascii=False)
                return json.dumps({
                    "mensaje": f"{npc['nombre']} ha muerto.",
                    "npc": npc
                }, ensure_ascii=False)

            with open(ENTIDADES_PATH, 'w', encoding='utf-8') as f:
                json.dump(entidades, f, indent=2, ensure_ascii=False)
            return json.dumps({
                "mensaje": f"{npc['nombre']} recibe {daño} de daño. Vida: {npc['vida_actual']}/{npc['vida_max']}",
                "npc": npc
            }, ensure_ascii=False)

    return f"Error: NPC '{npc_id}' no encontrado"
