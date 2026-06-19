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
from sqlalchemy import text

from app.chains.embeddings import get_embeddings
from app.core.config import settings
from app.db.session import get_engine

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


def recuperar_contexto_con_fuentes(consulta: str) -> tuple[str, list[str]]:
    """
    Recupera el contexto formateado Y la lista de fuentes (documentos) usadas.

    A diferencia de `get_contexto_runnable` (que solo devuelve el texto), aquí se
    exponen también los nombres de los documentos de los que salió el contexto.
    Esto permite que la clasificación informe SI se apoyó en algún documento y en
    cuál, haciendo la justificación verificable.

    Devuelve (contexto_formateado, fuentes). Si no se recuperó nada, las fuentes
    vienen vacías y el contexto es el texto neutro de "sin normativa relevante".
    """
    documentos: list[Document] = get_retriever().invoke(consulta)
    contexto = _formatear_documentos(documentos)
    # Fuentes únicas, conservando el orden de aparición.
    fuentes = list(
        dict.fromkeys(
            str(doc.metadata.get("fuente", "desconocida")) for doc in documentos
        )
    )
    return contexto, fuentes


def construir_consulta(asunto: str, descripcion: str) -> str:
    """
    Construye el texto de búsqueda a partir de asunto y descripción.

    Se concatenan ambos campos porque juntos describen mejor la solicitud y
    mejoran la recuperación semántica frente a usar solo uno.
    """
    return f"{asunto}\n{descripcion}"


def buscar_con_score(consulta: str, k: int | None = None) -> list[dict[str, object]]:
    """
    Recupera los fragmentos más parecidos a la consulta CON su puntuación.

    A diferencia del retriever (que solo devuelve documentos), aquí se expone
    también la distancia/score de cada fragmento. Sirve para inspeccionar y
    demostrar el retrieval: ver QUÉ se recuperó y CUÁN parecido era, sin que el
    LLM intervenga.

    pgvector devuelve una "distancia" (menor = más parecido). Se reporta tal
    cual en 'score' junto con el contenido y la fuente.
    """
    top_k = k or settings.rag_top_k
    resultados = get_vector_store().similarity_search_with_score(consulta, k=top_k)
    return [
        {
            "contenido": doc.page_content,
            "fuente": doc.metadata.get("fuente", "desconocida"),
            "score": float(score),
        }
        for doc, score in resultados
    ]


def listar_documentos() -> list[dict[str, object]]:
    """
    Devuelve los documentos indexados, agrupados por su nombre de archivo.

    Consulta la tabla `langchain_pg_embedding` (la que crea PGVector) y agrupa
    por la 'fuente' guardada en los metadatos JSONB, contando cuántos fragmentos
    tiene cada documento. Sirve para ver qué hay cargado en el vector store.

    Si la tabla aún no existe (no se ha indexado nada todavía), devuelve [].
    """
    sql = text(
        """
        select cmetadata->>'fuente' as fuente, count(*) as fragmentos
        from langchain_pg_embedding
        group by cmetadata->>'fuente'
        order by fuente
        """
    )
    try:
        with get_engine().connect() as conn:
            filas = conn.execute(sql).mappings().all()
    except Exception:
        # La tabla no existe todavía: nada indexado aún.
        logger.info("Aún no hay documentos indexados (tabla de vectores vacía).")
        return []
    return [
        {"fuente": fila["fuente"], "fragmentos": fila["fragmentos"]} for fila in filas
    ]
