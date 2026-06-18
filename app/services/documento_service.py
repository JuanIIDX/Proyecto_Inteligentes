"""
Servicio de ingesta de documentos para RAG.

Encapsula la lógica de "subir un documento y dejarlo listo para que la IA lo
use como contexto". Lo invoca el endpoint de subida (capa API) y se apoya en el
vector store de pgvector (app/chains/retriever.py).

Flujo de un documento:
    bytes del archivo -> texto -> fragmentos -> embeddings (Azure) -> pgvector

Una vez aquí, cualquier solicitud que se clasifique con RAG_ENABLED=true podrá
recuperar estos fragmentos como contexto. Soporta texto plano (.txt, .md). El
contenido se decodifica como UTF-8 (con respaldo latin-1 por si el archivo
viniera en otra codificación).
"""

import logging
from pathlib import Path

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.chains.retriever import get_vector_store

logger = logging.getLogger(__name__)

# Extensiones de texto plano que sabemos leer directamente.
EXTENSIONES_SOPORTADAS = {".txt", ".md"}


class DocumentoService:
    """Indexa documentos en el vector store para que la IA los use como contexto."""

    def __init__(self) -> None:
        # chunk_overlap evita cortar ideas a la mitad entre fragmentos.
        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
        )

    def _decodificar(self, contenido: bytes) -> str:
        """Convierte los bytes del archivo a texto, tolerando codificaciones."""
        try:
            return contenido.decode("utf-8")
        except UnicodeDecodeError:
            return contenido.decode("latin-1")

    def indexar(self, nombre_archivo: str, contenido: bytes) -> dict[str, int | str]:
        """
        Fragmenta e indexa un documento en el vector store.

        Devuelve un resumen con el nombre del archivo y cuántos fragmentos se
        guardaron. Lanza ValueError si el formato no está soportado o el archivo
        está vacío, para que la API responda con un 400 claro.
        """
        extension = Path(nombre_archivo).suffix.lower()
        if extension not in EXTENSIONES_SOPORTADAS:
            raise ValueError(
                f"Formato no soportado: '{extension}'. "
                f"Usa uno de: {sorted(EXTENSIONES_SOPORTADAS)}."
            )

        texto = self._decodificar(contenido).strip()
        if not texto:
            raise ValueError("El documento está vacío.")

        # Guardamos el nombre del archivo como metadato 'fuente' para poder
        # rastrear de qué documento salió cada fragmento.
        documento = Document(page_content=texto, metadata={"fuente": nombre_archivo})
        fragmentos = self._splitter.split_documents([documento])

        get_vector_store().add_documents(fragmentos)
        logger.info(
            "Documento '%s' indexado: %d fragmento(s).",
            nombre_archivo,
            len(fragmentos),
        )

        return {"fuente": nombre_archivo, "fragmentos": len(fragmentos)}
