from pydantic import BaseModel
from typing import Optional


# ============================================================
# SCHEMAS DE CAMPAÑA
# ============================================================

class CrearCampañaRequest(BaseModel):
    tema: str       # Tipo de aventura (ej: "mazmorra oscura")
    personaje: str  # Descripción del personaje (ej: "Thorin, enano guerrero")

class CampañaResponse(BaseModel):
    titulo: str
    gancho: str
    ambientacion: dict
    actos: list

# ============================================================
# SCHEMAS DE PERSONAJE
# ============================================================

class CrearPersonajeRequest(BaseModel):
    descripcion: str  # Descripción libre del personaje

class AtributosPersonaje(BaseModel):
    fue: int
    des: int
    con: int
    int_: int  # 'int' es palabra reservada en Python
    sab: int
    car: int

class ArmaPersonaje(BaseModel):
    nombre: str
    dado_daño: str  # Ej: "1d8"

class PersonajeResponse(BaseModel):
    nombre: str
    clase: str
    raza: str
    vida_max: int
    vida_actual: int
    ac: int
    atributos: dict
    arma: dict
    inventario: Optional[list] = []

# ============================================================
# SCHEMAS DE PARTIDA
# ============================================================

class AccionJugadorRequest(BaseModel):
    accion: str  # Lo que escribe el jugador (ej: "Entro a la taberna")

class RespuestaNarradorResponse(BaseModel):
    texto: str        # Narración generada
    tipo: str         # "narracion" | "combate_iniciado"

class EstadoPartidaResponse(BaseModel):
    beat_actual: Optional[dict]   # Beat en curso
    resumen: str                  # Resumen narrativo acumulado
    campaña_completada: bool

# ============================================================
# SCHEMAS DE COMBATE
# ============================================================

class AccionCombateRequest(BaseModel):
    accion: str  # Lo que hace el jugador en su turno (ej: "Ataco con mi espada larga")

class EstadoCombateResponse(BaseModel):
    jugador_vida: int
    jugador_vida_max: int
    entidades_vivas: list   # Lista de entidades vivas con nombre y vida
    combate_terminado: bool
    resultado: Optional[str]  # "victoria" | "derrota" | None

# ============================================================
# SCHEMAS DE INVENTARIO
# ============================================================

class ObjetoInventarioRequest(BaseModel):
    nombre: str
    tipo: str             # "arma" | "objeto"
    dado_daño: Optional[str] = None   # Solo para armas (ej: "1d6")
    descripcion: Optional[str] = ""

class InventarioResponse(BaseModel):
    inventario: list  # Lista completa de objetos
