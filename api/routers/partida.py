from fastapi import APIRouter, HTTPException
from api.schemas import AccionJugadorRequest, RespuestaNarradorResponse, EstadoPartidaResponse

router = APIRouter(
    prefix="/partida",
    tags=["Partida"]
)


@router.get("/estado", response_model=EstadoPartidaResponse)
def get_estado_partida(): # Devuelve el beat en curso, el resumen y si la campaña ha terminado
    pass


@router.get("/resumen")
def get_resumen(): # Devuelve el resumen narrativo acumulado hasta ahora
    pass


@router.post("/accion", response_model=RespuestaNarradorResponse)
def enviar_accion(body: AccionJugadorRequest): # Recibe la acción del jugador, si es ataque va a combate, si no al narrador
    pass


@router.post("/iniciar", response_model=RespuestaNarradorResponse)
def iniciar_partida(): # Inicia la partida desde el principio, solo se llama la primera vez
    pass
