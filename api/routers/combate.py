from fastapi import APIRouter, HTTPException
from api.schemas import AccionCombateRequest, EstadoCombateResponse

router = APIRouter(
    prefix="/combate", # Todas las rutas empezarán por /combate
    tags=["Combate"] # Agrupa los endpoints por categorías
)


@router.get("/estado", response_model=EstadoCombateResponse)
def get_estado_combate(): # Devuelve el estado actual del jugador, enemigos o NPCs y el progreso del combate
    pass


@router.post("/accion", response_model=EstadoCombateResponse)
def enviar_accion_combate(body: AccionCombateRequest): # Recibe la acción del jugador, procesa la acción del enemigo y actualiza el combate
    pass
