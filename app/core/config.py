"""
Configuración centralizada de la aplicación.

Usa pydantic-settings para leer las variables de entorno desde el archivo .env
de forma tipada y validada. Es el único punto del sistema que conoce los
valores de configuración: cualquier otro módulo importa `settings` desde aquí.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Define y valida todas las variables de configuración del sistema."""

    # ---- Aplicación ----
    app_name: str = "Sistema Inteligente de Solicitudes Universitarias"
    app_env: str = "development"

    # ---- Azure OpenAI ----
    azure_openai_api_key: str
    azure_openai_endpoint: str
    azure_openai_deployment: str
    azure_openai_api_version: str = "2024-10-21"
    llm_temperature: float = 0.1

    # ---- RAG (Retrieval-Augmented Generation) ----
    # Activa/desactiva el paso de recuperación de contexto en la cadena. Por
    # defecto está en True: /solicitudes siempre consulta la normativa/histórico
    # del vector store antes de clasificar. Se puede desactivar con RAG_ENABLED=False
    # en el .env si se quiere clasificar sin RAG.
    rag_enabled: bool = True
    # Deployment del modelo de embeddings en Azure (p. ej. text-embedding-3-small).
    azure_openai_embeddings_deployment: str = "text-embedding-3-small"
    # Nombre de la colección de pgvector donde se guardan los documentos indexados.
    rag_collection_name: str = "documentos_universitarios"
    # Número de fragmentos que el retriever inyecta como contexto en el prompt.
    rag_top_k: int = 3

    # ---- Base de datos (Azure Database for PostgreSQL) ----
    database_url: str

    # Lee el archivo .env, ignora variables extra y es insensible a mayúsculas.
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """
    Devuelve una instancia única (cacheada) de Settings.

    El decorador lru_cache garantiza que el .env se lea una sola vez durante
    todo el ciclo de vida del proceso, evitando lecturas repetidas a disco.
    """
    return Settings()


# Instancia global lista para importar: `from app.core.config import settings`
settings = get_settings()
