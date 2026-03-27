from fastapi import FastAPI
from api.routers import campaña, personaje, partida, combate, inventario

# Instancia principal de la aplicación FastAPI
app = FastAPI(
    title="DnD Dungeon Master IA",
    description="API REST para conectar el backend de la IA con el frontend del juego",
    version="1.0.0"
)

# Registro de routers: cada módulo gestiona su propio grupo de endpoints
app.include_router(campaña.router)    # /campaña  → Crear, obtener y borrar campaña
app.include_router(personaje.router)  # /personaje → Ficha del jugador
app.include_router(partida.router)    # /partida   → Acciones narrativas del juego
app.include_router(combate.router)    # /combate   → Turnos de combate
app.include_router(inventario.router) # /inventario → Gestión de objetos del jugador


@app.get("/")
def root():
    return {"estado": "ok", "mensaje": "DnD Dungeon Master IA en línea"}
