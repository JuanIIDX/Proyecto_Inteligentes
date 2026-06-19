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
from app.optimizacion.asignacion_busqueda_ciega import ejecutar_busqueda_ciega
from app.optimizacion.asignacion_genetico import ejecutar_genetico
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
    def _cargar_problema(
        self, solo_pendientes: bool = True
    ) -> tuple[list[SolicitudPendiente], list[FuncionarioCandidato]]:
        """
        Carga desde la BD el lote de solicitudes y los funcionarios, y los
        convierte a los tipos que usan los algoritmos de optimización.

        Es la entrada común a todas las técnicas (A*, BFS/DFS, genético), para
        que todas resuelvan exactamente el mismo problema.

        - solo_pendientes=True  -> solo solicitudes en estado 'pendiente'. Es lo
          que usa /optimizar-asignaciones, que asigna y persiste de verdad.
        - solo_pendientes=False -> todas las solicitudes ya clasificadas. Útil
          para /comparar-tecnicas, que es solo evaluación y no debería depender
          de que haya pendientes.
        """
        if solo_pendientes:
            base = self.repo.obtener_solicitudes_pendientes()
        else:
            base = self.repo.obtener_solicitudes()
        funcionarios = self.repo.obtener_funcionarios()

        solicitudes = [
            SolicitudPendiente(
                id=s["id"], categoria=s["categoria"], prioridad=s["prioridad"]
            )
            for s in base
            if s.get("categoria") and s.get("prioridad")
        ]
        candidatos = [
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
        return solicitudes, candidatos

    def optimizar_asignaciones(self) -> ResultadoAStar:
        """
        Asigna de forma óptima TODAS las solicitudes pendientes a los
        funcionarios disponibles usando búsqueda A* (ver
        app/optimizacion/asignacion_astar.py), persiste las asignaciones
        resultantes y marca esas solicitudes como 'asignada'.
        """
        solicitudes_astar, funcionarios_astar = self._cargar_problema()

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

    # ------------------------------------------------------------------ #
    #  Caso de uso: comparar técnicas (A* vs BFS/DFS vs Genético)
    # ------------------------------------------------------------------ #
    def comparar_tecnicas(self) -> dict[str, Any]:
        """
        Resuelve el MISMO lote de solicitudes pendientes con las cuatro técnicas
        (A*, BFS, DFS y Algoritmo Genético) y devuelve sus métricas lado a lado.

        Es un caso de uso de EVALUACIÓN: no persiste asignaciones ni cambia
        estados, solo ejecuta y mide. La salida está pensada para graficar la
        comparación en el frontend (costo, nodos/generaciones, tiempo) y la
        curva de convergencia del genético.

        Usa TODAS las solicitudes clasificadas (no solo las pendientes), para que
        la comparación se pueda ejecutar siempre que haya solicitudes, sin
        depender de su estado.
        """
        solicitudes, funcionarios = self._cargar_problema(solo_pendientes=False)

        a = ejecutar_astar(solicitudes, funcionarios)
        bfs = ejecutar_busqueda_ciega(solicitudes, funcionarios, "BFS")
        dfs = ejecutar_busqueda_ciega(solicitudes, funcionarios, "DFS")
        gen = ejecutar_genetico(solicitudes, funcionarios)

        # Métricas homogéneas por técnica para graficar barras comparativas.
        # 'esfuerzo' = nodos explorados (búsquedas) o generaciones (genético).
        tecnicas = [
            {
                "nombre": "A*",
                "tipo": "Búsqueda Informada",
                "costo_total": round(a.costo_total, 4),
                "esfuerzo": a.nodos_explorados,
                "esfuerzo_etiqueta": "nodos explorados",
                "tiempo_ejecucion_ms": round(a.tiempo_ejecucion_ms, 4),
                "optimo": True,
            },
            {
                "nombre": "BFS",
                "tipo": "Búsqueda No Informada",
                "costo_total": round(bfs.costo_total, 4),
                "esfuerzo": bfs.nodos_explorados,
                "esfuerzo_etiqueta": "nodos explorados",
                "tiempo_ejecucion_ms": round(bfs.tiempo_ejecucion_ms, 4),
                "optimo": True,
            },
            {
                "nombre": "DFS",
                "tipo": "Búsqueda No Informada",
                "costo_total": round(dfs.costo_total, 4),
                "esfuerzo": dfs.nodos_explorados,
                "esfuerzo_etiqueta": "nodos explorados",
                "tiempo_ejecucion_ms": round(dfs.tiempo_ejecucion_ms, 4),
                "optimo": True,
            },
            {
                "nombre": "Algoritmo Genético",
                "tipo": "Metaheurística",
                "costo_total": round(gen.costo_total, 4),
                "esfuerzo": gen.generaciones,
                "esfuerzo_etiqueta": "generaciones",
                "tiempo_ejecucion_ms": round(gen.tiempo_ejecucion_ms, 4),
                "optimo": False,
            },
        ]

        logger.info(
            "Comparación de técnicas sobre %d solicitudes: %s",
            len(solicitudes),
            {t["nombre"]: t["costo_total"] for t in tecnicas},
        )

        return {
            "num_solicitudes": len(solicitudes),
            "tecnicas": tecnicas,
            # Datos para gráficas específicas:
            "arbol_astar": a.arbol,  # grafo del árbol de búsqueda A*
            "convergencia_genetico": gen.historial_costos,  # curva por generación
        }
