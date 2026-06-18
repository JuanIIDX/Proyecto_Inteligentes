"""
Tools personalizadas de LangChain.

Aquí se define la Tool requerida por la rúbrica: `asignar_responsable`.

Una Tool de LangChain es una función expuesta al ecosistema de agentes/cadenas
con un nombre, una descripción y un esquema de argumentos. En este sistema la
Tool encapsula una regla de negocio con efecto de datos real: consultar la tabla
`funcionarios` de Supabase para decidir qué área debe atender la solicitud
según su categoría.

Se implementa con el decorador @tool y un esquema de argumentos Pydantic, de
modo que la Tool es directamente invocable tanto desde la cadena LCEL como
desde un futuro agente.
"""

import logging

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.repositories.solicitud_repository import SupabaseRepository
from app.schemas.enums import Categoria

logger = logging.getLogger(__name__)

# Responsable de respaldo si la categoría no estuviera en la tabla.
RESPONSABLE_POR_DEFECTO = "Secretaría Administrativa (sin asignación específica)"


class AsignarResponsableArgs(BaseModel):
    """Esquema de argumentos de la Tool de asignación."""

    categoria: str = Field(
        ...,
        description=(
            "Categoría de la solicitud. Debe ser una de: "
            "Académica, Financiera, Tecnológica, Administrativa."
        ),
    )


@tool(args_schema=AsignarResponsableArgs)
def asignar_responsable(categoria: str) -> str:
    """
    Asigna el área responsable de atender una solicitud según su categoría.

    Consulta la tabla `funcionarios` en Supabase y devuelve el nombre del
    área junto con su correo de contacto. Si la categoría no existe, devuelve
    un responsable por defecto.
    """
    repo = SupabaseRepository()
    funcionario = repo.obtener_funcionario_por_categoria(categoria)

    if funcionario is None:
        logger.warning(
            "No se encontró funcionario para la categoría '%s'. "
            "Se usa el valor por defecto.",
            categoria,
        )
        return RESPONSABLE_POR_DEFECTO

    return f"{funcionario['nombre']} ({funcionario['correo']})"


def asignar_responsable_seguro(categoria: Categoria) -> str:
    """
    Adaptador interno que invoca la Tool desde la cadena LCEL.

    La cadena trabaja con el Enum `Categoria`; esta función lo convierte a str
    y llama a la Tool mediante `.invoke`, que es la forma canónica de ejecutar
    una Tool de LangChain.
    """
    return asignar_responsable.invoke({"categoria": categoria.value})
