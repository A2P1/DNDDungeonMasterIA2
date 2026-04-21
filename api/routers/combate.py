import json # Para parsear la respuesta de get_estado_combate
from fastapi import APIRouter, HTTPException, Query # APIRouter para agrupar endpoints, Query para parámetros de URL
from api.schemas import AccionCombateRequest, EstadoCombateResponse # Schemas de validación
from agentes.combate import procesar_turno # Procesa un turno completo (jugador + enemigos) y devuelve el estado
from tools.entidades import get_estado_combate as _get_estado_combate # Para consultar el estado del combate sin hacer un turno
from config import STATS_PATH # Ruta a la ficha del jugador

router = APIRouter( # Router de combate, todos sus endpoints empiezan por /combate
    prefix="/combate",
    tags=["Combate"]
)


def _cargar_jugador() -> dict: # Lee la ficha del jugador del disco, o lanza 404 si no existe
    if not STATS_PATH.exists():
        raise HTTPException(status_code=404, detail="No hay ningún personaje creado")
    with open(STATS_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


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
        "narracion": None # Sin narración en el GET, solo en el POST /accion
    }


@router.post("/accion", response_model=EstadoCombateResponse)
def enviar_accion_combate(body: AccionCombateRequest): # Procesa el turno del jugador y el contraataque de los enemigos
    if not STATS_PATH.exists():
        raise HTTPException(status_code=404, detail="No hay ningún personaje creado")
    turno = procesar_turno(body.beat_id, body.accion) # El agente de combate resuelve el turno completo
    return turno # Devolvemos el estado actualizado con la narración del turno
