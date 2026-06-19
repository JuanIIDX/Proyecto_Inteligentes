"""
Asignación óptima de funcionarios mediante búsqueda A*.

Formulación como problema de búsqueda
--------------------------------------
En lugar de asignar cada solicitud de forma aislada (decisión local, regla
fija por categoría), este módulo resuelve la asignación de un LOTE completo
de solicitudes pendientes como un único problema de búsqueda en espacio de
estados. Esto permite que A* explore distintos órdenes/combinaciones de
asignación y encuentre la combinación de costo total mínimo, repartiendo
la carga entre los funcionarios candidatos en vez de saturar siempre al
mismo.

- Estado:
    (índice, capacidades)
    - índice: cuántas solicitudes del lote ya quedaron asignadas (0..n).
    - capacidades: tupla con las horas de disponibilidad restantes de cada
      funcionario candidato en este punto de la búsqueda.

- Estado inicial:
    (0, capacidades_iniciales) donde capacidades_iniciales son las horas de
    disponibilidad de cada funcionario tal como están en la base de datos.

- Estado objetivo:
    índice == len(solicitudes) → todas las solicitudes del lote ya fueron
    asignadas (o registradas como sin solución por falta de candidatos).

- Acciones:
    Desde el estado (índice, capacidades), asignar la solicitud en
    `solicitudes[índice]` a uno de sus funcionarios candidatos `j` que aún
    tenga `capacidades[j] > 0`. Cada acción consume 1 hora de disponibilidad
    de ese funcionario y avanza el índice en 1.

- Costo de la acción g(n):
    Ver `_costo_asignacion`. Combina carga actual del funcionario, su tiempo
    promedio de respuesta, y una penalización si la solicitud es de
    prioridad Alta pero el funcionario está sobrecargado o es lento.

- Heurística h(n):
    Ver `_heuristica`. Suma, para cada solicitud que falta por asignar desde
    el índice actual, el menor costo posible entre sus candidatos (ignorando
    si ya se quedaron sin capacidad). Es admisible: nunca sobreestima el
    costo real restante, porque el costo real no puede ser menor que asignar
    cada solicitud restante a su candidato más barato.

- f(n) = g(n) + h(n), explorado con un heap de prioridad (heapq).
"""

from __future__ import annotations

import heapq
import itertools
import time
from dataclasses import dataclass, field

from app.schemas.enums import Prioridad

# ---------------------------------------------------------------------------
# Pesos y umbrales de la función de costo
# ---------------------------------------------------------------------------
PESO_CARGA = 1.0
PESO_TIEMPO_RESPUESTA = 1.0
PENALIZACION_URGENCIA = 2.0
UMBRAL_CARGA_ALTA = 4
UMBRAL_TIEMPO_LENTO = 2.0


@dataclass(frozen=True)
class SolicitudPendiente:
    """Solicitud a asignar dentro del lote que procesa A*."""

    id: int
    categoria: str
    prioridad: str


@dataclass(frozen=True)
class FuncionarioCandidato:
    """Funcionario candidato con los datos que necesita la función de costo."""

    id: int
    nombre: str
    especialidad: str
    carga_actual: int
    tiempo_promedio_respuesta: float
    disponibilidad_horas: int


@dataclass
class AsignacionResultado:
    """Una asignación concreta que A* decidió dentro de la solución óptima."""

    solicitud_id: int
    funcionario_id: int
    funcionario_nombre: str
    costo: float


@dataclass
class NodoArbol:
    """Un nodo del árbol de búsqueda que A* expandió (para graficar)."""

    id: int
    padre: int | None
    indice: int  # cuántas solicitudes ya asignadas en este nodo (profundidad)
    g: float  # costo acumulado
    h: float  # heurística
    f: float  # g + h


@dataclass
class ResultadoAStar:
    """Resultado completo de ejecutar A* sobre un lote de solicitudes."""

    asignaciones: list[AsignacionResultado]
    costo_total: float
    nodos_explorados: int
    tiempo_ejecucion_ms: float
    profundidad: int = 0  # nº de niveles del árbol = nº de solicitudes asignadas
    arbol: list[NodoArbol] = field(default_factory=list)
    sin_solucion: list[int] = field(default_factory=list)


def _normalizar(valor: float, maximo: float) -> float:
    """Normaliza `valor` a [0, 1] usando `maximo` como referencia."""
    if maximo <= 0:
        return 0.0
    return min(max(valor / maximo, 0.0), 1.0)


def _costo_asignacion(
    solicitud: SolicitudPendiente,
    funcionario: FuncionarioCandidato,
    max_carga: float,
    max_tiempo: float,
) -> float:
    """g(n): costo real de asignar `solicitud` a `funcionario`.

    Combina carga actual y tiempo promedio de respuesta (ambos normalizados
    para que sean comparables), y añade una penalización fija cuando la
    solicitud es urgente (prioridad Alta) pero el funcionario está
    sobrecargado o responde lento — para evitar que A* mande solicitudes
    urgentes a quien tardará más en atenderlas.
    """
    costo = PESO_CARGA * _normalizar(funcionario.carga_actual, max_carga)
    costo += PESO_TIEMPO_RESPUESTA * _normalizar(
        funcionario.tiempo_promedio_respuesta, max_tiempo
    )

    es_urgente = solicitud.prioridad == Prioridad.ALTA.value
    esta_saturado = funcionario.carga_actual >= UMBRAL_CARGA_ALTA
    es_lento = funcionario.tiempo_promedio_respuesta >= UMBRAL_TIEMPO_LENTO
    if es_urgente and (esta_saturado or es_lento):
        costo += PENALIZACION_URGENCIA

    return costo


def _candidatos_por_solicitud(
    solicitudes: list[SolicitudPendiente],
    funcionarios: list[FuncionarioCandidato],
) -> list[list[int]]:
    """Filtro duro: para cada solicitud, índices de funcionarios cuya
    especialidad coincide con la categoría de la solicitud.
    """
    return [
        [j for j, f in enumerate(funcionarios) if f.especialidad == s.categoria]
        for s in solicitudes
    ]


def _heuristica(
    indice: int,
    solicitudes: list[SolicitudPendiente],
    candidatos: list[list[int]],
    costos_por_par: dict[tuple[int, int], float],
) -> float:
    """h(n): suma del menor costo posible (sin considerar capacidad) para
    cada solicitud restante desde `indice`. Es admisible porque el costo
    real nunca puede ser menor que asignar cada solicitud a su candidato
    más barato.
    """
    total = 0.0
    for i in range(indice, len(solicitudes)):
        idxs = candidatos[i]
        if not idxs:
            continue
        total += min(costos_por_par[(i, j)] for j in idxs)
    return total


def ejecutar_astar(
    solicitudes: list[SolicitudPendiente],
    funcionarios: list[FuncionarioCandidato],
) -> ResultadoAStar:
    """Ejecuta A* para asignar de forma óptima un lote de solicitudes
    pendientes a los funcionarios candidatos, minimizando el costo total.
    """
    inicio = time.perf_counter()

    if not solicitudes:
        return ResultadoAStar(
            asignaciones=[],
            costo_total=0.0,
            nodos_explorados=0,
            tiempo_ejecucion_ms=(time.perf_counter() - inicio) * 1000,
            profundidad=0,
            arbol=[],
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

    contador = itertools.count()
    nodos_explorados = 0
    profundidad_max = 0
    arbol: list[NodoArbol] = []
    mejor_costo_visto: dict[tuple[int, tuple[int, ...]], float] = {}

    # Cada entrada del heap lleva ahora el id de su nodo y el id de su padre,
    # para poder reconstruir el árbol de búsqueda (nodos + aristas) al graficar.
    h_inicial = _heuristica(0, solicitudes, candidatos, costos_por_par)
    id_raiz = next(contador)
    heap: list[tuple[float, float, int, int, int | None, int, tuple[int, ...], tuple]] = [
        (h_inicial, 0.0, id_raiz, id_raiz, None, 0, capacidad_inicial, ())
    ]

    while heap:
        (
            f_actual,
            g,
            _orden,
            id_nodo,
            id_padre,
            indice,
            capacidades,
            asignaciones_parciales,
        ) = heapq.heappop(heap)
        nodos_explorados += 1

        clave_estado = (indice, capacidades)
        if mejor_costo_visto.get(clave_estado, float("inf")) <= g:
            continue
        mejor_costo_visto[clave_estado] = g

        # Registrar este nodo expandido en el árbol de búsqueda.
        arbol.append(
            NodoArbol(
                id=id_nodo,
                padre=id_padre,
                indice=indice,
                g=round(g, 4),
                h=round(f_actual - g, 4),
                f=round(f_actual, 4),
            )
        )
        profundidad_max = max(profundidad_max, indice)

        if indice == len(solicitudes):
            asignaciones = [
                AsignacionResultado(
                    solicitud_id=solicitudes[i].id,
                    funcionario_id=funcionarios[j].id,
                    funcionario_nombre=funcionarios[j].nombre,
                    costo=costo,
                )
                for (i, j, costo) in asignaciones_parciales
            ]
            return ResultadoAStar(
                asignaciones=asignaciones,
                costo_total=g,
                nodos_explorados=nodos_explorados,
                tiempo_ejecucion_ms=(time.perf_counter() - inicio) * 1000,
                profundidad=profundidad_max,
                arbol=arbol,
                sin_solucion=sin_candidatos,
            )

        idxs_candidatos = candidatos[indice]

        if not idxs_candidatos:
            # Esta solicitud no tiene ningún funcionario con la especialidad
            # requerida: se registra como sin solución y se avanza sin
            # consumir capacidad de nadie.
            nuevo_indice = indice + 1
            nuevo_h = _heuristica(nuevo_indice, solicitudes, candidatos, costos_por_par)
            id_hijo = next(contador)
            heapq.heappush(
                heap,
                (
                    g + nuevo_h,
                    g,
                    id_hijo,
                    id_hijo,
                    id_nodo,
                    nuevo_indice,
                    capacidades,
                    asignaciones_parciales,
                ),
            )
            continue

        for j in idxs_candidatos:
            if capacidades[j] <= 0:
                continue
            nuevas_capacidades = list(capacidades)
            nuevas_capacidades[j] -= 1
            nuevas_capacidades = tuple(nuevas_capacidades)

            costo_accion = costos_por_par[(indice, j)]
            nuevo_g = g + costo_accion
            nuevo_indice = indice + 1
            nuevo_h = _heuristica(nuevo_indice, solicitudes, candidatos, costos_por_par)
            id_hijo = next(contador)

            heapq.heappush(
                heap,
                (
                    nuevo_g + nuevo_h,
                    nuevo_g,
                    id_hijo,
                    id_hijo,
                    id_nodo,
                    nuevo_indice,
                    nuevas_capacidades,
                    asignaciones_parciales + ((indice, j, costo_accion),),
                ),
            )

    # El heap se vació sin alcanzar el estado objetivo: no hay capacidad
    # suficiente entre los candidatos para cubrir todo el lote.
    return ResultadoAStar(
        asignaciones=[],
        costo_total=0.0,
        nodos_explorados=nodos_explorados,
        tiempo_ejecucion_ms=(time.perf_counter() - inicio) * 1000,
        profundidad=profundidad_max,
        arbol=arbol,
        sin_solucion=[s.id for s in solicitudes],
    )
