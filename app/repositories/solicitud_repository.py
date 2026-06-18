"""
Repositorio de acceso a datos (Azure Database for PostgreSQL).

Encapsula TODAS las operaciones contra las tablas de la base de datos mediante
SQLAlchemy Core. El resto del sistema (servicio, API) nunca habla directamente
con la base de datos: solo usa estos métodos. Esto mantiene el acceso a datos
en un único lugar y facilita pruebas y mantenimiento.

Tablas: solicitudes, funcionarios, asignaciones.
"""

import logging
from typing import Any

from sqlalchemy import Engine, text

from app.db.session import get_engine

logger = logging.getLogger(__name__)


class SupabaseRepository:
    """Operaciones CRUD sobre PostgreSQL para el dominio de solicitudes."""

    def __init__(self, engine: Engine | None = None) -> None:
        # Permite inyectar un engine en pruebas; por defecto usa el global.
        self.db: Engine = engine or get_engine()

    # ------------------------------------------------------------------ #
    #  SOLICITUDES
    # ------------------------------------------------------------------ #
    # LEFT JOIN con asignaciones para resolver el responsable en una sola
    # consulta, igual que hacía el "embed" de PostgREST en Supabase.
    _SELECT_CON_RESPONSABLE = """
        select s.*, a.responsable as responsable
        from public.solicitudes s
        left join public.asignaciones a on a.solicitud_id = s.id
    """

    def obtener_solicitudes(self, limite: int = 50) -> list[dict[str, Any]]:
        """Devuelve las solicitudes más recientes, con su responsable asignado."""
        sql = text(
            self._SELECT_CON_RESPONSABLE
            + " order by s.creado_en desc limit :limite"
        )
        with self.db.connect() as conn:
            filas = conn.execute(sql, {"limite": limite}).mappings().all()
        return [dict(fila) for fila in filas]

    def obtener_solicitudes_pendientes(self) -> list[dict[str, Any]]:
        """Devuelve las solicitudes en estado 'pendiente' (lote para A*)."""
        sql = text(
            "select * from public.solicitudes "
            "where estado = 'pendiente' order by creado_en"
        )
        with self.db.connect() as conn:
            filas = conn.execute(sql).mappings().all()
        return [dict(fila) for fila in filas]

    def obtener_solicitud(self, solicitud_id: int) -> dict[str, Any] | None:
        """Devuelve una solicitud por id (con responsable), o None si no existe."""
        sql = text(self._SELECT_CON_RESPONSABLE + " where s.id = :id limit 1")
        with self.db.connect() as conn:
            fila = conn.execute(sql, {"id": solicitud_id}).mappings().first()
        return dict(fila) if fila else None

    def crear_solicitud(self, datos: dict[str, Any]) -> dict[str, Any]:
        """Inserta una solicitud y devuelve el registro creado."""
        columnas = ", ".join(datos.keys())
        marcadores = ", ".join(f":{clave}" for clave in datos)
        sql = text(
            f"insert into public.solicitudes ({columnas}) "
            f"values ({marcadores}) returning *"
        )
        with self.db.begin() as conn:
            fila = conn.execute(sql, datos).mappings().first()
        return dict(fila)

    def actualizar_solicitud(
        self, solicitud_id: int, cambios: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Actualiza una solicitud y devuelve el registro actualizado."""
        if not cambios:
            return self.obtener_solicitud(solicitud_id)
        asignaciones = ", ".join(f"{clave} = :{clave}" for clave in cambios)
        sql = text(
            f"update public.solicitudes set {asignaciones} "
            f"where id = :id returning *"
        )
        with self.db.begin() as conn:
            fila = conn.execute(sql, {**cambios, "id": solicitud_id}).mappings().first()
        return dict(fila) if fila else None

    # ------------------------------------------------------------------ #
    #  FUNCIONARIOS
    # ------------------------------------------------------------------ #
    def obtener_funcionarios(self) -> list[dict[str, Any]]:
        """Devuelve el catálogo completo de funcionarios."""
        sql = text("select * from public.funcionarios order by id")
        with self.db.connect() as conn:
            filas = conn.execute(sql).mappings().all()
        return [dict(fila) for fila in filas]

    def obtener_funcionario_por_categoria(
        self, categoria: str
    ) -> dict[str, Any] | None:
        """Busca el funcionario responsable de una categoría dada."""
        sql = text(
            "select * from public.funcionarios "
            "where categoria = :categoria limit 1"
        )
        with self.db.connect() as conn:
            fila = conn.execute(sql, {"categoria": categoria}).mappings().first()
        return dict(fila) if fila else None

    # ------------------------------------------------------------------ #
    #  ASIGNACIONES
    # ------------------------------------------------------------------ #
    def crear_asignacion(self, datos: dict[str, Any]) -> dict[str, Any]:
        """Crea una asignación (solicitud <-> funcionario) y la devuelve."""
        columnas = ", ".join(datos.keys())
        marcadores = ", ".join(f":{clave}" for clave in datos)
        sql = text(
            f"insert into public.asignaciones ({columnas}) "
            f"values ({marcadores}) returning *"
        )
        with self.db.begin() as conn:
            fila = conn.execute(sql, datos).mappings().first()
        return dict(fila)

    def crear_asignaciones(self, filas: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Inserta varias asignaciones en una sola operación (resultado de A*)."""
        if not filas:
            return []
        columnas = ", ".join(filas[0].keys())
        marcadores = ", ".join(f":{clave}" for clave in filas[0])
        sql = text(
            f"insert into public.asignaciones ({columnas}) "
            f"values ({marcadores}) returning *"
        )
        with self.db.begin() as conn:
            resultado = [
                dict(conn.execute(sql, fila).mappings().first()) for fila in filas
            ]
        return resultado
