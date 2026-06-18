"""
Cadena de clasificación construida con LCEL (LangChain Expression Language).

Esta es la pieza central de IA del sistema. Orquesta tres pasos:

    1) ChatPromptTemplate  -> arma el prompt con asunto y descripción.
    2) LLM estructurado     -> Azure OpenAI devuelve un ClasificacionResult
                               (categoría + prioridad + razonamiento).
    3) RunnableLambda        -> invoca la Tool `asignar_responsable` para
                               añadir el responsable según la categoría.

El operador `|` de LCEL conecta los pasos como un pipeline declarativo. La
salida final es un diccionario con la clasificación y el responsable, listo
para persistir y devolver por la API.

RAG: antes de armar el prompt, un paso previo recupera contexto (normativa
universitaria o solicitudes históricas) desde el vector store de pgvector y lo
inyecta en la variable {contexto}. Este paso se activa con `settings.rag_enabled`:
si está desactivado, se rellena {contexto} con un texto neutro y el sistema se
comporta como un clasificador puro, sin tocar la base vectorial.
"""

import logging
from functools import lru_cache
from typing import Any

from langchain_core.runnables import Runnable, RunnableLambda

from app.chains.llm import get_llm
from app.chains.prompts import get_clasificacion_prompt
from app.chains.tools import asignar_responsable_seguro
from app.core.config import settings
from app.schemas.solicitud import ClasificacionResult

logger = logging.getLogger(__name__)

# Texto usado como {contexto} cuando RAG está desactivado: mantiene el prompt
# válido sin afirmar nada que el LLM pueda tomar como normativa.
_CONTEXTO_VACIO = "Sin contexto adicional. Clasifica solo con la solicitud."


def _preparar_entrada(data: dict[str, Any]) -> dict[str, Any]:
    """
    Primer paso de la cadena: añade la variable {contexto} a la entrada.

    Si RAG está activo, recupera normativa/histórico relevante desde el vector
    store usando asunto + descripción como consulta. Si no, usa un contexto
    neutro. Se importa el retriever de forma perezosa para que el módulo no
    dependa de pgvector cuando RAG está apagado.
    """
    if not settings.rag_enabled:
        return {**data, "contexto": _CONTEXTO_VACIO}

    from app.chains.retriever import construir_consulta, get_contexto_runnable

    consulta = construir_consulta(data["asunto"], data["descripcion"])
    try:
        contexto = get_contexto_runnable().invoke(consulta)
    except Exception:
        # Si el vector store falla (sin extensión, sin documentos, etc.) no
        # rompemos la clasificación: degradamos a contexto vacío y avisamos.
        logger.exception("Fallo al recuperar contexto RAG; se clasifica sin él.")
        contexto = _CONTEXTO_VACIO

    return {**data, "contexto": contexto}


def _agregar_responsable(data: dict[str, Any]) -> dict[str, Any]:
    """
    Paso de LCEL: toma la clasificación del LLM e invoca la Tool de asignación.

    Recibe {'clasificacion': ClasificacionResult} y devuelve un diccionario
    enriquecido con el responsable asignado.
    """
    clasificacion: ClasificacionResult = data["clasificacion"]
    responsable = asignar_responsable_seguro(clasificacion.categoria)

    logger.info(
        "Clasificación -> categoria=%s prioridad=%s responsable=%s",
        clasificacion.categoria.value,
        clasificacion.prioridad.value,
        responsable,
    )

    return {
        "categoria": clasificacion.categoria,
        "prioridad": clasificacion.prioridad,
        "razonamiento": clasificacion.razonamiento,
        "responsable": responsable,
    }


@lru_cache
def get_clasificacion_chain() -> Runnable:
    """
    Construye y cachea la cadena LCEL completa.

    Pipeline:
        _preparar_entrada (añade {contexto} vía RAG)
                                     -> prompt | llm_estructurado
                                     -> ClasificacionResult
                                     -> {'clasificacion': ...}
                                     -> _agregar_responsable
    """
    prompt = get_clasificacion_prompt()

    # with_structured_output fuerza al LLM a responder con el esquema
    # ClasificacionResult, eliminando la necesidad de parsear texto a mano.
    llm_estructurado = get_llm().with_structured_output(ClasificacionResult)

    # Subcadena: recupera contexto -> prompt -> LLM. El resultado se etiqueta
    # como 'clasificacion'.
    clasificador: Runnable = (
        RunnableLambda(_preparar_entrada)
        | prompt
        | llm_estructurado
        | RunnableLambda(lambda r: {"clasificacion": r})
    )

    # Cadena final: clasifica y luego asigna el responsable vía Tool.
    return clasificador | RunnableLambda(_agregar_responsable)


def clasificar_solicitud(asunto: str, descripcion: str) -> dict[str, Any]:
    """
    Punto de entrada de alto nivel para clasificar una solicitud.

    Ejecuta la cadena LCEL y devuelve un diccionario con:
    categoria, prioridad, razonamiento y responsable.
    """
    chain = get_clasificacion_chain()
    return chain.invoke({"asunto": asunto, "descripcion": descripcion})
