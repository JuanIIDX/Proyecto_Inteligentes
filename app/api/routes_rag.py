"""
Endpoints REST de RAG (Retrieval-Augmented Generation).

Agrupa, bajo el prefijo /rag, todo lo necesario para PROBAR y usar el RAG de
forma aislada de la clasificación de solicitudes:

    POST /rag/documentos     -> subir e indexar un documento
    GET  /rag/documentos     -> listar los documentos indexados
    GET  /rag/buscar?q=...    -> ver qué fragmentos recupera (sin pasar por la IA)
    POST /rag/preguntar      -> preguntar y que la IA responda con los documentos

Igual que el resto de la API, esta capa es delgada: valida la entrada y delega
en los servicios y en el módulo de retriever.
"""

import logging

from fastapi import APIRouter, File, HTTPException, Query, UploadFile, status

from app.chains.retriever import buscar_con_score, listar_documentos
from app.schemas.rag import (
    BusquedaResponse,
    DocumentoIndexado,
    FragmentoRecuperado,
    PreguntaRequest,
    RespuestaRAG,
)
from app.services.documento_service import DocumentoService
from app.services.rag_service import preguntar as responder_pregunta

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/rag", tags=["RAG"])


@router.post(
    "/documentos",
    status_code=status.HTTP_201_CREATED,
    summary="Subir e indexar un documento (RAG)",
)
async def subir_documento(archivo: UploadFile = File(...)) -> dict[str, int | str]:
    """
    Recibe un documento (.txt o .md), lo fragmenta, genera sus embeddings con
    Azure OpenAI y lo guarda en el vector store (pgvector). Tras subirlo, la IA
    podrá usar su contenido como contexto.
    """
    contenido = await archivo.read()
    service = DocumentoService()
    try:
        return service.indexar(archivo.filename or "documento", contenido)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("Error indexando el documento")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"No se pudo indexar el documento: {exc}",
        ) from exc


@router.get(
    "/documentos",
    response_model=list[DocumentoIndexado],
    summary="Listar documentos indexados en el vector store",
)
def get_documentos() -> list[DocumentoIndexado]:
    """Devuelve los documentos indexados y cuántos fragmentos tiene cada uno."""
    return [DocumentoIndexado(**d) for d in listar_documentos()]


@router.get(
    "/buscar",
    response_model=BusquedaResponse,
    summary="Recuperar fragmentos relevantes (retrieval, sin LLM)",
)
def buscar(
    q: str = Query(..., min_length=1, description="Texto a buscar en los documentos"),
    k: int | None = Query(None, ge=1, le=20, description="Nº de fragmentos a traer"),
) -> BusquedaResponse:
    """
    Muestra los fragmentos que el retrieval recupera para una consulta, con su
    score de similitud. NO llama a la IA: sirve para ver/demostrar exactamente
    qué recupera el vector store.
    """
    try:
        fragmentos = buscar_con_score(q, k=k)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Error en la búsqueda RAG")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"No se pudo buscar en los documentos: {exc}",
        ) from exc
    return BusquedaResponse(
        consulta=q,
        fragmentos=[FragmentoRecuperado(**f) for f in fragmentos],
    )


@router.post(
    "/preguntar",
    response_model=RespuestaRAG,
    summary="Preguntar a la IA usando los documentos como contexto",
)
def preguntar(payload: PreguntaRequest) -> RespuestaRAG:
    """
    Recupera los fragmentos relevantes y deja que la IA responda la pregunta
    basándose en ellos. Devuelve la respuesta y las fuentes usadas.
    """
    try:
        resultado = responder_pregunta(payload.pregunta)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Error respondiendo la pregunta RAG")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"No se pudo responder la pregunta: {exc}",
        ) from exc
    return RespuestaRAG(**resultado)
