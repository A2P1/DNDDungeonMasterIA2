from agentes.Narrador import narrador, narrador_inicio
from agentes.director import generar_campaña, campaña_existe, cargar_campaña
from agentes.enriquecedor import enriquecer_entidades, entidades_existen
from agentes.combate import combate
from tools.campana import get_siguiente_beat, marcar_beat_completado
from dotenv import load_dotenv
from config import RESUMEN_PATH, CAMPAIGN_PATH, ENTIDADES_PATH
import json


def _nueva_campaña():
    """Crea una campaña desde cero pidiendo datos al jugador."""
    print("=== CREACIÓN DE CAMPAÑA ===\n")
    tema = input("¿Qué tipo de aventura quieres? (ej: mazmorra oscura, bosque maldito, ciudad pirata): ")
    personaje = input("Describe tu personaje (ej: Thorin, enano guerrero): ")

    print("\nGenerando tu campaña... (esto puede tardar unos segundos)\n")
    campaña = generar_campaña(tema, personaje)
    print(f"¡Campaña '{campaña['titulo']}' creada!\n")
    print(f"Gancho: {campaña['gancho']}\n")
    return campaña


def _limpiar_partida():
    """Borra los archivos de la partida anterior para empezar de cero."""
    for path in [CAMPAIGN_PATH, ENTIDADES_PATH]:
        if path.exists():
            path.unlink()
    # Vaciar resumen (crear directorio si no existe)
    RESUMEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(RESUMEN_PATH, 'w', encoding='utf-8') as f:
        f.write("")


def iniciar_campaña():
    """Muestra menú de inicio: continuar partida existente o empezar nueva."""
    if campaña_existe():
        campaña = cargar_campaña()
        print(f"=== Campaña encontrada: '{campaña.get('titulo', 'Sin título')}' ===\n")
        print("1. Continuar partida")
        print("2. Nueva campaña\n")
        opcion = input("Elige una opción (1/2): ").strip()

        if opcion == "2":
            _limpiar_partida()
            campaña = _nueva_campaña()
        else:
            print("Continuando partida...\n")
    else:
        campaña = _nueva_campaña()

    # Enriquecer entidades si no existen
    if not entidades_existen():
        print("Generando fichas detalladas de enemigos y NPCs...\n")
        enriquecer_entidades(campaña)
        print("Fichas generadas.\n")

    return campaña


def _beat_es_combate():
    """Comprueba si el siguiente beat pendiente es de combate. Devuelve el beat o None."""
    raw = get_siguiente_beat.invoke({})
    if raw == "CAMPAÑA COMPLETADA":
        return None
    data = json.loads(raw)
    beat = data.get("beat", {})
    if beat.get("tipo") in ("combate", "jefe", "climax"):
        return beat
    return None


def main():
    load_dotenv()

    # Generar o cargar la campaña antes de empezar
    campaña = iniciar_campaña()

    while True:
        # Comprobar si el beat actual es de combate antes de pedir input
        beat_combate = _beat_es_combate()
        if beat_combate:
            # Transición narrativa: el narrador introduce el combate
            print(narrador(f"[SISTEMA] El jugador llega al momento: {beat_combate['descripcion']}. Narra la aparición de los enemigos y la tensión del momento."))

            resultado = combate(beat_combate["id"])
            marcar_beat_completado.invoke({"beat_id": beat_combate["id"]})

            # Transición narrativa post-combate
            if resultado == "victoria":
                print(narrador(f"[SISTEMA] El jugador ha ganado el combate en: {beat_combate['descripcion']}. Narra las consecuencias de la victoria y guía hacia lo que viene después."))
            else:
                print(narrador(f"[SISTEMA] El jugador ha sido derrotado en: {beat_combate['descripcion']}. Narra su caída."))
                break
            continue

        resumen = RESUMEN_PATH.read_text(encoding='utf-8').strip() if RESUMEN_PATH.exists() else ""
        if resumen:
            user_input = input("Escribe tu mensaje (o 'salir' para terminar): \n")
            if user_input.lower() == "salir":
                break
            print(narrador(user_input))
        else:
            print(narrador_inicio(campaña))
main()

