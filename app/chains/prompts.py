"""
Plantillas de prompt (ChatPromptTemplate).

Centraliza la ingeniería de prompts del sistema. El prompt de clasificación
está diseñado con:
  - Un mensaje de sistema que define el rol y las reglas del clasificador.
  - Definiciones explícitas de cada categoría y de cada nivel de prioridad,
    para reducir ambigüedad y mejorar la consistencia del LLM.
  - Un mensaje humano con las variables {asunto}, {descripcion} y {contexto}.

La variable {contexto} contiene la normativa o el histórico recuperado por el
retriever (RAG). Cuando RAG está desactivado, la cadena la rellena con un texto
neutro, de modo que el mismo prompt sirve con y sin recuperación.
"""

from langchain_core.prompts import ChatPromptTemplate

SISTEMA_CLASIFICADOR = """\
Eres un asistente experto de la Universidad de Caldas encargado de clasificar
y priorizar solicitudes universitarias. Tu trabajo es analizar el asunto y la
descripción de cada solicitud y devolver una clasificación estructurada.

Debes asignar EXACTAMENTE una CATEGORÍA entre estas:
- Académica: matrículas, notas, cursos, docentes, horarios, exámenes, grados.
- Financiera: pagos, becas, créditos, facturación, devoluciones, descuentos.
- Tecnológica: plataformas (Moodle, correo, wifi), accesos, software, equipos.
- Administrativa: certificados, trámites, constancias, documentos, atención general.

Debes asignar EXACTAMENTE una PRIORIDAD entre estas:
- Alta: bloquea por completo al usuario, tiene fecha límite inminente, o afecta
  a muchas personas (caída de plataforma, vencimiento de pago, cierre de matrícula).
- Media: genera molestia o demora pero existe alternativa o el plazo no es urgente.
- Baja: consulta general, información o solicitud sin impacto inmediato.

Reglas:
1. Basa tu decisión en el contenido del asunto y la descripción.
2. Si el CONTEXTO incluye normativa o casos históricos relevantes, úsalo como
   apoyo para decidir la categoría y la prioridad. Si el contexto no es
   pertinente o está vacío, ignóralo y clasifica solo con la solicitud.
3. Sé consistente: ante el mismo tipo de solicitud, clasifica siempre igual.
4. En 'razonamiento' explica de forma breve (1-2 frases) por qué elegiste esa
   categoría y prioridad.
5. Responde siempre en español.
"""

HUMANO_CLASIFICADOR = """\
Clasifica la siguiente solicitud universitaria.

CONTEXTO (normativa o histórico relevante recuperado):
{contexto}

ASUNTO: {asunto}
DESCRIPCIÓN: {descripcion}
"""


def get_clasificacion_prompt() -> ChatPromptTemplate:
    """Devuelve el ChatPromptTemplate usado para clasificar solicitudes."""
    return ChatPromptTemplate.from_messages(
        [
            ("system", SISTEMA_CLASIFICADOR),
            ("human", HUMANO_CLASIFICADOR),
        ]
    )
