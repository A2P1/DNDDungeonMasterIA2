"""Utilidades de presentación en terminal."""

# Colores ANSI
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"

CYAN = "\033[36m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
MAGENTA = "\033[35m"
BLUE = "\033[34m"
WHITE = "\033[37m"

SEPARADOR = f"{DIM}{'─' * 60}{RESET}"


def narrador_msg(texto: str):
    """Imprime un mensaje del Narrador."""
    print(f"\n{SEPARADOR}")
    print(f"{BOLD}{CYAN}📖 Narrador{RESET}")
    print(f"{WHITE}{texto}{RESET}")
    print(SEPARADOR)


def combate_msg(texto: str):
    """Imprime un mensaje del sistema de combate."""
    print(f"\n{SEPARADOR}")
    print(f"{BOLD}{RED}⚔️  Combate{RESET}")
    print(f"{WHITE}{texto}{RESET}")
    print(SEPARADOR)


def estado_combate(vida_actual: int, vida_max: int, enemigos_str: str):
    """Imprime la barra de estado del combate."""
    print(f"\n{BOLD}{YELLOW}❤️  Vida: {vida_actual}/{vida_max}  |  👹 Enemigos: {enemigos_str}{RESET}\n")


def enemigo_msg(nombre: str, texto: str):
    """Imprime un mensaje de un enemigo atacando."""
    print(f"\n  {BOLD}{MAGENTA}🗡️  {nombre}{RESET}")
    print(f"  {WHITE}{texto}{RESET}")


def sistema_msg(texto: str):
    """Imprime un mensaje del sistema (carga, menús, etc.)."""
    print(f"\n{BOLD}{BLUE}⚙️  {texto}{RESET}")


def titulo_msg(texto: str):
    """Imprime un título grande."""
    borde = "═" * (len(texto) + 4)
    print(f"\n{BOLD}{YELLOW}╔{borde}╗")
    print(f"║  {texto}  ║")
    print(f"╚{borde}╝{RESET}\n")


def victoria_msg(texto: str):
    """Imprime un mensaje de victoria."""
    print(f"\n{BOLD}{GREEN}🏆 ¡Victoria!{RESET}")
    print(f"{GREEN}{texto}{RESET}\n")


def derrota_msg(texto: str):
    """Imprime un mensaje de derrota."""
    print(f"\n{BOLD}{RED}💀 Derrota...{RESET}")
    print(f"{RED}{texto}{RESET}\n")


def prompt_jugador(texto: str = "¿Qué haces?") -> str:
    """Muestra el prompt del jugador y devuelve su input."""
    return input(f"\n{BOLD}{GREEN}🧙 Tú > {RESET}").strip()


def prompt_input(texto: str) -> str:
    """Muestra un prompt genérico y devuelve su input."""
    return input(f"{BOLD}{GREEN}> {RESET}{texto}: ").strip()
