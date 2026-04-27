# Códigos de escape ANSI para dar color y formato al texto de la terminal
RESET = "\033[0m" # Vuelve al estilo por defecto
BOLD = "\033[1m" # Texto en negrita
DIM = "\033[2m" # Texto atenuado

CYAN = "\033[36m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
MAGENTA = "\033[35m"
BLUE = "\033[34m"
WHITE = "\033[37m"

SEPARADOR = f"{DIM}{'─' * 60}{RESET}" # Línea separadora para dividir visualmente los mensajes


def narrador_msg(texto: str): # Imprime la narración del DM con su formato visual propio
    print(f"\n{SEPARADOR}")
    print(f"{BOLD}{CYAN}📖 Narrador{RESET}")
    print(f"{WHITE}{texto}{RESET}")
    print(SEPARADOR)


def combate_msg(texto: str): # Imprime mensajes del sistema de combate en rojo
    print(f"\n{SEPARADOR}")
    print(f"{BOLD}{RED}⚔️  Combate{RESET}")
    print(f"{WHITE}{texto}{RESET}")
    print(SEPARADOR)


def estado_combate(vida_actual: int, vida_max: int, enemigos_str: str): # Imprime la barra de estado del combate con vida y enemigos restantes
    print(f"\n{BOLD}{YELLOW}❤️  Vida: {vida_actual}/{vida_max}  |  👹 Enemigos: {enemigos_str}{RESET}\n")


def enemigo_msg(nombre: str, texto: str): # Imprime el ataque de un enemigo concreto con su nombre
    print(f"\n  {BOLD}{MAGENTA}🗡️  {nombre}{RESET}")
    print(f"  {WHITE}{texto}{RESET}")


def sistema_msg(texto: str): # Imprime mensajes del sistema como carga, menús o debug en azul
    print(f"\n{BOLD}{BLUE}⚙️  {texto}{RESET}")


def titulo_msg(texto: str): # Imprime un título con un marco de doble línea para secciones importantes
    borde = "═" * (len(texto) + 4) # El borde se ajusta al largo del texto
    print(f"\n{BOLD}{YELLOW}╔{borde}╗")
    print(f"║  {texto}  ║")
    print(f"╚{borde}╝{RESET}\n")


def victoria_msg(texto: str): # Imprime el mensaje de victoria en verde
    print(f"\n{BOLD}{GREEN}🏆 ¡Victoria!{RESET}")
    print(f"{GREEN}{texto}{RESET}\n")


def derrota_msg(texto: str): # Imprime el mensaje de derrota en rojo
    print(f"\n{BOLD}{RED}💀 Derrota...{RESET}")
    print(f"{RED}{texto}{RESET}\n")


# ── Helpers de streaming ────────────────────────────────────────────────────
# Se usan en triples inicio/chunk/fin: el caller imprime la cabecera con _inicio,
# va recibiendo trocitos del LLM y los imprime con _chunk, y cierra con _fin.
# Las versiones batch existentes (narrador_msg, combate_msg, etc.) siguen vivas
# para llamadas que no necesitan UI streaming (como la API REST).

def narrador_msg_inicio(): # Imprime el borde superior y la cabecera "📖 Narrador"
    print(f"\n{SEPARADOR}")
    print(f"{BOLD}{CYAN}📖 Narrador{RESET}")

def narrador_msg_chunk(texto: str): # Imprime un trozo de la narración del DM en color blanco, sin saltar de línea
    print(f"{WHITE}{texto}{RESET}", end="", flush=True)

def narrador_msg_fin(): # Cierra con un newline y el borde inferior
    print()
    print(SEPARADOR)


def combate_msg_inicio(): # Borde superior y cabecera "⚔️ Combate"
    print(f"\n{SEPARADOR}")
    print(f"{BOLD}{RED}⚔️  Combate{RESET}")

def combate_msg_chunk(texto: str): # Trozo de narración de combate en blanco, inline
    print(f"{WHITE}{texto}{RESET}", end="", flush=True)

def combate_msg_fin(): # Newline y borde inferior
    print()
    print(SEPARADOR)


def victoria_msg_inicio(): # Cabecera "🏆 ¡Victoria!" en verde, sin separador (igual que la versión batch)
    print(f"\n{BOLD}{GREEN}🏆 ¡Victoria!{RESET}")

def victoria_msg_chunk(texto: str): # Trozo de narración en verde, inline
    print(f"{GREEN}{texto}{RESET}", end="", flush=True)

def victoria_msg_fin(): # Cierre con newline extra para separar del siguiente bloque
    print("\n")


def derrota_msg_inicio(): # Cabecera "💀 Derrota..." en rojo
    print(f"\n{BOLD}{RED}💀 Derrota...{RESET}")

def derrota_msg_chunk(texto: str): # Trozo en rojo
    print(f"{RED}{texto}{RESET}", end="", flush=True)

def derrota_msg_fin():
    print("\n")


def enemigo_msg_inicio(nombre: str): # Cabecera con el nombre del enemigo, indentada y con la espada
    print(f"\n  {BOLD}{MAGENTA}🗡️  {nombre}{RESET}")
    print("  ", end="", flush=True) # Indentación inicial para que la primera línea de la narración quede alineada (líneas posteriores no se reindentan, igual que en la versión batch)

def enemigo_msg_chunk(texto: str): # Trozo de la acción del enemigo en blanco
    print(f"{WHITE}{texto}{RESET}", end="", flush=True)

def enemigo_msg_fin():
    print()


def prompt_jugador(texto: str = "¿Qué haces?") -> str: # Muestra el prompt del jugador y espera su input. Rechaza entradas vacías
    while True:
        respuesta = input(f"\n{BOLD}{GREEN}🧙 Tú > {RESET}").strip() # Quitamos espacios al principio y al final
        if respuesta:
            return respuesta
        print(f"{YELLOW}Escribe algo antes de pulsar Enter.{RESET}")


def prompt_input(texto: str) -> str: # Muestra un prompt genérico para pedir datos al jugador (menús, creación de personaje...). Rechaza entradas vacías
    while True:
        respuesta = input(f"{BOLD}{GREEN}> {RESET}{texto}: ").strip()
        if respuesta:
            return respuesta
        print(f"{YELLOW}Escribe algo antes de pulsar Enter.{RESET}")
