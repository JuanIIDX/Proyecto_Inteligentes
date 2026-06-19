"""
Endpoints REST del sistema.

La capa API es deliberadamente delgada: valida la entrada (vía Pydantic),
delega toda la lógica en el servicio y serializa la salida. No contiene reglas
de negocio ni acceso directo a Supabase.
"""

import logging

from fastapi import APIRouter, HTTPException, status

from app.schemas.solicitud import (
    ComparacionTecnicasResponse,
    FuncionarioResponse,
    OptimizacionResponse,
    SolicitudRequest,
    SolicitudResponse,
    SolicitudUpdate,
)
from app.services.solicitud_service import SolicitudService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Solicitudes"])


# ---------------------------------------------------------------------- #
#  Solicitudes
# ---------------------------------------------------------------------- #
@router.post(
    "/solicitudes",
    response_model=SolicitudResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear y clasificar una solicitud",
)
def crear_solicitud(payload: SolicitudRequest) -> SolicitudResponse:
    """
    Recibe una solicitud, la clasifica y prioriza con IA (Azure OpenAI + LangChain),
    le asigna un responsable mediante la Tool, la almacena en Supabase y crea
    la asignación al funcionario correspondiente.
    """
    service = SolicitudService()
    try:
        solicitud = service.procesar(payload)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Error procesando la solicitud")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"No se pudo procesar la solicitud: {exc}",
        ) from exc
    return SolicitudResponse.model_validate(solicitud)


@router.get(
    "/solicitudes",
    response_model=list[SolicitudResponse],
    summary="Listar historial de solicitudes",
)
def listar_solicitudes(limite: int = 50) -> list[SolicitudResponse]:
    """Devuelve las solicitudes más recientes procesadas por el sistema."""
    service = SolicitudService()
    return [SolicitudResponse.model_validate(s) for s in service.listar(limite)]


@router.get(
    "/solicitudes/{solicitud_id}",
    response_model=SolicitudResponse,
    summary="Obtener una solicitud por id",
)
def obtener_solicitud(solicitud_id: int) -> SolicitudResponse:
    """Devuelve una solicitud específica por su identificador."""
    service = SolicitudService()
    solicitud = service.obtener(solicitud_id)
    if solicitud is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Solicitud no encontrada."
        )
    return SolicitudResponse.model_validate(solicitud)


@router.patch(
    "/solicitudes/{solicitud_id}",
    response_model=SolicitudResponse,
    summary="Actualizar una solicitud",
)
def actualizar_solicitud(
    solicitud_id: int, payload: SolicitudUpdate
) -> SolicitudResponse:
    """Actualiza campos de una solicitud (estado, categoría, etc.)."""
    service = SolicitudService()
    solicitud = service.actualizar(solicitud_id, payload)
    if solicitud is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Solicitud no encontrada."
        )
    return SolicitudResponse.model_validate(solicitud)


# ---------------------------------------------------------------------- #
#  Optimización (A*)
# ---------------------------------------------------------------------- #
@router.post(
    "/optimizar-asignaciones",
    response_model=OptimizacionResponse,
    summary="Asignar de forma óptima el lote de solicitudes pendientes (A*)",
)
def optimizar_asignaciones() -> OptimizacionResponse:
    """
    Ejecuta búsqueda A* sobre todas las solicitudes en estado 'pendiente',
    eligiendo para cada una el funcionario que minimiza el costo total del
    lote (carga + tiempo de respuesta + urgencia desalineada), persiste las
    asignaciones resultantes y devuelve las métricas de la búsqueda.
    """
    service = SolicitudService()
    try:
        resultado = service.optimizar_asignaciones()
    except Exception as exc:  # noqa: BLE001
        logger.exception("Error optimizando asignaciones")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"No se pudo optimizar las asignaciones: {exc}",
        ) from exc
    return OptimizacionResponse.model_validate(resultado, from_attributes=True)


@router.post(
    "/comparar-tecnicas",
    response_model=ComparacionTecnicasResponse,
    summary="Comparar A* vs BFS/DFS vs Algoritmo Genético sobre el lote pendiente",
)
def comparar_tecnicas() -> ComparacionTecnicasResponse:
    """
    Resuelve el mismo lote de solicitudes pendientes con las cuatro técnicas
    (A*, BFS, DFS y genético) y devuelve sus métricas para comparar y graficar.

    Es solo evaluación: NO persiste asignaciones ni cambia estados.
    """
    service = SolicitudService()
    try:
        resultado = service.comparar_tecnicas()
    except Exception as exc:  # noqa: BLE001
        logger.exception("Error comparando técnicas")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"No se pudo comparar las técnicas: {exc}",
        ) from exc
    return ComparacionTecnicasResponse.model_validate(resultado, from_attributes=True)


# ---------------------------------------------------------------------- #
#  Funcionarios
# ---------------------------------------------------------------------- #
@router.get(
    "/funcionarios",
    response_model=list[FuncionarioResponse],
    summary="Listar funcionarios",
)
def listar_funcionarios() -> list[FuncionarioResponse]:
    """Devuelve el catálogo de funcionarios responsables por categoría."""
    service = SolicitudService()
    return [
        FuncionarioResponse.model_validate(f) for f in service.listar_funcionarios()
    ]
