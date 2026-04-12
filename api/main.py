from fastapi import FastAPI
from api.routers import campaña, personaje, partida, combate, inventario

app = FastAPI(
    title="DnD Dungeon Master IA",
    description="API REST para conectar el backend de la IA con el frontend del juego",
    version="1.0.0"
)

# Registramos cada router con su grupo de endpoints
app.include_router(campaña.router)    # /campaña
app.include_router(personaje.router)  # /personaje
app.include_router(partida.router)    # /partida
app.include_router(combate.router)    # /combate
app.include_router(inventario.router) # /inventario


@app.get("/")
def root(): # Comprueba que la API está activa
    return {"estado": "ok", "mensaje": "DnD Dungeon Master IA en línea"}
