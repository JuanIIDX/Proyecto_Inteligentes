"""
Servicio de solicitudes (capa de orquestación / casos de uso).

Coordina IA + datos en flujos de negocio:
  1. Invoca la cadena LCEL para clasificar, priorizar y asignar responsable.
  2. Persiste la solicitud en Supabase.
  3. Crea la asignación (solicitud <-> funcionario) y marca la solicitud como
     'asignada'.

Mantener esta lógica fuera del endpoint hace que la API sea delgada y que el
caso de uso sea reutilizable.
"""

import logging
from typing import Any

from app.chains.clasificacion_chain import clasificar_solicitud
from app.optimizacion.asignacion_astar import (
    FuncionarioCandidato,
    ResultadoAStar,
    SolicitudPendiente,
    ejecutar_astar,
)
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
        # exclude_unset: solo enviamos a Supabase los campos realmente provistos.
        payload = cambios.model_dump(exclude_unset=True, exclude_none=True)
        # Convertir Enums a su valor string para Supabase.
        for clave in ("categoria", "prioridad"):
            if clave in payload and hasattr(payload[clave], "value"):
                payload[clave] = payload[clave].value
        return self.repo.actualizar_solicitud(solicitud_id, payload)

    def listar_funcionarios(self) -> list[dict[str, Any]]:
        """Devuelve el catálogo de funcionarios."""
        return self.repo.obtener_funcionarios()

    # ------------------------------------------------------------------ #
    #  Caso de uso: optimizar asignaciones pendientes con A*
    # ------------------------------------------------------------------ #
    def optimizar_asignaciones(self) -> ResultadoAStar:
        """
        Asigna de forma óptima TODAS las solicitudes pendientes a los
        funcionarios disponibles usando búsqueda A* (ver
        app/optimizacion/asignacion_astar.py), persiste las asignaciones
        resultantes y marca esas solicitudes como 'asignada'.
        """
        pendientes = self.repo.obtener_solicitudes_pendientes()
        funcionarios = self.repo.obtener_funcionarios()

        solicitudes_astar = [
            SolicitudPendiente(
                id=s["id"], categoria=s["categoria"], prioridad=s["prioridad"]
            )
            for s in pendientes
            if s.get("categoria") and s.get("prioridad")
        ]
        funcionarios_astar = [
            FuncionarioCandidato(
                id=f["id"],
                nombre=f["nombre"],
                especialidad=f.get("especialidad") or f["categoria"],
                carga_actual=f.get("carga_actual", 0),
                tiempo_promedio_respuesta=f.get("tiempo_promedio_respuesta", 1),
                disponibilidad_horas=f.get("disponibilidad_horas", 8),
            )
            for f in funcionarios
        ]

        resultado = ejecutar_astar(solicitudes_astar, funcionarios_astar)

        if resultado.asignaciones:
            funcionarios_por_id = {f.id: f for f in funcionarios_astar}
            filas = [
                {
                    "solicitud_id": a.solicitud_id,
                    "funcionario_id": a.funcionario_id,
                    "responsable": (
                        f"{a.funcionario_nombre} "
                        f"({funcionarios_por_id[a.funcionario_id].especialidad})"
                    ),
                    "metodo": "astar",
                    "costo": a.costo,
                }
                for a in resultado.asignaciones
            ]
            self.repo.crear_asignaciones(filas)
            for a in resultado.asignaciones:
                self.repo.actualizar_solicitud(a.solicitud_id, {"estado": "asignada"})

        logger.info(
            "A*: %d asignaciones, costo_total=%.3f, nodos_explorados=%d, "
            "tiempo=%.2fms, sin_solucion=%s",
            len(resultado.asignaciones),
            resultado.costo_total,
            resultado.nodos_explorados,
            resultado.tiempo_ejecucion_ms,
            resultado.sin_solucion,
        )
        return resultado
