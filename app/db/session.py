"""
Engine de SQLAlchemy para Azure Database for PostgreSQL.

Sustituye al cliente de Supabase: aquí trabajamos con SQL directo a través de
SQLAlchemy Core (sin ORM), usando un único Engine (pool de conexiones)
compartido por toda la aplicación.
"""

from functools import lru_cache

from sqlalchemy import Engine, create_engine

from app.core.config import settings


@lru_cache
def get_engine() -> Engine:
    """
    Devuelve una instancia única (cacheada) del Engine de SQLAlchemy.

    El Engine mantiene un pool de conexiones hacia Azure Database for
    PostgreSQL; se crea una sola vez y se reutiliza en toda la app.
    """
    return create_engine(settings.database_url, pool_pre_ping=True)
