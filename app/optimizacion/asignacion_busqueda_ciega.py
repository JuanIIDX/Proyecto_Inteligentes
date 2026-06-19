"""
Asignación mediante búsqueda NO informada (BFS y DFS).

Resuelve EXACTAMENTE el mismo problema de asignación que `asignacion_astar.py`
(asignar un lote de solicitudes pendientes a funcionarios candidatos), pero sin
usar heurística. Sirve como punto de comparación frente a A*:

  - BFS (Breadth-First Search): explora por niveles, con una cola FIFO.
  - DFS (Depth-First Search): explora en profundidad, con una pila LIFO.

Ninguna usa información del costo para guiar la búsqueda (son "ciegas"): recorren
el espacio de estados expandiendo nodos hasta llegar a un estado objetivo. Por
eso, frente a A*, exploran MÁS nodos para encontrar una solución — y esa es
justamente la comparación que pide la rúbrica (valor de la heurística).

Reutiliza el mismo modelado de estado que A*:
    estado = (índice, capacidades)
Para que la comparación de COSTO sea justa, ambas recorren todo el espacio y se
quedan con la solución completa de MENOR costo encontrada (búsqueda exhaustiva).

- Estado, acciones y costo g(n): idénticos a A* (ver asignacion_astar.py).
- Diferencia: el orden de expansión (cola vs pila) y la ausencia de h(n).
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Literal

from app.optimizacion.asignacion_astar import (
    AsignacionResultado,
    FuncionarioCandidato,
    SolicitudPendiente,
    _candidatos_por_solicitud,
    _costo_asignacion,
)


@dataclass
class ResultadoBusquedaCiega:
    """Resultado de ejecutar BFS o DFS sobre el lote de solicitudes."""

    estrategia: str  # "BFS" o "DFS"
    asignaciones: list[AsignacionResultado]
    costo_total: float
    nodos_explorados: int
    tiempo_ejecucion_ms: float
    profundidad: int = 0
    sin_solucion: list[int] = field(default_factory=list)


def ejecutar_busqueda_ciega(
    solicitudes: list[SolicitudPendiente],
    funcionarios: list[FuncionarioCandidato],
    estrategia: Literal["BFS", "DFS"] = "BFS",
) -> ResultadoBusquedaCiega:
    """
    Asigna el lote con búsqueda ciega exhaustiva (BFS o DFS) y devuelve la mejor
    solución encontrada, junto con las métricas de la búsqueda.

    BFS usa una cola (popleft, FIFO); DFS usa una pila (pop, LIFO). El resto es
    idéntico: se expanden estados hasta agotar el espacio, conservando la
    asignación completa de menor costo total.
    """
    inicio = time.perf_counter()

    if not solicitudes:
        return ResultadoBusquedaCiega(
            estrategia=estrategia,
            asignaciones=[],
            costo_total=0.0,
            nodos_explorados=0,
            tiempo_ejecucion_ms=(time.perf_counter() - inicio) * 1000,
        )

    candidatos = _candidatos_por_solicitud(solicitudes, funcionarios)
    max_carga = max((f.carga_actual for f in funcionarios), default=0) or 1
    max_tiempo = max(
        (f.tiempo_promedio_respuesta for f in funcionarios), default=0
    ) or 1

    costos_por_par: dict[tuple[int, int], float] = {}
    for i, s in enumerate(solicitudes):
        for j in candidatos[i]:
            costos_por_par[(i, j)] = _costo_asignacion(
                s, funcionarios[j], max_carga, max_tiempo
            )

    sin_candidatos = [s.id for i, s in enumerate(solicitudes) if not candidatos[i]]
    capacidad_inicial = tuple(f.disponibilidad_horas for f in funcionarios)

    # Frontera: cada elemento es (indice, capacidades, g, asignaciones_parciales).
    frontera: deque = deque([(0, capacidad_inicial, 0.0, ())])

    nodos_explorados = 0
    profundidad_max = 0
    mejor_costo = float("inf")
    mejor_asignaciones_parciales: tuple = ()

    while frontera:
        # BFS saca por el frente (FIFO); DFS por el final (LIFO).
        if estrategia == "BFS":
            indice, capacidades, g, parciales = frontera.popleft()
        else:
            indice, capacidades, g, parciales = frontera.pop()

        nodos_explorados += 1
        profundidad_max = max(profundidad_max, indice)

        # Poda simple: si ya superamos la mejor solución, no seguimos por aquí.
        if g >= mejor_costo:
            continue

        if indice == len(solicitudes):
            if g < mejor_costo:
                mejor_costo = g
                mejor_asignaciones_parciales = parciales
            continue

        idxs_candidatos = candidatos[indice]

        if not idxs_candidatos:
            # Solicitud sin candidato: avanza sin asignar ni consumir capacidad.
            frontera.append((indice + 1, capacidades, g, parciales))
            continue

        for j in idxs_candidatos:
            if capacidades[j] <= 0:
                continue
            nuevas_capacidades = list(capacidades)
            nuevas_capacidades[j] -= 1
            costo_accion = costos_por_par[(indice, j)]
            frontera.append(
                (
                    indice + 1,
                    tuple(nuevas_capacidades),
                    g + costo_accion,
                    parciales + ((indice, j, costo_accion),),
                )
            )

    tiempo_ms = (time.perf_counter() - inicio) * 1000

    if mejor_costo == float("inf"):
        # No se logró asignar el lote completo (sin capacidad suficiente).
        return ResultadoBusquedaCiega(
            estrategia=estrategia,
            asignaciones=[],
            costo_total=0.0,
            nodos_explorados=nodos_explorados,
            tiempo_ejecucion_ms=tiempo_ms,
            profundidad=profundidad_max,
            sin_solucion=[s.id for s in solicitudes],
        )

    asignaciones = [
        AsignacionResultado(
            solicitud_id=solicitudes[i].id,
            funcionario_id=funcionarios[j].id,
            funcionario_nombre=funcionarios[j].nombre,
            costo=costo,
        )
        for (i, j, costo) in mejor_asignaciones_parciales
    ]
    return ResultadoBusquedaCiega(
        estrategia=estrategia,
        asignaciones=asignaciones,
        costo_total=mejor_costo,
        nodos_explorados=nodos_explorados,
        tiempo_ejecucion_ms=tiempo_ms,
        profundidad=profundidad_max,
        sin_solucion=sin_candidatos,
    )
