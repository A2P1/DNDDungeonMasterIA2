from fastapi import APIRouter, HTTPException
from api.schemas import AccionJugadorRequest, RespuestaNarradorResponse, EstadoPartidaResponse

router = APIRouter(
    prefix="/partida",
    tags=["Partida"]
)


@router.get("/estado", response_model=EstadoPartidaResponse)
def get_estado_partida(): # Devuelve el estado actual de la partida
    pass


@router.get("/resumen")
def get_resumen(): # Devuelve el resumen de la historia hasta el momento
    pass


@router.post("/accion", response_model=RespuestaNarradorResponse)
def enviar_accion(body: AccionJugadorRequest): # Recibe la acción del jugador y se la pasa al narrador, pero si es combate se pasa al agente combate
    pass


@router.post("/iniciar", response_model=RespuestaNarradorResponse)
def iniciar_partida(): # Inicia la partida desde el principio
    pass
