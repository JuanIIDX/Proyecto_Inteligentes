"""
Servicio de solicitudes (capa de orquestación / casos de uso).

Coordina IA + datos en flujos de negocio:
  1. Invoca la cadena LCEL para clasificar, priorizar y asignar responsable.
  2. Persiste la solicitud en la base de datos.
  3. Crea la asignación (solicitud <-> funcionario) y marca la solicitud como
     'asignada'.

Mantener esta lógica fuera del endpoint hace que la API sea delgada y que el
caso de uso sea reutilizable.

Nota: la comparación de técnicas de búsqueda (A*, BFS, DFS, genético) se movió a
un notebook de Google Colab (proyecto_inteligentes_optimizacion.ipynb) para no
cargar el servidor de Azure con ese cómputo. La app solo conserva clasificación,
RAG y consulta de datos.
"""

import logging
from typing import Any

from app.chains.clasificacion_chain import clasificar_solicitud
from app.repositories.solicitud_repository import SupabaseRepository
from app.schemas.solicitud import SolicitudRequest, SolicitudUpdate

logger = logging.getLogger(__name__)


class SolicitudService:
    """Casos de uso del dominio de solicitudes universitarias."""

    def __init__(self) -> None:
        self.repo = SupabaseRepository()

    # ------------------------------------------------------------------ #
    #  Caso de uso principal: procesar una solicitud
    # ------------------------------------------------------------------ #
    def procesar(self, datos: SolicitudRequest) -> dict[str, Any]:
        """
        Procesa una solicitud de extremo a extremo: clasifica con IA, la
        persiste, asigna responsable y registra la asignación.
        """
        logger.info("Procesando solicitud: %s", datos.asunto)

        # 1) IA: clasificación + prioridad + responsable (cadena LCEL + Tool).
        clasificacion = clasificar_solicitud(
            asunto=datos.asunto, descripcion=datos.descripcion
        )

        # 2) Persistir la solicitud con su clasificación.
        solicitud = self.repo.crear_solicitud(
            {
                "asunto": datos.asunto,
                "descripcion": datos.descripcion,
                "solicitante": datos.solicitante,
                "categoria": clasificacion["categoria"].value,
                "prioridad": clasificacion["prioridad"].value,
                "razonamiento": clasificacion["razonamiento"],
                "estado": "asignada",
            }
        )

        # 3) Crear la asignación al funcionario de esa categoría.
        funcionario = self.repo.obtener_funcionario_por_categoria(
            clasificacion["categoria"].value
        )
        self.repo.crear_asignacion(
            {
                "solicitud_id": solicitud["id"],
                "funcionario_id": funcionario["id"] if funcionario else None,
                "responsable": clasificacion["responsable"],
            }
        )

        logger.info("Solicitud #%s procesada y asignada.", solicitud["id"])

        # Devolvemos la solicitud enriquecida con el responsable (campo derivado).
        solicitud["responsable"] = clasificacion["responsable"]
        return solicitud

    # ------------------------------------------------------------------ #
    #  Consultas / actualización
    # ------------------------------------------------------------------ #
    def listar(self, limite: int = 50) -> list[dict[str, Any]]:
        """Devuelve el historial de solicitudes."""
        return self.repo.obtener_solicitudes(limite=limite)

    def obtener(self, solicitud_id: int) -> dict[str, Any] | None:
        """Devuelve una solicitud por id."""
        return self.repo.obtener_solicitud(solicitud_id)

    def actualizar(
        self, solicitud_id: int, cambios: SolicitudUpdate
    ) -> dict[str, Any] | None:
        """Actualiza campos de una solicitud (sin re-clasificar)."""
        # exclude_unset: solo enviamos los campos realmente provistos.
        payload = cambios.model_dump(exclude_unset=True, exclude_none=True)
        # Convertir Enums a su valor string.
        for clave in ("categoria", "prioridad"):
            if clave in payload and hasattr(payload[clave], "value"):
                payload[clave] = payload[clave].value
        return self.repo.actualizar_solicitud(solicitud_id, payload)

    def listar_funcionarios(self) -> list[dict[str, Any]]:
        """Devuelve el catálogo de funcionarios."""
        return self.repo.obtener_funcionarios()
