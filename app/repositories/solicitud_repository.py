"""
Repositorio de acceso a datos (Supabase).

Encapsula TODAS las operaciones contra las tablas de Supabase mediante
supabase-py. El resto del sistema (servicio, API) nunca habla directamente con
Supabase: solo usa estos métodos. Esto mantiene el acceso a datos en un único
lugar y facilita pruebas y mantenimiento.

Tablas: solicitudes, funcionarios, asignaciones.
"""

import logging
from typing import Any

from supabase import Client

from app.db.session import get_supabase

logger = logging.getLogger(__name__)


class SupabaseRepository:
    """Operaciones CRUD sobre Supabase para el dominio de solicitudes."""

    def __init__(self, client: Client | None = None) -> None:
        # Permite inyectar un cliente en pruebas; por defecto usa el global.
        self.db: Client = client or get_supabase()

    # ------------------------------------------------------------------ #
    #  SOLICITUDES
    # ------------------------------------------------------------------ #
    # PostgREST permite "embeber" la tabla relacionada (asignaciones) en la
    # misma consulta gracias a la foreign key solicitud_id -> solicitudes.id.
    # Así evitamos una segunda consulta manual para resolver el responsable.
    _SELECT_CON_RESPONSABLE = "*, asignaciones(responsable)"

    @staticmethod
    def _aplanar_responsable(fila: dict[str, Any]) -> dict[str, Any]:
        """Extrae 'responsable' de la asignación embebida hacia el nivel raíz."""
        asignaciones = fila.pop("asignaciones", None) or []
        fila["responsable"] = asignaciones[0]["responsable"] if asignaciones else None
        return fila

    def obtener_solicitudes(self, limite: int = 50) -> list[dict[str, Any]]:
        """Devuelve las solicitudes más recientes, con su responsable asignado."""
        resp = (
            self.db.table("solicitudes")
            .select(self._SELECT_CON_RESPONSABLE)
            .order("creado_en", desc=True)
            .limit(limite)
            .execute()
        )
        return [self._aplanar_responsable(fila) for fila in resp.data]

    def obtener_solicitudes_pendientes(self) -> list[dict[str, Any]]:
        """Devuelve las solicitudes en estado 'pendiente' (lote para A*)."""
        resp = (
            self.db.table("solicitudes")
            .select("*")
            .eq("estado", "pendiente")
            .order("creado_en")
            .execute()
        )
        return resp.data

    def obtener_solicitud(self, solicitud_id: int) -> dict[str, Any] | None:
        """Devuelve una solicitud por id (con responsable), o None si no existe."""
        resp = (
            self.db.table("solicitudes")
            .select(self._SELECT_CON_RESPONSABLE)
            .eq("id", solicitud_id)
            .limit(1)
            .execute()
        )
        return self._aplanar_responsable(resp.data[0]) if resp.data else None

    def crear_solicitud(self, datos: dict[str, Any]) -> dict[str, Any]:
        """Inserta una solicitud y devuelve el registro creado."""
        resp = self.db.table("solicitudes").insert(datos).execute()
        return resp.data[0]

    def actualizar_solicitud(
        self, solicitud_id: int, cambios: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Actualiza una solicitud y devuelve el registro actualizado."""
        if not cambios:
            return self.obtener_solicitud(solicitud_id)
        resp = (
            self.db.table("solicitudes")
            .update(cambios)
            .eq("id", solicitud_id)
            .execute()
        )
        return resp.data[0] if resp.data else None

    # ------------------------------------------------------------------ #
    #  FUNCIONARIOS
    # ------------------------------------------------------------------ #
    def obtener_funcionarios(self) -> list[dict[str, Any]]:
        """Devuelve el catálogo completo de funcionarios."""
        resp = self.db.table("funcionarios").select("*").order("id").execute()
        return resp.data

    def obtener_funcionario_por_categoria(
        self, categoria: str
    ) -> dict[str, Any] | None:
        """Busca el funcionario responsable de una categoría dada."""
        resp = (
            self.db.table("funcionarios")
            .select("*")
            .eq("categoria", categoria)
            .limit(1)
            .execute()
        )
        return resp.data[0] if resp.data else None

    # ------------------------------------------------------------------ #
    #  ASIGNACIONES
    # ------------------------------------------------------------------ #
    def crear_asignacion(self, datos: dict[str, Any]) -> dict[str, Any]:
        """Crea una asignación (solicitud <-> funcionario) y la devuelve."""
        resp = self.db.table("asignaciones").insert(datos).execute()
        return resp.data[0]

    def crear_asignaciones(self, filas: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Inserta varias asignaciones en una sola operación (resultado de A*)."""
        if not filas:
            return []
        resp = self.db.table("asignaciones").insert(filas).execute()
        return resp.data
