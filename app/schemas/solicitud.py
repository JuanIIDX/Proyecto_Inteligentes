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
    # Campos que usa el modelo de costo de la optimización (notebook de Colab).
    especialidad: Optional[str] = None
    carga_actual: int = 0
    tiempo_promedio_respuesta: float = 1.0
    disponibilidad_horas: int = 8
    creado_en: Optional[datetime] = None


class AsignacionResponse(BaseModel):
    """Asignación de una solicitud a un funcionario."""

    id: int
    solicitud_id: int
    funcionario_id: Optional[int] = None
    responsable: str
    creado_en: Optional[datetime] = None


