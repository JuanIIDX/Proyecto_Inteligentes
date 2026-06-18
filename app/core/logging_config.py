"""
Configuración de logging para todo el sistema.

Centralizar el logging permite que cada módulo obtenga un logger con
`logging.getLogger(__name__)` y que el formato y nivel se controlen desde
un único lugar.
"""

import logging
import sys


def setup_logging(level: int = logging.INFO) -> None:
    """Configura el logger raíz con un formato legible hacia stdout."""
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
