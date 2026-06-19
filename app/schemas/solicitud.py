"""
Esquemas Pydantic que definen los contratos de entrada y salida del sistema.

Modelos principales:
  - SolicitudRequest / SolicitudUpdate: lo que el cliente ENVÍA a la API.
  - ClasificacionResult: lo que el LLM DEVUELVE (categoría + prioridad + razón).
  - SolicitudResponse: la respuesta de una solicitud ya procesada.
  - FuncionarioResponse / AsignacionResponse: entidades de apoyo.

Con Supabase los registros llegan como diccionarios (JSON de la API REST);
estos modelos validan y tipan esa información de forma segura.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.schemas.enums import Categoria, Prioridad


class SolicitudRequest(BaseModel):
    """Datos que el usuario envía al crear una solicitud."""

    asunto: str = Field(
        ...,
        min_length=3,
        max_length=200,
        description="Título o asunto breve de la solicitud.",
        examples=["No puedo acceder a la plataforma Moodle"],
    )
    descripcion: str = Field(
        ...,
        min_length=5,
        max_length=2000,
        description="Descripción detallada de la solicitud.",
        examples=[
            "Desde ayer no logro iniciar sesión en Moodle, "
            "me aparece error 500 al ingresar mis credenciales."
        ],
    )
    solicitante: Optional[str] = Field(
        default=None,
        max_length=120,
        description="Nombre o identificación de quien realiza la solicitud.",
        examples=["Juan Pérez - Estudiante Ing. Sistemas"],
    )


class SolicitudUpdate(BaseModel):
    """Campos editables de una solicitud (todos opcionales)."""

    asunto: Optional[str] = Field(default=None, max_length=200)
    descripcion: Optional[str] = Field(default=None, max_length=2000)
    solicitante: Optional[str] = Field(default=None, max_length=120)
    categoria: Optional[Categoria] = None
    prioridad: Optional[Prioridad] = None
    estado: Optional[str] = Field(
        default=None,
        description="Estado de la solicitud: pendiente | asignada | resuelta.",
    )


class ClasificacionResult(BaseModel):
    """
    Resultado estructurado producido por el LLM.

    Este modelo se usa como `output schema` del LLM (salida estructurada),
    garantizando que el LLM responda siempre con estos campos exactos.
    """

    categoria: Categoria = Field(..., description="Categoría asignada a la solicitud.")
    prioridad: Prioridad = Field(..., description="Prioridad asignada a la solicitud.")
    razonamiento: str = Field(
        ...,
        description="Justificación breve de por qué se asignó esa categoría y prioridad.",
    )


class SolicitudResponse(BaseModel):
    """Respuesta de una solicitud ya procesada y persistida en Supabase."""

    id: int
    asunto: str
    descripcion: str
    solicitante: Optional[str] = None
    categoria: Optional[Categoria] = None
    prioridad: Optional[Prioridad] = None
    razonamiento: Optional[str] = None
    estado: str = "pendiente"
    responsable: Optional[str] = Field(
        default=None, description="Área o persona responsable asignada."
    )
    creado_en: Optional[datetime] = None


class FuncionarioResponse(BaseModel):
    """Funcionario/área responsable del catálogo."""

    id: int
    nombre: str
    categoria: Categoria
    correo: str
    creado_en: Optional[datetime] = None


class AsignacionResponse(BaseModel):
    """Asignación de una solicitud a un funcionario."""

    id: int
    solicitud_id: int
    funcionario_id: Optional[int] = None
    responsable: str
    creado_en: Optional[datetime] = None


class AsignacionAStarResponse(BaseModel):
    """Una asignación individual decidida por la búsqueda A*."""

    solicitud_id: int
    funcionario_id: int
    funcionario_nombre: str
    costo: float = Field(..., description="Costo g(n) de esta asignación.")


class NodoArbolResponse(BaseModel):
    """Un nodo del árbol de búsqueda de A* (para graficar el grafo explorado)."""

    id: int = Field(..., description="Identificador único del nodo.")
    padre: Optional[int] = Field(
        None, description="Id del nodo padre (None en la raíz). Define las aristas."
    )
    indice: int = Field(
        ..., description="Profundidad: solicitudes ya asignadas en este nodo."
    )
    g: float = Field(..., description="Costo acumulado g(n).")
    h: float = Field(..., description="Heurística h(n).")
    f: float = Field(..., description="Costo estimado total f(n) = g + h.")


class OptimizacionResponse(BaseModel):
    """
    Resultado de ejecutar A* sobre el lote de solicitudes pendientes.

    Incluye las asignaciones decididas y las métricas de la búsqueda, para
    poder visualizarlas en el frontend: métricas numéricas (nodos, tiempo,
    costo, profundidad) y el árbol de búsqueda explorado (nodos + aristas).
    """

    asignaciones: list[AsignacionAStarResponse]
    costo_total: float
    nodos_explorados: int
    tiempo_ejecucion_ms: float
    profundidad: int = Field(
        0, description="Niveles del árbol = solicitudes asignadas en la solución."
    )
    arbol: list[NodoArbolResponse] = Field(
        default_factory=list,
        description="Nodos explorados por A* (cada uno con su f/g/h y su padre).",
    )
    sin_solucion: list[int] = Field(
        default_factory=list,
        description="Ids de solicitudes sin funcionario candidato disponible.",
    )


class MetricaTecnica(BaseModel):
    """Métricas de una técnica al resolver el lote (para comparación/gráficas)."""

    nombre: str = Field(..., description="Nombre de la técnica (A*, BFS, ...).")
    tipo: str = Field(..., description="Familia de la técnica según la rúbrica.")
    costo_total: float = Field(..., description="Costo total de la solución hallada.")
    esfuerzo: int = Field(
        ..., description="Nodos explorados (búsquedas) o generaciones (genético)."
    )
    esfuerzo_etiqueta: str = Field(
        ..., description="Qué mide 'esfuerzo' en esta técnica."
    )
    tiempo_ejecucion_ms: float = Field(..., description="Tiempo de ejecución en ms.")
    optimo: bool = Field(
        ..., description="True si la técnica garantiza el óptimo (no el genético)."
    )
    truncado: bool = Field(
        False,
        description="True si la búsqueda se detuvo por el límite de nodos (lote grande).",
    )


class ComparacionTecnicasResponse(BaseModel):
    """
    Comparación de A*, BFS, DFS y Algoritmo Genético sobre el mismo lote.

    Pensada para graficar en el frontend: métricas por técnica (barras), el
    árbol de búsqueda de A* (grafo) y la curva de convergencia del genético.
    """

    num_solicitudes: int
    tecnicas: list[MetricaTecnica]
    arbol_astar: list[NodoArbolResponse] = Field(
        default_factory=list, description="Árbol de búsqueda explorado por A*."
    )
    convergencia_genetico: list[float] = Field(
        default_factory=list,
        description="Mejor costo por generación del genético (curva de convergencia).",
    )
