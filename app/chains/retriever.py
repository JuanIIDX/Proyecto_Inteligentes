"""
Vector store y retriever (RAG) sobre Azure Database for PostgreSQL + pgvector.

Este módulo es la capa de "Persistencia y RAG" del sistema:

  - VECTOR STORE: usa `PGVector` de langchain-postgres, que guarda los vectores
    en la MISMA base de datos PostgreSQL de Azure que ya usa la app (no hace
    falta una base de datos aparte). Requiere la extensión `vector` instalada
    (ver _private/db/migracion_rag.sql).

  - DOCUMENTOS INDEXADOS: normativa universitaria, reglamentos o solicitudes
    históricas. Se cargan con scripts/ingestar_documentos.py.

  - ESTRATEGIA DE RETRIEVAL: búsqueda por similitud semántica (coseno). El
    retriever recupera los `rag_top_k` fragmentos más parecidos a la solicitud
    y los inyecta como contexto en el prompt de clasificación.

Toda la creación queda cacheada para reutilizar la conexión y el modelo de
embeddings durante la vida del proceso.
"""

import logging
from functools import lru_cache

from langchain_core.documents import Document
from langchain_core.runnables import Runnable, RunnableLambda
from langchain_postgres import PGVector

from app.chains.embeddings import get_embeddings
from app.core.config import settings

logger = logging.getLogger(__name__)


@lru_cache
def get_vector_store() -> PGVector:
    """
    Construye (una sola vez) el vector store de pgvector.

    `use_jsonb=True` guarda los metadatos como JSONB (formato recomendado).
    La conexión reutiliza `database_url`; PGVector espera el driver psycopg,
    que ya es el que usa el resto de la app.
    """
    return PGVector(
        embeddings=get_embeddings(),
        collection_name=settings.rag_collection_name,
        connection=settings.database_url,
        use_jsonb=True,
    )


@lru_cache
def get_retriever() -> Runnable:
    """
    Devuelve el retriever configurado para búsqueda por similitud.

    Recupera los `rag_top_k` documentos más relevantes para la consulta. Se
    expone como Runnable para encajarlo directamente en la cadena LCEL.
    """
    return get_vector_store().as_retriever(
        search_type="similarity",
        search_kwargs={"k": settings.rag_top_k},
    )


def _formatear_documentos(documentos: list[Document]) -> str:
    """Une los fragmentos recuperados en un único bloque de texto para el prompt."""
    if not documentos:
        return "No se encontró normativa o histórico relevante para esta solicitud."
    return "\n\n---\n\n".join(doc.page_content for doc in documentos)


@lru_cache
def get_contexto_runnable() -> Runnable:
    """
    Runnable que, dada la consulta, devuelve el contexto ya formateado (str).

    Encadena: consulta -> retriever (documentos) -> texto formateado. Es la
    pieza que la cadena de clasificación inserta como variable {contexto}.
    """
    return get_retriever() | RunnableLambda(_formatear_documentos)


def construir_consulta(asunto: str, descripcion: str) -> str:
    """
    Construye el texto de búsqueda a partir de asunto y descripción.

    Se concatenan ambos campos porque juntos describen mejor la solicitud y
    mejoran la recuperación semántica frente a usar solo uno.
    """
    return f"{asunto}\n{descripcion}"
