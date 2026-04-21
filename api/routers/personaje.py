import json # Para leer y escribir el stats.json
from fastapi import APIRouter, HTTPException # APIRouter para agrupar endpoints, HTTPException para errores HTTP
from api.schemas import CrearPersonajeRequest, PersonajeResponse # Schemas de validación
from agentes.creador_personaje import crear_personaje as _crear_personaje, personaje_existe # Funciones del agente creador
from config import STATS_PATH # Ruta al archivo de la ficha del jugador

router = APIRouter( # Router de personaje, todos sus endpoints empiezan por /personaje
    prefix="/personaje",
    tags=["Personaje"]
)


def _cargar_stats() -> dict: # Lee la ficha del jugador del disco, o lanza 404 si no existe
    if not STATS_PATH.exists():
        raise HTTPException(status_code=404, detail="No hay ningún personaje creado")
    with open(STATS_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def _guardar_stats(stats: dict): # Guarda la ficha del jugador en el disco
    with open(STATS_PATH, 'w', encoding='utf-8') as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)


@router.get("/", response_model=PersonajeResponse)
def get_personaje(): # Devuelve la ficha completa del jugador, o 404 si no existe
    return _cargar_stats()


@router.post("/", response_model=PersonajeResponse, status_code=201)
def crear_personaje(body: CrearPersonajeRequest): # Genera una ficha nueva a partir de la descripción del jugador
    stats = _crear_personaje(body.descripcion) # El agente creador genera los stats y los guarda en el disco
    return stats


@router.put("/", response_model=PersonajeResponse)
def actualizar_personaje(body: PersonajeResponse): # Actualiza los datos del personaje, útil para modificar stats desde el frontend
    if not personaje_existe():
        raise HTTPException(status_code=404, detail="No hay ningún personaje creado")
    stats = _cargar_stats() # Cargamos la ficha actual
    stats.update(body.model_dump(exclude_none=True)) # Sobreescribimos solo los campos que vienen en el body
    _guardar_stats(stats) # Guardamos los cambios
    return stats
