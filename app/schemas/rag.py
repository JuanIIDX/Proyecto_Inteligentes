"""
Esquemas Pydantic para los endpoints de RAG (/rag/*).

Definen los contratos de entrada/salida de la búsqueda y la pregunta sobre los
documentos indexados, separados de los esquemas de solicitudes.
"""

from pydantic import BaseModel, Field


class DocumentoIndexado(BaseModel):
    """Un documento presente en el vector store y su nº de fragmentos."""

    fuente: str = Field(description="Nombre del archivo indexado.")
    fragmentos: int = Field(description="Cantidad de fragmentos guardados.")


class FragmentoRecuperado(BaseModel):
    """Un fragmento devuelto por el retrieval, con su puntuación."""

    contenido: str = Field(description="Texto del fragmento recuperado.")
    fuente: str = Field(description="Documento del que proviene el fragmento.")
    score: float = Field(
        description="Distancia de similitud (menor = más parecido a la consulta)."
    )


class BusquedaResponse(BaseModel):
    """Resultado de /rag/buscar: la consulta y los fragmentos recuperados."""

    consulta: str
    fragmentos: list[FragmentoRecuperado]


class PreguntaRequest(BaseModel):
    """Pregunta que el usuario envía a /rag/preguntar."""

    pregunta: str = Field(
        ...,
        min_length=3,
        max_length=1000,
        description="Pregunta a responder usando los documentos indexados.",
        examples=["¿Cuántas materias puedo perder antes de quedar en condicional?"],
    )


class RespuestaRAG(BaseModel):
    """Respuesta de /rag/preguntar: lo que la IA respondió y sus fuentes."""

    pregunta: str
    respuesta: str
    fuentes: list[str] = Field(
        description="Documentos usados como contexto para la respuesta."
    )
