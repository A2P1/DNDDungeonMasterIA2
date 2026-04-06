from fastapi import APIRouter, HTTPException
from api.schemas import ObjetoInventarioRequest, InventarioResponse

router = APIRouter(
    prefix="/inventario",
    tags=["Inventario"]
)


@router.get("/", response_model=InventarioResponse)
def get_inventario(): # Devuelve el inventario completo del jugador
    pass


@router.post("/objeto", response_model=InventarioResponse, status_code=201)
def añadir_objeto(body: ObjetoInventarioRequest): # Añade un objeto al inventario, si ya existe devuelve 409
    pass


@router.delete("/objeto/{nombre}", response_model=InventarioResponse)
def eliminar_objeto(nombre: str): # Elimina un objeto del inventario por su nombre, si no existe devuelve 404
    pass
