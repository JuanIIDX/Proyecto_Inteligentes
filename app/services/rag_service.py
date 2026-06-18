"""
Servicio de preguntas y respuestas sobre los documentos (RAG puro).

Aísla el flujo "pregunta -> recuperar contexto -> responder con el LLM" para
poder probar el RAG de forma independiente de la clasificación de solicitudes.
Es lo que usa el endpoint POST /rag/preguntar.

Flujo:
    pregunta -> retrieval (fragmentos relevantes) -> prompt + LLM -> respuesta
    Devuelve también las 'fuentes' (de qué documentos salió el contexto) para
    que la respuesta sea verificable.
"""

import logging

from langchain_core.prompts import ChatPromptTemplate

from app.chains.llm import get_llm
from app.chains.retriever import buscar_con_score
from app.core.config import settings

logger = logging.getLogger(__name__)

_SISTEMA_QA = """\
Eres un asistente de la Universidad de Caldas que responde preguntas basándose
ÚNICAMENTE en el CONTEXTO proporcionado (normativa, reglamentos o documentos
institucionales).

Reglas:
1. Responde solo con la información del CONTEXTO. No inventes datos.
2. Si el contexto no contiene la respuesta, dilo claramente: "No encuentro esa
   información en los documentos disponibles."
3. Sé claro y conciso. Responde en español.
"""

_HUMANO_QA = """\
CONTEXTO:
{contexto}

PREGUNTA: {pregunta}
"""


def preguntar(pregunta: str) -> dict[str, object]:
    """
    Responde una pregunta usando los documentos indexados (RAG).

    1) Recupera los fragmentos más relevantes del vector store.
    2) Se los pasa al LLM como contexto para que redacte la respuesta.
    3) Devuelve la respuesta y la lista de fuentes (documentos) usadas.

    Si no hay ningún fragmento relevante, no llama al LLM: avisa de que no hay
    documentos que respondan la pregunta.
    """
    fragmentos = buscar_con_score(pregunta, k=settings.rag_top_k)

    if not fragmentos:
        return {
            "pregunta": pregunta,
            "respuesta": "No hay documentos indexados que respondan esta pregunta.",
            "fuentes": [],
        }

    contexto = "\n\n---\n\n".join(str(f["contenido"]) for f in fragmentos)
    # Fuentes únicas, conservando el orden de aparición.
    fuentes = list(dict.fromkeys(str(f["fuente"]) for f in fragmentos))

    prompt = ChatPromptTemplate.from_messages(
        [("system", _SISTEMA_QA), ("human", _HUMANO_QA)]
    )
    cadena = prompt | get_llm()
    respuesta = cadena.invoke({"contexto": contexto, "pregunta": pregunta})

    logger.info("Pregunta RAG respondida usando fuentes: %s", fuentes)
    return {
        "pregunta": pregunta,
        "respuesta": respuesta.content,
        "fuentes": fuentes,
    }
