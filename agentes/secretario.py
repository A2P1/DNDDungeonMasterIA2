import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from typing import Optional
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from config import DIARIO_PATH, SECRETARIO_MODEL, SECRETARIO_PROMPT_PATH # FIX-15: modelo configurable por agente

load_dotenv()


class NPC(BaseModel):
    nombre: str
    rol: Optional[str] = None
    ubicacion: Optional[str] = None
    estado: Optional[str] = None


class Diario(BaseModel): # Memoria estructurada a largo plazo. Crece poco y nunca se borra.
    npcs: dict[str, NPC] = Field(default_factory=dict) # indexados por nombre en minúsculas
    decisiones: list[str] = Field(default_factory=list)
    promesas_abiertas: list[str] = Field(default_factory=list)
    promesas_cumplidas: list[str] = Field(default_factory=list)
    items: list[str] = Field(default_factory=list)
    lugares: list[str] = Field(default_factory=list)
    hechos: list[str] = Field(default_factory=list)


class DeltaDiario(BaseModel): # Lo que devuelve el secretario tras cada turno. Listas vacías = nada que añadir.
    npcs: list[NPC] = Field(default_factory=list)
    decisiones: list[str] = Field(default_factory=list)
    nuevas_promesas: list[str] = Field(default_factory=list)
    promesas_cumplidas: list[str] = Field(default_factory=list)
    items: list[str] = Field(default_factory=list)
    lugares: list[str] = Field(default_factory=list)
    hechos: list[str] = Field(default_factory=list)


def cargar_diario() -> Diario:
    if not DIARIO_PATH.exists():
        return Diario()
    return Diario.model_validate_json(DIARIO_PATH.read_text(encoding='utf-8'))


def guardar_diario(d: Diario) -> None:
    DIARIO_PATH.parent.mkdir(parents=True, exist_ok=True)
    DIARIO_PATH.write_text(d.model_dump_json(indent=2, exclude_none=True), encoding='utf-8')


def aplicar_delta(d: Diario, delta: DeltaDiario) -> Diario: # Muta el diario con los cambios del delta
    for npc in delta.npcs: # merge: si ya existe, fusiona los campos no-None
        clave = npc.nombre.lower()
        existente = d.npcs.get(clave)
        d.npcs[clave] = existente.model_copy(update=npc.model_dump(exclude_none=True)) if existente else npc
    d.decisiones.extend(delta.decisiones)
    for p in delta.nuevas_promesas:
        if p not in d.promesas_abiertas:
            d.promesas_abiertas.append(p)
    for p in delta.promesas_cumplidas:
        if p in d.promesas_abiertas:
            d.promesas_abiertas.remove(p)
        if p not in d.promesas_cumplidas:
            d.promesas_cumplidas.append(p)
    d.items.extend(delta.items)
    for l in delta.lugares:
        if l not in d.lugares:
            d.lugares.append(l)
    d.hechos.extend(delta.hechos)
    return d


# ── Agente LLM ──────────────────────────────────────────────────────────────

with open(SECRETARIO_PROMPT_PATH, 'r', encoding='utf-8') as f:
    _PROMPT = f.read().strip()

_llm = ChatOpenAI(model=SECRETARIO_MODEL, temperature=0.2).with_structured_output(DeltaDiario) # Temperatura baja: queremos fidelidad, no creatividad


def extraer_delta(accion: str, narracion: str, diario: Diario) -> DeltaDiario: # Llama al LLM para extraer el delta del turno
    return _llm.invoke([
        SystemMessage(content=_PROMPT),
        HumanMessage(content=(
            f"Diario actual:\n{diario.model_dump_json(indent=2, exclude_none=True)}\n\n"
            f"Acción del jugador: {accion}\n\n"
            f"Narración generada: {narracion}"
        ))
    ])
