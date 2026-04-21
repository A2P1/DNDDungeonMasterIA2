from fastapi import APIRouter, HTTPException # APIRouter para agrupar endpoints, HTTPException para errores HTTP
from api.schemas import AccionJugadorRequest, RespuestaNarradorResponse, EstadoPartidaResponse # Schemas de validación
from agentes.director import campaña_existe, cargar_campaña # Para comprobar si hay campaña activa
from agentes.Narrador import narrador, narrador_inicio # Los dos modos del narrador: turno normal e inicio de partida
from config import RESUMEN_PATH # Ruta al resumen narrativo de la partida

router = APIRouter( # Router de partida, todos sus endpoints empiezan por /partida
    prefix="/partida",
    tags=["Partida"]
)


def _get_beat_actual(campaña: dict) -> dict | None: # Devuelve el primer beat que no esté completado, o None si la campaña terminó
    for acto in campaña.get("actos", []):
        for beat in acto.get("beats", []):
            if not beat.get("completado", False): # El primer beat no completado es el beat actual
                return beat
    return None # Si todos están completados, la campaña ha terminado


def _campaña_completada(campaña: dict) -> bool: # Comprueba si todos los beats de la campaña están completados
    return all(
        beat.get("completado", False)
        for acto in campaña.get("actos", [])
        for beat in acto.get("beats", [])
    )


@router.get("/estado", response_model=EstadoPartidaResponse)
def get_estado_partida(): # Devuelve el beat en curso, el resumen y si la campaña ha terminado
    if not campaña_existe():
        raise HTTPException(status_code=404, detail="No hay ninguna campaña activa")
    campaña = cargar_campaña() # Cargamos la campaña del disco
    resumen = RESUMEN_PATH.read_text(encoding='utf-8').strip() if RESUMEN_PATH.exists() else "" # Leemos el resumen si existe
    return {
        "beat_actual": _get_beat_actual(campaña),
        "resumen": resumen,
        "campaña_completada": _campaña_completada(campaña)
    }


@router.get("/resumen")
def get_resumen(): # Devuelve solo el resumen narrativo acumulado hasta ahora
    if not RESUMEN_PATH.exists():
        return {"resumen": ""}
    return {"resumen": RESUMEN_PATH.read_text(encoding='utf-8').strip()}


@router.post("/accion", response_model=RespuestaNarradorResponse)
def enviar_accion(body: AccionJugadorRequest): # Recibe la acción del jugador y la procesa con el narrador
    if not campaña_existe():
        raise HTTPException(status_code=404, detail="No hay ninguna campaña activa")
    texto = narrador(body.accion) # El narrador genera la respuesta narrativa
    return {"texto": texto, "tipo": "narracion"}


@router.post("/iniciar", response_model=RespuestaNarradorResponse)
def iniciar_partida(): # Inicia la partida desde el principio, solo se llama la primera vez
    if not campaña_existe():
        raise HTTPException(status_code=404, detail="No hay ninguna campaña creada")
    campaña = cargar_campaña() # Cargamos la campaña para pasársela al narrador de inicio
    texto = narrador_inicio(campaña) # El narrador genera la narración de apertura con el contexto de la campaña
    return {"texto": texto, "tipo": "narracion"}
