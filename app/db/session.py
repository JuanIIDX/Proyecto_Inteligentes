"""
Engine de SQLAlchemy para Azure Database for PostgreSQL.

Sustituye al cliente de Supabase: aquí trabajamos con SQL directo a través de
SQLAlchemy Core (sin ORM), usando un único Engine (pool de conexiones)
compartido por toda la aplicación.
"""

import logging
from functools import lru_cache

from sqlalchemy import Engine, create_engine, text

from app.core.config import settings

logger = logging.getLogger(__name__)


@lru_cache
def get_engine() -> Engine:
    """
    Devuelve una instancia única (cacheada) del Engine de SQLAlchemy.

    El Engine mantiene un pool de conexiones hacia Azure Database for
    PostgreSQL; se crea una sola vez y se reutiliza en toda la app.
    """
    return create_engine(settings.database_url, pool_pre_ping=True)


def asegurar_extension_vector() -> None:
    """
    Crea la extensión 'vector' (pgvector) si aún no existe.

    Es lo único que pgvector no puede crear por sí solo, y normalmente se hace
    con un cliente SQL. Aquí se ejecuta al arrancar la app (solo si RAG está
    activado) para no depender de herramientas externas.

    Requiere que 'vector' esté PERMITIDA a nivel de servidor en Azure (parámetro
    azure.extensions). Si no lo está, este CREATE EXTENSION fallará: por eso se
    registra el error pero no se detiene el arranque de la aplicación.
    """
    try:
        with get_engine().begin() as conn:
            conn.execute(text("create extension if not exists vector"))
        logger.info("Extensión pgvector verificada/creada correctamente.")
    except Exception:
        logger.exception(
            "No se pudo crear la extensión 'vector'. Revisa que esté habilitada "
            "en azure.extensions (Server parameters) en el portal de Azure."
        )
