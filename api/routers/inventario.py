import json # Para leer y escribir el stats.json
from fastapi import APIRouter, HTTPException # APIRouter para agrupar endpoints, HTTPException para errores HTTP
from api.schemas import ObjetoInventarioRequest, InventarioResponse # Schemas de validación
from config import STATS_PATH # Ruta a la ficha del jugador donde está el inventario

router = APIRouter( # Router de inventario, todos sus endpoints empiezan por /inventario
    prefix="/inventario",
    tags=["Inventario"]
)


def _cargar_stats() -> dict: # Lee la ficha del jugador del disco, o lanza 404 si no existe
    if not STATS_PATH.exists():
        raise HTTPException(status_code=404, detail="No hay ningún personaje creado")
    with open(STATS_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def _guardar_stats(stats: dict): # Guarda la ficha del jugador actualizada en el disco
    with open(STATS_PATH, 'w', encoding='utf-8') as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)


@router.get("/", response_model=InventarioResponse)
def get_inventario(): # Devuelve el inventario completo del jugador
    stats = _cargar_stats()
    return {"inventario": stats.get("inventario", [])} # Si no tiene inventario, devolvemos lista vacía


@router.post("/objeto", response_model=InventarioResponse, status_code=201)
def añadir_objeto(body: ObjetoInventarioRequest): # Añade un objeto al inventario, si ya existe devuelve 409
    stats = _cargar_stats()
    inventario = stats.get("inventario", [])

    if any(obj["nombre"].lower() == body.nombre.lower() for obj in inventario): # Comprobamos si ya existe un objeto con ese nombre
        raise HTTPException(status_code=409, detail=f"El objeto '{body.nombre}' ya existe en el inventario")

    nuevo_objeto = body.model_dump(exclude_none=True) # Convertimos el body a dict descartando los campos None
    inventario.append(nuevo_objeto) # Añadimos el objeto al inventario
    stats["inventario"] = inventario
    _guardar_stats(stats) # Guardamos la ficha actualizada
    return {"inventario": inventario}


@router.delete("/objeto/{nombre}", response_model=InventarioResponse)
def eliminar_objeto(nombre: str): # Elimina un objeto del inventario por su nombre, o 404 si no existe
    stats = _cargar_stats()
    inventario = stats.get("inventario", [])

    inventario_nuevo = [obj for obj in inventario if obj["nombre"].lower() != nombre.lower()] # Filtramos el objeto a eliminar
    if len(inventario_nuevo) == len(inventario): # Si el tamaño no cambió, el objeto no estaba en el inventario
        raise HTTPException(status_code=404, detail=f"El objeto '{nombre}' no existe en el inventario")

    stats["inventario"] = inventario_nuevo
    _guardar_stats(stats) # Guardamos el inventario sin el objeto eliminado
    return {"inventario": inventario_nuevo}
