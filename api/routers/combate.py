import json
from fastapi import APIRouter, HTTPException, Query
from api.schemas import AccionCombateRequest, EstadoCombateResponse
from agentes.combate import procesar_turno
from tools.entidades import get_estado_combate as _get_estado_combate
from config import STATS_PATH

router = APIRouter(
    prefix="/combate",
    tags=["Combate"]
)


def _cargar_jugador() -> dict:
    if not STATS_PATH.exists():
        raise HTTPException(status_code=404, detail="No hay ningún personaje creado")
    with open(STATS_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


@router.get("/estado", response_model=EstadoCombateResponse)
def get_estado_combate(beat_id: str = Query(..., description="ID del beat activo, ej: 'b2'")): # Devuelve la vida del jugador, las entidades vivas y si el combate ha terminado
    jugador = _cargar_jugador()
    estado = json.loads(_get_estado_combate.invoke({"beat_id": beat_id}))
    return {
        "jugador_vida": jugador["vida_actual"],
        "jugador_vida_max": jugador["vida_max"],
        "entidades_vivas": estado.get("enemigos_vivos", []),
        "combate_terminado": estado.get("combate_terminado", False),
        "resultado": None,
        "narracion": None
    }


@router.post("/accion", response_model=EstadoCombateResponse)
def enviar_accion_combate(body: AccionCombateRequest): # Procesa el turno del jugador y el de los enemigos y devuelve el estado actualizado
    if not STATS_PATH.exists():
        raise HTTPException(status_code=404, detail="No hay ningún personaje creado")
    turno = procesar_turno(body.beat_id, body.accion)
    return turno
