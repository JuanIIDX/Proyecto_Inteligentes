"""
Fábrica del modelo de embeddings (Azure OpenAI).

Aísla la creación del modelo de embeddings en un único lugar, igual que
`llm.py` hace con el modelo de chat. Los embeddings convierten texto en
vectores numéricos: es lo que permite buscar por similitud semántica en el
vector store (pgvector) durante el paso de retrieval del RAG.

Reutiliza el mismo recurso de Azure OpenAI que el LLM, pero apuntando a un
deployment de embeddings distinto (p. ej. text-embedding-3-small).
"""

from functools import lru_cache

from langchain_openai import AzureOpenAIEmbeddings

from app.core.config import settings


@lru_cache
def get_embeddings() -> AzureOpenAIEmbeddings:
    """
    Construye (una sola vez) el modelo de embeddings de Azure OpenAI.

    `azure_deployment` es el nombre del despliegue de embeddings creado en
    Azure AI Foundry, no el nombre genérico del modelo. El mismo modelo debe
    usarse para indexar documentos y para consultar: si cambia, hay que
    reindexar, porque los vectores dejan de ser comparables.
    """
    return AzureOpenAIEmbeddings(
        azure_endpoint=settings.azure_openai_endpoint,
        api_key=settings.azure_openai_api_key,
        azure_deployment=settings.azure_openai_embeddings_deployment,
        api_version=settings.azure_openai_api_version,
    )
