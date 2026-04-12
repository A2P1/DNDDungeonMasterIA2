from fastapi import APIRouter, HTTPException
from api.schemas import AccionJugadorRequest, RespuestaNarradorResponse, EstadoPartidaResponse
from agentes.director import campaña_existe, cargar_campaña
from agentes.Narrador import narrador, narrador_inicio
from config import RESUMEN_PATH

router = APIRouter(
    prefix="/partida",
    tags=["Partida"]
)


def _get_beat_actual(campaña: dict) -> dict | None:
    for acto in campaña.get("actos", []):
        for beat in acto.get("beats", []):
            if not beat.get("completado", False):
                return beat
    return None


def _campaña_completada(campaña: dict) -> bool:
    return all(
        beat.get("completado", False)
        for acto in campaña.get("actos", [])
        for beat in acto.get("beats", [])
    )


@router.get("/estado", response_model=EstadoPartidaResponse)
def get_estado_partida(): # Devuelve el beat en curso, el resumen y si la campaña ha terminado
    if not campaña_existe():
        raise HTTPException(status_code=404, detail="No hay ninguna campaña activa")
    campaña = cargar_campaña()
    resumen = RESUMEN_PATH.read_text(encoding='utf-8').strip() if RESUMEN_PATH.exists() else ""
    return {
        "beat_actual": _get_beat_actual(campaña),
        "resumen": resumen,
        "campaña_completada": _campaña_completada(campaña)
    }


@router.get("/resumen")
def get_resumen(): # Devuelve el resumen narrativo acumulado hasta ahora
    if not RESUMEN_PATH.exists():
        return {"resumen": ""}
    return {"resumen": RESUMEN_PATH.read_text(encoding='utf-8').strip()}


@router.post("/accion", response_model=RespuestaNarradorResponse)
def enviar_accion(body: AccionJugadorRequest): # Recibe la acción del jugador y la procesa con el narrador
    if not campaña_existe():
        raise HTTPException(status_code=404, detail="No hay ninguna campaña activa")
    texto = narrador(body.accion)
    return {"texto": texto, "tipo": "narracion"}


@router.post("/iniciar", response_model=RespuestaNarradorResponse)
def iniciar_partida(): # Inicia la partida desde el principio, solo se llama la primera vez
    if not campaña_existe():
        raise HTTPException(status_code=404, detail="No hay ninguna campaña creada")
    campaña = cargar_campaña()
    texto = narrador_inicio(campaña)
    return {"texto": texto, "tipo": "narracion"}
