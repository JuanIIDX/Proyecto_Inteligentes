"""
Fábrica del modelo de lenguaje (Azure OpenAI).

Aísla la creación del LLM en un único lugar. Si en el futuro se cambia de
proveedor o de modelo, solo se modifica este archivo. El resto del sistema
trabaja contra la abstracción `BaseChatModel` de LangChain.
"""

from functools import lru_cache

from langchain_openai import AzureChatOpenAI

from app.core.config import settings


@lru_cache
def get_llm() -> AzureChatOpenAI:
    """
    Construye (una sola vez) la instancia de Azure OpenAI configurada.

    `azure_deployment` es el nombre del despliegue creado en Azure AI Foundry
    (no el nombre genérico del modelo, p. ej. "gpt-4o-mini-1").

    Se usa una temperatura baja por defecto (0.1) porque la tarea es de
    clasificación: queremos respuestas deterministas y consistentes, no
    creativas.
    """
    return AzureChatOpenAI(
        azure_endpoint=settings.azure_openai_endpoint,
        api_key=settings.azure_openai_api_key,
        azure_deployment=settings.azure_openai_deployment,
        api_version=settings.azure_openai_api_version,
        temperature=settings.llm_temperature,
    )
