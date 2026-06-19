"""
Asignación mediante Algoritmo Genético (metaheurística).

Resuelve el MISMO problema de asignación que A* y la búsqueda ciega, pero con un
enfoque evolutivo: en lugar de explorar el espacio de estados de forma
sistemática, mantiene una POBLACIÓN de soluciones candidatas y las mejora a lo
largo de varias GENERACIONES mediante selección, cruce y mutación.

A diferencia de A* (que garantiza el óptimo), el genético da una solución
APROXIMADA: no garantiza el mínimo global, pero escala mejor cuando el espacio
es enorme y suele encontrar soluciones muy buenas en poco tiempo. Esa es la
comparación interesante para la rúbrica: óptimo y costoso (A*) vs aproximado y
rápido (genético).

Representación (codificación):
    Un individuo (cromosoma) es una lista de longitud = nº de solicitudes. El
    gen i indica el índice del funcionario candidato asignado a la solicitud i
    (o None si la solicitud no tiene candidatos). Es una codificación entera
    directa del problema.

Función objetivo (fitness):
    Se minimiza el costo total de la asignación (mismo g(n) que A*) más una
    penalización si un individuo viola la capacidad de algún funcionario. Como
    el GA "maximiza", el fitness se define como el negativo de ese costo.
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field

from app.optimizacion.asignacion_astar import (
    AsignacionResultado,
    FuncionarioCandidato,
    SolicitudPendiente,
    _candidatos_por_solicitud,
    _costo_asignacion,
)

# Penalización por cada unidad de capacidad excedida en un funcionario. Alta para
# que el GA evite soluciones inválidas sin descartarlas de golpe.
PENALIZACION_CAPACIDAD = 100.0


@dataclass
class ResultadoGenetico:
    """Resultado de ejecutar el Algoritmo Genético sobre el lote."""

    asignaciones: list[AsignacionResultado]
    costo_total: float
    generaciones: int
    tiempo_ejecucion_ms: float
    # Mejor costo por generación: sirve para graficar la curva de convergencia.
    historial_costos: list[float] = field(default_factory=list)
    sin_solucion: list[int] = field(default_factory=list)


def _costo_individuo(
    individuo: list[int | None],
    solicitudes: list[SolicitudPendiente],
    funcionarios: list[FuncionarioCandidato],
    costos_por_par: dict[tuple[int, int], float],
) -> float:
    """Costo total de un individuo: suma de costos + penalización por capacidad."""
    costo = 0.0
    uso_por_funcionario: dict[int, int] = {}

    for i, j in enumerate(individuo):
        if j is None:
            continue
        costo += costos_por_par[(i, j)]
        uso_por_funcionario[j] = uso_por_funcionario.get(j, 0) + 1

    # Penaliza exceder la disponibilidad de horas de cada funcionario.
    for j, usados in uso_por_funcionario.items():
        exceso = usados - funcionarios[j].disponibilidad_horas
        if exceso > 0:
            costo += PENALIZACION_CAPACIDAD * exceso

    return costo


def _crear_individuo(
    candidatos: list[list[int]], rng: random.Random
) -> list[int | None]:
    """Genera un individuo aleatorio: a cada solicitud, un candidato al azar."""
    return [rng.choice(idxs) if idxs else None for idxs in candidatos]


def _seleccion_torneo(
    poblacion: list[list[int | None]],
    costos: list[float],
    rng: random.Random,
    k: int = 3,
) -> list[int | None]:
    """Selección por torneo: elige el mejor (menor costo) de k individuos al azar."""
    aspirantes = rng.sample(range(len(poblacion)), min(k, len(poblacion)))
    ganador = min(aspirantes, key=lambda idx: costos[idx])
    return poblacion[ganador]


def _cruzar(
    padre1: list[int | None], padre2: list[int | None], rng: random.Random
) -> list[int | None]:
    """Cruce de un punto: combina los genes de dos padres."""
    if len(padre1) < 2:
        return list(padre1)
    punto = rng.randint(1, len(padre1) - 1)
    return padre1[:punto] + padre2[punto:]


def _mutar(
    individuo: list[int | None],
    candidatos: list[list[int]],
    rng: random.Random,
    prob: float,
) -> list[int | None]:
    """Mutación: con probabilidad `prob`, reasigna un gen a otro candidato."""
    nuevo = list(individuo)
    for i, idxs in enumerate(candidatos):
        if idxs and rng.random() < prob:
            nuevo[i] = rng.choice(idxs)
    return nuevo


def ejecutar_genetico(
    solicitudes: list[SolicitudPendiente],
    funcionarios: list[FuncionarioCandidato],
    tam_poblacion: int = 50,
    generaciones: int = 100,
    prob_mutacion: float = 0.1,
    semilla: int | None = 42,
) -> ResultadoGenetico:
    """
    Ejecuta el Algoritmo Genético para asignar el lote de solicitudes.

    Parámetros (configurables para la rúbrica): tamaño de población, nº de
    generaciones y probabilidad de mutación. `semilla` fija la aleatoriedad para
    resultados reproducibles. Usa elitismo (conserva el mejor de cada generación)
    para no perder la mejor solución encontrada.
    """
    inicio = time.perf_counter()
    rng = random.Random(semilla)

    if not solicitudes:
        return ResultadoGenetico(
            asignaciones=[],
            costo_total=0.0,
            generaciones=0,
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

    # Población inicial aleatoria.
    poblacion = [_crear_individuo(candidatos, rng) for _ in range(tam_poblacion)]
    historial: list[float] = []

    mejor_individuo = poblacion[0]
    mejor_costo = float("inf")

    for _ in range(generaciones):
        costos = [
            _costo_individuo(ind, solicitudes, funcionarios, costos_por_par)
            for ind in poblacion
        ]

        # Elitismo: recordar el mejor de la generación.
        idx_mejor = min(range(len(poblacion)), key=lambda i: costos[i])
        if costos[idx_mejor] < mejor_costo:
            mejor_costo = costos[idx_mejor]
            mejor_individuo = list(poblacion[idx_mejor])
        historial.append(round(mejor_costo, 4))

        # Nueva generación: el élite pasa directo; el resto por selección+cruce+mutación.
        nueva_poblacion: list[list[int | None]] = [list(mejor_individuo)]
        while len(nueva_poblacion) < tam_poblacion:
            p1 = _seleccion_torneo(poblacion, costos, rng)
            p2 = _seleccion_torneo(poblacion, costos, rng)
            hijo = _cruzar(p1, p2, rng)
            hijo = _mutar(hijo, candidatos, rng, prob_mutacion)
            nueva_poblacion.append(hijo)
        poblacion = nueva_poblacion

    tiempo_ms = (time.perf_counter() - inicio) * 1000

    asignaciones = [
        AsignacionResultado(
            solicitud_id=solicitudes[i].id,
            funcionario_id=funcionarios[j].id,
            funcionario_nombre=funcionarios[j].nombre,
            costo=costos_por_par[(i, j)],
        )
        for i, j in enumerate(mejor_individuo)
        if j is not None
    ]

    return ResultadoGenetico(
        asignaciones=asignaciones,
        costo_total=mejor_costo,
        generaciones=generaciones,
        tiempo_ejecucion_ms=tiempo_ms,
        historial_costos=historial,
        sin_solucion=sin_candidatos,
    )
