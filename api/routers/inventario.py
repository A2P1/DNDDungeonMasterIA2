import json
from fastapi import APIRouter, HTTPException
from api.schemas import ObjetoInventarioRequest, InventarioResponse
from config import STATS_PATH

router = APIRouter(
    prefix="/inventario",
    tags=["Inventario"]
)


def _cargar_stats() -> dict:
    if not STATS_PATH.exists():
        raise HTTPException(status_code=404, detail="No hay ningún personaje creado")
    with open(STATS_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def _guardar_stats(stats: dict):
    with open(STATS_PATH, 'w', encoding='utf-8') as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)


@router.get("/", response_model=InventarioResponse)
def get_inventario(): # Devuelve el inventario completo del jugador
    stats = _cargar_stats()
    return {"inventario": stats.get("inventario", [])}


@router.post("/objeto", response_model=InventarioResponse, status_code=201)
def añadir_objeto(body: ObjetoInventarioRequest): # Añade un objeto al inventario, si ya existe devuelve 409
    stats = _cargar_stats()
    inventario = stats.get("inventario", [])

    if any(obj["nombre"].lower() == body.nombre.lower() for obj in inventario):
        raise HTTPException(status_code=409, detail=f"El objeto '{body.nombre}' ya existe en el inventario")

    nuevo_objeto = body.model_dump(exclude_none=True)
    inventario.append(nuevo_objeto)
    stats["inventario"] = inventario
    _guardar_stats(stats)
    return {"inventario": inventario}


@router.delete("/objeto/{nombre}", response_model=InventarioResponse)
def eliminar_objeto(nombre: str): # Elimina un objeto del inventario por su nombre, si no existe devuelve 404
    stats = _cargar_stats()
    inventario = stats.get("inventario", [])

    inventario_nuevo = [obj for obj in inventario if obj["nombre"].lower() != nombre.lower()]
    if len(inventario_nuevo) == len(inventario):
        raise HTTPException(status_code=404, detail=f"El objeto '{nombre}' no existe en el inventario")

    stats["inventario"] = inventario_nuevo
    _guardar_stats(stats)
    return {"inventario": inventario_nuevo}
