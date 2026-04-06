from fastapi import APIRouter, HTTPException
from api.schemas import AccionCombateRequest, EstadoCombateResponse

router = APIRouter(
    prefix="/combate",
    tags=["Combate"]
)


@router.get("/estado", response_model=EstadoCombateResponse)
def get_estado_combate(): # Devuelve la vida del jugador, las entidades vivas y si el combate ha terminado
    pass


@router.post("/accion", response_model=EstadoCombateResponse)
def enviar_accion_combate(body: AccionCombateRequest): # Procesa el turno del jugador y el de los enemigos y devuelve el estado actualizado
    pass
