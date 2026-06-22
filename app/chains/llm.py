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
    return AzureChatOpenAI(
        azure_endpoint=settings.azure_openai_endpoint,
        api_key=settings.azure_openai_api_key,
        azure_deployment=settings.azure_openai_deployment,
        api_version=settings.azure_openai_api_version,
        temperature=settings.llm_temperature,
    )
