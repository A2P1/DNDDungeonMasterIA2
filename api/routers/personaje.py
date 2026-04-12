import json
from fastapi import APIRouter, HTTPException
from api.schemas import CrearPersonajeRequest, PersonajeResponse
from agentes.creador_personaje import crear_personaje as _crear_personaje, personaje_existe
from config import STATS_PATH

router = APIRouter(
    prefix="/personaje",
    tags=["Personaje"]
)


def _cargar_stats() -> dict:
    if not STATS_PATH.exists():
        raise HTTPException(status_code=404, detail="No hay ningún personaje creado")
    with open(STATS_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def _guardar_stats(stats: dict):
    with open(STATS_PATH, 'w', encoding='utf-8') as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)


@router.get("/", response_model=PersonajeResponse)
def get_personaje(): # Devuelve la ficha del personaje, si no existe devuelve 404
    return _cargar_stats()


@router.post("/", response_model=PersonajeResponse, status_code=201)
def crear_personaje(body: CrearPersonajeRequest): # Genera la ficha del personaje a partir de su descripción
    stats = _crear_personaje(body.descripcion)
    return stats


@router.put("/", response_model=PersonajeResponse)
def actualizar_personaje(body: PersonajeResponse): # Actualiza los datos del personaje, útil para modificar stats desde el frontend
    if not personaje_existe():
        raise HTTPException(status_code=404, detail="No hay ningún personaje creado")
    stats = _cargar_stats()
    stats.update(body.model_dump(exclude_none=True))
    _guardar_stats(stats)
    return stats
