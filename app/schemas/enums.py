"""
Enumeraciones del dominio.

Definir las categorías y prioridades como Enums (en lugar de strings sueltos)
da una única fuente de verdad: el LLM, la base de datos, las reglas de negocio
y la API comparten exactamente los mismos valores válidos. Esto evita errores
de tipeo y facilita la validación.
"""

from enum import Enum


class Categoria(str, Enum):
    """Categorías posibles de una solicitud universitaria."""

    ACADEMICA = "Académica"
    FINANCIERA = "Financiera"
    TECNOLOGICA = "Tecnológica"
    ADMINISTRATIVA = "Administrativa"


class Prioridad(str, Enum):
    """Niveles de prioridad con que se atiende una solicitud."""

    ALTA = "Alta"
    MEDIA = "Media"
    BAJA = "Baja"
