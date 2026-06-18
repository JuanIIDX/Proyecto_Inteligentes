"""
Script de ingesta de documentos al vector store (RAG).

Lee los archivos de una carpeta (por defecto ./documentos), los divide en
fragmentos, los convierte en embeddings con Azure OpenAI y los guarda en
pgvector dentro de la base de datos de Azure PostgreSQL. Esto es lo que
"alimenta" el retrieval: sin documentos indexados, RAG no aporta contexto.

Requisitos previos:
  1. Haber ejecutado _private/db/migracion_rag.sql (extensión 'vector').
  2. Tener configurado AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT en el .env.
  3. Colocar los documentos en la carpeta de origen (.txt o .md).

Formatos soportados: .txt y .md (texto plano). Para PDF/DOCX habría que añadir
el loader correspondiente de langchain-community.

Ejecutar:
    python -m scripts.ingestar_documentos                 # usa ./documentos
    python -m scripts.ingestar_documentos ruta/a/carpeta  # carpeta concreta
"""

import sys
from pathlib import Path

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.chains.retriever import get_vector_store
from app.core.logging_config import setup_logging

# Carpeta por defecto donde buscar los documentos a indexar.
CARPETA_POR_DEFECTO = Path("documentos")
# Extensiones de texto plano que sabemos leer directamente.
EXTENSIONES = {".txt", ".md"}


def cargar_documentos(carpeta: Path) -> list[Document]:
    """Lee todos los .txt/.md de la carpeta y los devuelve como Documentos."""
    if not carpeta.exists():
        raise SystemExit(
            f"La carpeta '{carpeta}' no existe. Crea la carpeta y coloca dentro "
            "tus documentos (.txt o .md), o pasa otra ruta como argumento."
        )

    documentos: list[Document] = []
    for ruta in sorted(carpeta.rglob("*")):
        if ruta.suffix.lower() not in EXTENSIONES:
            continue
        texto = ruta.read_text(encoding="utf-8")
        # Guardamos el nombre del archivo como metadato 'fuente' para poder
        # citar de dónde salió cada fragmento más adelante.
        documentos.append(Document(page_content=texto, metadata={"fuente": ruta.name}))

    if not documentos:
        raise SystemExit(
            f"No se encontraron archivos {sorted(EXTENSIONES)} en '{carpeta}'."
        )
    return documentos


def fragmentar(documentos: list[Document]) -> list[Document]:
    """
    Divide los documentos en fragmentos de ~1000 caracteres con solape.

    El solape (200) evita cortar ideas a la mitad entre fragmentos. Fragmentos
    de este tamaño dan buen equilibrio entre precisión del retrieval y cantidad
    de contexto que cabe en el prompt.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
    )
    return splitter.split_documents(documentos)


def main() -> None:
    setup_logging()

    carpeta = Path(sys.argv[1]) if len(sys.argv) > 1 else CARPETA_POR_DEFECTO
    print(f"Leyendo documentos de: {carpeta.resolve()}")

    documentos = cargar_documentos(carpeta)
    fragmentos = fragmentar(documentos)
    print(f"  {len(documentos)} documento(s) -> {len(fragmentos)} fragmento(s).")

    print("Generando embeddings y guardando en pgvector...")
    vector_store = get_vector_store()
    vector_store.add_documents(fragmentos)

    print("Ingesta completada. El retriever ya puede usar estos documentos.")


if __name__ == "__main__":
    main()
