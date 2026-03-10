import random
from langchain_core.tools import tool


@tool
def dados_ataque(tipodado: int):
    """
    Ejecuta esta función para tirar dados en situaciones de combate contra enemigos. El tipo de dado dependerá del arma que esté utilizando el jugador:
    - D4: Armas pequeñas como dagas, ballestas ligeras, hechizos menores, etc.
    - D8: Armas medianas como espadas largas, hachas, ballestas pesadas, hechizos de daño moderado, etc.

    Si 'resultado_dado' es mayor a 10, en el return devuelve el resultado como el daño que se le ha infligido al enemigo
    Si 'resultado_dado' es menor o igual a 10, en el return devuelve el resultado como un fallo en el ataque
    
    """
    print(tipodado)
    resultado_dado = dados_situacion.invoke({})
    if resultado_dado > 10:
        resultado = random.randint(1, tipodado)
        return resultado
    return resultado_dado

@tool
def dados_situacion(dificultad: int):
    """
    Ejecuta esta función para tirar dados en situaciones en las que el jugador deba superar un obstáculo o desafío que no sea un combate directo, como por ejemplo saltar algo, caminar sigilosamente, correr muchísimo, etc
    La dificultad dependerá de la complejidad del obstáculo o desafío al que el jugador está expuesto, pero el baremo por lo general irá desde 5 a 15
    Si 'resultado' es mayor a la dificultad establecida, en el return devuelve el resultado como un éxito del obsáculo o desafío realizado por el jugador
    Si 'resultado' es menor o igual a la dificultad establecida, en el return devuelve el resultado como un fracaso del obsáculo o desafío realizado por el jugador
    """
    
    resultado = random.randint(1, 20)
    print(dificultad)
    print(resultado)
    if resultado > dificultad:
        return resultado
    return resultado

