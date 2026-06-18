"""
Endpoints REST para la gestión de documentos del RAG.

Permite que el frontend suba documentos (normativa, reglamentos, históricos) que
el sistema indexa en el vector store. A partir de ese momento, las solicitudes
clasificadas con RAG activado pueden usar esos documentos como contexto.

Igual que el resto de la API, esta capa es delgada: valida la entrada y delega
en DocumentoService.
"""

import logging

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from app.services.documento_service import DocumentoService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Documentos (RAG)"])


@router.post(
    "/documentos",
    status_code=status.HTTP_201_CREATED,
    summary="Subir e indexar un documento para el contexto de la IA (RAG)",
)
async def subir_documento(archivo: UploadFile = File(...)) -> dict[str, int | str]:
    """
    Recibe un documento (.txt o .md), lo fragmenta, genera sus embeddings con
    Azure OpenAI y lo guarda en el vector store (pgvector).

    Tras subirlo, la IA podrá recuperar su contenido como contexto al clasificar
    solicitudes (requiere RAG_ENABLED=true).
    """
    contenido = await archivo.read()
    service = DocumentoService()
    try:
        return service.indexar(archivo.filename or "documento", contenido)
    except ValueError as exc:
        # Formato no soportado o archivo vacío: error del cliente.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    except Exception as exc:  # noqa: BLE001
        # Fallo al generar embeddings o al escribir en pgvector.
        logger.exception("Error indexando el documento")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"No se pudo indexar el documento: {exc}",
        ) from exc
