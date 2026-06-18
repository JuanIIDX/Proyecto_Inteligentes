"""
Cliente de Supabase.

Con supabase-py NO usamos un ORM ni una sesión SQL tradicional: trabajamos
contra la API REST de Supabase a través de un único cliente. Este módulo crea
ese cliente una sola vez (cacheado) y lo expone para que los repositorios lo
reutilicen.
"""

from functools import lru_cache

from supabase import Client, create_client

from app.core.config import settings


@lru_cache
def get_supabase() -> Client:
    """
    Devuelve una instancia única (cacheada) del cliente de Supabase.

    Usa la SUPABASE_KEY (service_role en el backend), lo que permite operar
    sobre las tablas saltando las políticas RLS desde el servidor.
    """
    return create_client(settings.supabase_url, settings.supabase_key)
