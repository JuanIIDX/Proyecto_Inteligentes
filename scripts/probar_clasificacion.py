"""
Script de prueba manual de la cadena de clasificación SIN levantar la API.

Útil para verificar rápidamente que Gemini, la cadena LCEL y la Tool funcionan.
Requiere GOOGLE_API_KEY, SUPABASE_URL y SUPABASE_KEY configurados, y las tablas
ya creadas en Supabase (_private/db/schema.sql).

Ejecutar:  python -m scripts.probar_clasificacion
"""

from app.chains.clasificacion_chain import clasificar_solicitud
from app.core.logging_config import setup_logging

EJEMPLOS = [
    {
        "asunto": "No puedo acceder a Moodle",
        "descripcion": "Desde ayer me sale error 500 al iniciar sesión en la "
        "plataforma y tengo un examen mañana.",
    },
    {
        "asunto": "Consulta sobre fechas de grado",
        "descripcion": "Quisiera saber cuándo abren las inscripciones para la "
        "próxima ceremonia de grados.",
    },
    {
        "asunto": "Error en el cobro de matrícula",
        "descripcion": "Me cobraron dos veces el valor de la matrícula y necesito "
        "la devolución antes del cierre financiero del viernes.",
    },
]


def main() -> None:
    setup_logging()
    for ejemplo in EJEMPLOS:
        print("\n" + "=" * 70)
        print(f"ASUNTO: {ejemplo['asunto']}")
        resultado = clasificar_solicitud(**ejemplo)
        print(f"  Categoría    : {resultado['categoria'].value}")
        print(f"  Prioridad    : {resultado['prioridad'].value}")
        print(f"  Responsable  : {resultado['responsable']}")
        print(f"  Razonamiento : {resultado['razonamiento']}")


if __name__ == "__main__":
    main()
