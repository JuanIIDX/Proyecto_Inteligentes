"""
Punto de entrada de la aplicación FastAPI.

Responsabilidades:
  - Configurar el logging.
  - Inicializar la base de datos (crear tablas + seed de responsables) al
    arrancar, mediante el lifespan de FastAPI.
  - Montar los routers de la API.
  - Exponer un endpoint de salud (/health) y la documentación interactiva
    en /docs.

Ejecutar:  uvicorn app.main:app --reload
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes_documentos import router as documentos_router
from app.api.routes_solicitudes import router as solicitudes_router
from app.core.config import settings
from app.core.logging_config import setup_logging

setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Se ejecuta al arrancar y al apagar la aplicación."""
    logger.info("Iniciando %s ...", settings.app_name)
    # Las tablas de Supabase se crean ejecutando _private/db/schema.sql en el
    # SQL Editor del proyecto (una sola vez), no desde la aplicación.
    # Si RAG está activado, nos aseguramos de que la extensión pgvector exista
    # para no depender de un cliente SQL externo.
    if settings.rag_enabled:
        from app.db.session import asegurar_extension_vector

        asegurar_extension_vector()
    logger.info("Aplicación lista.")
    yield
    logger.info("Apagando la aplicación.")


app = FastAPI(
    title=settings.app_name,
    description=(
        "Sistema Inteligente de Clasificación, Priorización y Asignación de "
        "Solicitudes Universitarias mediante IA (LangChain + Azure OpenAI) y "
        "Optimización Heurística."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# Habilita que la página HTML de prueba (servida desde otro origen, p. ej.
# file:// o un servidor estático local) pueda llamar a esta API desde el
# navegador. Es solo para desarrollo local del proyecto académico.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(solicitudes_router)
app.include_router(documentos_router)


@app.get("/health", tags=["Sistema"], summary="Estado del servicio")
def health() -> dict[str, str]:
    """Verifica que el servicio está activo."""
    return {"status": "ok", "app": settings.app_name}
