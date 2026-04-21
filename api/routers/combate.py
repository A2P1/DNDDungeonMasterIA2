import json # Para parsear respuestas de las tools y leer entidades.json
from fastapi import APIRouter, HTTPException, Query # APIRouter para agrupar endpoints, Query para parámetros de URL
from api.schemas import AccionCombateRequest, EstadoCombateResponse, IniciarCombateResponse # Schemas de validación
from agentes.combate import procesar_turno # Procesa un turno completo (jugador + enemigos) y devuelve el estado
from agentes.Narrador import narrador # Para generar la narración de introducción del combate
from tools.entidades import get_estado_combate as _get_estado_combate # Para consultar el estado del combate sin hacer un turno
from tools.campana import marcar_beat_completado, get_siguiente_beat # Para marcar el beat como superado y obtener el beat activo
from tools.inventario import add_item_to_inventory # Para añadir el loot al inventario del jugador
from agentes.director import campaña_existe # Para comprobar si hay campaña activa antes de iniciar el combate
from services.routing import get_entidades_presentes # Para obtener las entidades vivas del beat activo
from config import STATS_PATH, ENTIDADES_PATH # Rutas a la ficha del jugador y al archivo de entidades

router = APIRouter( # Router de combate, todos sus endpoints empiezan por /combate
    prefix="/combate",
    tags=["Combate"]
)

# Tipos de beat que implican combate — usados para validar que el beat activo es de combate
_TIPOS_COMBATE = ("combate", "jefe", "climax")


def _cargar_jugador() -> dict: # Lee la ficha del jugador del disco, o lanza 404 si no existe
    if not STATS_PATH.exists():
        raise HTTPException(status_code=404, detail="No hay ningún personaje creado")
    with open(STATS_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def _recoger_loot(beat_id: str) -> list: # Busca los enemigos muertos del beat, recoge su loot y lo añade al inventario
    if not ENTIDADES_PATH.exists(): # Si no hay archivo de entidades no hay loot que recoger
        return []

    with open(ENTIDADES_PATH, 'r', encoding='utf-8') as f: # Leemos todas las entidades
        entidades = json.load(f)

    items_recogidos = [] # Aquí acumulamos los items que vayamos recogiendo

    enemigos_del_beat = [ # Filtramos los enemigos muertos del beat (o "temp" para combate narrativo)
        e for e in entidades.get("enemigos", [])
        if e.get("beat_origen") == beat_id and e.get("estado") == "muerto"
    ]

    for enemigo in enemigos_del_beat: # Recorremos cada enemigo muerto del beat
        for item in enemigo.get("loot", []): # Recorremos su lista de loot (puede estar vacía)
            add_item_to_inventory.invoke({"item_json": json.dumps(item, ensure_ascii=False)}) # Añadimos el item al inventario
            items_recogidos.append(item) # Lo añadimos a la lista de respuesta

    return items_recogidos # Devolvemos todos los items recogidos


@router.post("/iniciar", response_model=IniciarCombateResponse)
def iniciar_combate(): # Inicializa el combate del beat activo: valida que es de combate, obtiene entidades y genera la intro
    if not campaña_existe(): # Sin campaña no hay beat de combate
        raise HTTPException(status_code=404, detail="No hay ninguna campaña activa")

    raw = get_siguiente_beat.invoke({}) # Consultamos cuál es el siguiente beat pendiente
    if raw == "CAMPAÑA COMPLETADA": # Si la campaña terminó, no hay combate que iniciar
        raise HTTPException(status_code=409, detail="La campaña ya está completada")

    data = json.loads(raw) # Parseamos la respuesta del beat
    beat = data.get("beat", {}) # Extraemos el objeto beat
    beat_id = beat.get("id", "") # Guardamos el id del beat
    beat_tipo = beat.get("tipo", "") # Tipo del beat: "combate", "dialogo", "exploracion", etc.

    if beat_tipo not in _TIPOS_COMBATE: # Si el beat activo no es de combate, no tiene sentido inicializarlo así
        raise HTTPException(
            status_code=409,
            detail=f"El beat activo ('{beat_id}') es de tipo '{beat_tipo}', no es un beat de combate"
        )

    entidades = get_entidades_presentes() # Obtenemos las entidades vivas registradas en este beat
    if not entidades: # Si no hay entidades, el beat de combate ya está limpio (puede que fuera resuelto antes)
        raise HTTPException(
            status_code=409,
            detail=f"No hay enemigos vivos en el beat '{beat_id}'. El combate puede que ya esté resuelto."
        )

    descripcion = beat.get("descripcion", "") # Descripción del beat para dar contexto al frontend
    narracion = narrador( # El narrador genera la introducción del combate con el contexto del beat
        f"[SISTEMA] El jugador llega al momento: {descripcion}. "
        f"Narra la aparición de los enemigos y la tensión del momento. No resuelvas ningún ataque todavía."
    )

    return { # Devolvemos todo lo que el frontend necesita para arrancar la pantalla de combate
        "beat_id": beat_id, # El frontend lo usará en cada POST /combate/accion
        "descripcion": descripcion, # Para mostrar contexto al jugador
        "entidades": entidades, # Las entidades contra las que va a pelear (con sus stats)
        "narracion": narracion # El texto de introducción para mostrar antes de empezar los turnos
    }


@router.get("/estado", response_model=EstadoCombateResponse)
def get_estado_combate(beat_id: str = Query(..., description="ID del beat activo, ej: 'b2'")): # Devuelve la vida del jugador, las entidades vivas y si el combate ha terminado
    jugador = _cargar_jugador() # Cargamos la ficha del jugador para saber su vida actual
    estado = json.loads(_get_estado_combate.invoke({"beat_id": beat_id})) # Consultamos el estado del combate en el beat
    return {
        "jugador_vida": jugador["vida_actual"],
        "jugador_vida_max": jugador["vida_max"],
        "entidades_vivas": estado.get("enemigos_vivos", []), # Lista de enemigos que siguen en pie
        "combate_terminado": estado.get("combate_terminado", False),
        "resultado": None, # Sin resultado todavía, el combate sigue
        "narracion": None, # Sin narración en el GET, solo en el POST /accion
        "loot": None # Sin loot en el GET, solo se devuelve al terminar el combate
    }


@router.post("/accion", response_model=EstadoCombateResponse)
def enviar_accion_combate(body: AccionCombateRequest): # Procesa el turno del jugador y el contraataque de los enemigos
    if not STATS_PATH.exists():
        raise HTTPException(status_code=404, detail="No hay ningún personaje creado")

    turno = procesar_turno(body.beat_id, body.accion) # El agente de combate resuelve el turno completo

    resultado = turno.get("resultado") # "victoria", "derrota", "resolucion" o None si el combate sigue
    loot = None # Por defecto no hay loot; solo se rellena al terminar el combate

    if resultado in ("victoria", "resolucion"): # Si el combate terminó, completamos el beat y recogemos el loot
        if body.beat_id != "temp": # Los beats temporales (combate narrativo) no existen en campaign.json
            marcar_beat_completado.invoke({"beat_id": body.beat_id}) # Avanzamos la campaña al siguiente beat
        loot = _recoger_loot(body.beat_id) # Recogemos el loot de todos los enemigos muertos del beat

    turno["loot"] = loot # Añadimos el loot a la respuesta para que el frontend lo pueda mostrar
    return turno
