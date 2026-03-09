import random
from langchain_core.tools import tool

@tool
def d20(): # Dado de 20 caras para atacar, escabullirse, defenderse, etc.
    '''Útil para acciones como atacar, defenderse, escabullirse, realizar acciones de habilidad, etc. También sirve para intentar huir de un combate.'''
    random_num = random.randint(1, 20)
    print(random_num)
    return random_num
@tool
def d8(): # Dado de 8 caras para daño de golpes más fuertes o hechizos más poderosos
    '''Útil para calcular el daño de armas fuertes, tanto con espadas, hechizos, etc.'''
    tirada_ataque = d20.invoke({}) 
    if tirada_ataque > 10: # Si el ataque tiene éxito, tiramos el d8 para calcular el daño
        random_num = random.randint(1, 8)
        print(random_num)
        return random_num
    else:
        return 0
@tool
def d4(): # Dado de 4 caras para el daño de armas pequeñas, hechizos menores, etc.
    '''Útil para calcular el daño de armas más débiles, como ataques con dagas, hechizos menores, etc.'''
    tirada_ataque = d20.invoke({}) 
    if tirada_ataque > 10: # Si el ataque tiene éxito, tiramos el d4 para calcular el daño
        random_num = random.randint(1, 4)
        print(random_num)
        return random_num
    else:
        return 0