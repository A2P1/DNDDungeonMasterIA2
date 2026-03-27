from fastapi import APIRouter, HTTPException
from api.schemas import ObjetoInventarioRequest, InventarioResponse

router = APIRouter(
    prefix="/inventario",
    tags=["Inventario"]
)


@router.get("/", response_model=InventarioResponse)
def get_inventario(): # Devuelve el inventario
    pass


@router.post("/objeto", response_model=InventarioResponse, status_code=201)
def añadir_objeto(body: ObjetoInventarioRequest): # Añade un objeto al inventario del jugador
    pass


@router.delete("/objeto/{nombre}", response_model=InventarioResponse)
def eliminar_objeto(nombre: str): # Elimina un objeto del inventario por su nombre
    pass
