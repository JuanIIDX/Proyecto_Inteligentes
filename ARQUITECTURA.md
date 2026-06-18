# Arquitectura — Nivel 2 (LangChain)

Estado: **implementado y verificado en ejecución real** (Azure OpenAI + Supabase).
Este documento describe la arquitectura tal como existe en el código hoy, y cómo
se extenderá con A* (Nivel 3 / optimización heurística).

---

## 1. Flujo del sistema

```
Solicitud Universitaria (POST /solicitudes)
        │
        ▼
 Clasificación (LLM vía LangChain)
        │   categoría: Académica | Financiera | Tecnológica | Administrativa
        ▼
 Priorización (mismo LLM, misma llamada)
        │   prioridad: Alta | Media | Baja
        ▼
 Consulta de funcionarios disponibles (Tool -> Supabase)
        │   tabla `funcionarios`, filtrada por categoría
        ▼
 Asignación de responsable (Tool)
        │   hoy: regla fija 1 categoría -> 1 funcionario
        │   futuro: búsqueda A* sobre funcionarios candidatos (sección 8)
        ▼
 Persistencia (Supabase / Postgres)
        │   tabla `solicitudes` (clasificación) + `asignaciones` (responsable)
        ▼
 Respuesta JSON (FastAPI)
```

Esto reemplaza 1 a 1 el flujo de N8N (Nivel 1): cada nodo de N8N es ahora un
componente de código explícito y testeable.

---

## 2. Componentes necesarios

| Componente | Responsabilidad | Por qué existe separado |
|---|---|---|
| **API (FastAPI)** | Recibe HTTP, valida con Pydantic, serializa respuesta | No debe saber nada de IA ni de Supabase: solo HTTP |
| **Servicio** | Orquesta el caso de uso completo: clasificar → persistir → asignar | Punto único donde se define el *orden* de las operaciones |
| **Cadena LCEL (LangChain)** | Prompt → LLM → salida estructurada → Tool | Es la única pieza que "piensa"; aislarla permite probarla sin HTTP ni BD |
| **Tool personalizada** | Encapsula la regla de negocio "categoría → responsable" como función invocable por LangChain | Permite que un futuro agente la use igual, y que A* la reemplace sin tocar la cadena |
| **Repositorio** | Único punto que habla con Supabase | Si cambia el proveedor de BD, solo cambia este archivo |
| **Esquemas (Pydantic)** | Contratos de entrada/salida y Enums de dominio | Una sola fuente de verdad para qué es una categoría/prioridad válida |

---

## 3. Estructura de carpetas (real, en el repo)

```
app/
├── main.py                       # Arranque FastAPI, CORS, lifespan
├── api/
│   └── routes_solicitudes.py     # Endpoints REST (capa delgada)
├── core/
│   ├── config.py                 # Settings desde .env (Azure + Supabase)
│   └── logging_config.py
├── schemas/
│   ├── enums.py                  # Categoria, Prioridad
│   └── solicitud.py              # Request / ClasificacionResult / Response
├── chains/                       # ===== Núcleo LangChain =====
│   ├── llm.py                    # Fábrica de AzureChatOpenAI
│   ├── prompts.py                # ChatPromptTemplate
│   ├── tools.py                  # Tool: asignar_responsable
│   └── clasificacion_chain.py    # prompt | llm_estructurado | Tool  (LCEL)
├── repositories/
│   └── solicitud_repository.py   # CRUD sobre Supabase (supabase-py)
├── services/
│   └── solicitud_service.py      # Caso de uso: procesar(), listar(), actualizar()
└── db/
    ├── session.py                # Cliente Supabase (create_client)
    └── schema.sql                # DDL de solicitudes/funcionarios/asignaciones
```

---

## 4. Responsabilidad de cada módulo

- **`main.py`**: construye la app, registra el router, habilita CORS (para el
  cliente HTML de prueba) y expone `/health`.
- **`api/routes_solicitudes.py`**: 5 endpoints (`POST/GET/PATCH /solicitudes`,
  `GET /solicitudes/{id}`, `GET /funcionarios`). Nunca contiene lógica de
  negocio: cada handler llama a `SolicitudService` y traduce el resultado o
  excepción a HTTP.
- **`services/solicitud_service.py`**: el único lugar donde está escrito el
  *orden* de pasos del flujo (clasificar → guardar solicitud → buscar
  funcionario → crear asignación). Si el orden cambia, cambia aquí y en
  ningún otro sitio.
- **`chains/llm.py`**: construye una única instancia cacheada de
  `AzureChatOpenAI` a partir de `Settings`. Cambiar de modelo o de proveedor
  es editar un archivo.
- **`chains/prompts.py`**: define el `ChatPromptTemplate` con las reglas de
  clasificación y priorización en lenguaje natural (las 4 categorías y los 3
  niveles de prioridad, con criterios explícitos).
- **`chains/tools.py`**: la `Tool` `asignar_responsable`, decorada con
  `@tool`, con su propio `args_schema` Pydantic. Es invocable tanto desde la
  cadena LCEL como, en el futuro, desde un agente.
- **`chains/clasificacion_chain.py`**: compone `prompt | llm.with_structured_output(...) | Tool`
  con LCEL. Es la función `clasificar_solicitud(asunto, descripcion)` que el
  servicio invoca.
- **`repositories/solicitud_repository.py`**: todas las queries a Supabase
  (`solicitudes`, `funcionarios`, `asignaciones`), incluido el *embed* de
  PostgREST para resolver el responsable en los `GET`.
- **`schemas/enums.py` y `schemas/solicitud.py`**: `Categoria`, `Prioridad`,
  y los modelos Pydantic que validan entrada/salida en cada capa.

---

## 5. Cómo se integra LangChain

Tres piezas estándar de LangChain, conectadas con LCEL:

```python
prompt = get_clasificacion_prompt()                       # ChatPromptTemplate
llm_estructurado = get_llm().with_structured_output(ClasificacionResult)
clasificador = prompt | llm_estructurado                  # operador LCEL

# La Tool se invoca después, fuera del LLM, con el resultado ya estructurado:
responsable = asignar_responsable.invoke({"categoria": resultado.categoria.value})
```

- **`with_structured_output`** fuerza al modelo a devolver exactamente
  `{categoria, prioridad, razonamiento}` tipados como Enum — sin parseo de
  texto libre, sin regex, sin fallos por formato inesperado.
- **La Tool no se deja "decidir" al LLM** (no es function-calling libre):
  se invoca de forma determinista con la categoría ya clasificada. Esto es
  intencional para un sistema de clasificación — la aleatoriedad del LLM se
  limita a la parte que la necesita (entender lenguaje natural), no a la
  regla de negocio de asignación.
- Queda preparado para evolucionar a un **agente** (`AgentExecutor` o
  `create_tool_calling_agent`) si en el futuro se quiere que el propio LLM
  decida cuándo consultar funcionarios o pedir más contexto — hoy no hace
  falta porque el flujo es lineal y determinista.

---

## 6. Cómo se integra PostgreSQL / Supabase

Supabase **es** PostgreSQL gestionado; aquí se usa vía su **API REST**
(`supabase-py`), no vía SQLAlchemy/driver directo:

```python
db: Client = create_client(settings.supabase_url, settings.supabase_key)
db.table("solicitudes").insert(datos).execute()
db.table("solicitudes").select("*, asignaciones(responsable)").execute()
```

- **`session.py`** crea un único cliente cacheado (`@lru_cache`).
- **`schema.sql`** contiene el DDL real (`create table`, FKs, seed de
  funcionarios) — se ejecuta una vez en el SQL Editor de Supabase, no desde
  Python, porque no hay ORM ni migraciones automáticas en este diseño.
- Las relaciones (`asignaciones.solicitud_id → solicitudes.id`,
  `asignaciones.funcionario_id → funcionarios.id`) se resuelven con el
  *embedding* nativo de PostgREST (`select("*, asignaciones(responsable)")`),
  evitando joins manuales en Python.
- Si en el futuro se migra a Postgres puro (sin Supabase), solo cambia
  `db/session.py` y `repositories/solicitud_repository.py` — el resto del
  sistema (chains, servicio, API) no sabe ni le importa cómo se persisten
  los datos.

---

## 7. Tablas reales

```sql
funcionarios   (id, nombre, categoria UNIQUE, correo, creado_en)
solicitudes    (id, asunto, descripcion, solicitante, categoria, prioridad,
                razonamiento, estado, creado_en)
asignaciones   (id, solicitud_id FK, funcionario_id FK, responsable, creado_en)
```

`asignaciones` existe como tabla separada (no una columna más en
`solicitudes`) precisamente para que A* tenga un lugar natural donde escribir
*por qué* asignó a ese funcionario y no a otro — ver sección 8.

### 7.1. Por qué `categoria` y `prioridad` NO son tablas separadas

Es una decisión de diseño deliberada, no una omisión:

| Alternativa considerada | Por qué se descartó |
|---|---|
| Tablas `categorias` y `prioridades` con FK desde `solicitudes` | Son conjuntos **fijos y pequeños** (4 y 3 valores) que no cambian en tiempo de ejecución. Normalizarlos solo agrega joins sin beneficio: ninguna consulta del sistema necesita filtrar "categorías activas" o agregar una categoría nueva sin desplegar código. |
| SQLAlchemy + Postgres directo, en vez de `supabase-py` | El proyecto ya migró deliberadamente de SQLAlchemy a la API REST de Supabase (decisión anterior de arquitectura). Mantener ambos sería dos formas distintas de hablarle a la misma base de datos, lo que aumenta superficie de error sin necesidad real hoy. Queda como migración explícita a futuro si se pasa a Postgres autoadministrado. |

En su lugar, `Categoria` y `Prioridad` son **Enums de Python**
(`app/schemas/enums.py`), usados por: el LLM (vía `with_structured_output`,
que solo puede devolver uno de los valores del Enum), Pydantic (que rechaza
cualquier valor fuera del Enum en la API) y Supabase (donde se guardan como
`text`, validados antes de llegar a la base). Esto da la misma garantía de
integridad que una FK, sin el costo de mantenimiento de tablas de catálogo
para datos que no varían.

Si en el futuro una categoría o prioridad necesitara metadatos propios
(ej. un SLA en horas por prioridad, o un color por categoría para la UI),
ese es el punto en el que normalizar a tabla sí se justificaría.

---

## 8. Cómo se integrará A* (optimización heurística — trabajo futuro)

**Problema que resuelve:** hoy `asignar_responsable` aplica una regla fija
(1 categoría → 1 funcionario). En la realidad puede haber **varios
funcionarios por categoría**, cada uno con carga de trabajo, especialidad o
disponibilidad distinta. A* buscará la asignación de **costo mínimo**, no la
primera coincidencia.

### Formulación como problema de búsqueda

| Elemento de A* | En este dominio |
|---|---|
| **Estado** | Una asignación parcial: qué solicitudes pendientes ya tienen funcionario y cuáles no |
| **Estado objetivo** | Todas las solicitudes pendientes tienen un funcionario asignado |
| **Acción** | Asignar la siguiente solicitud pendiente a uno de sus funcionarios candidatos (misma categoría) |
| **Costo `g(n)`** | Acumulado: carga actual del funcionario + penalización si su prioridad de atención no coincide con la prioridad de la solicitud |
| **Heurística `h(n)`** | Estimación de costo restante: solicitudes pendientes × carga mínima disponible en cada categoría (admisible: nunca sobreestima) |
| **`f(n) = g(n) + h(n)`** | Función que A* minimiza para elegir qué expandir primero |

### Dónde se conecta en el código existente (sin romper nada)

`asignar_responsable` en `chains/tools.py` hoy hace una sola consulta y
devuelve un funcionario. Se reemplaza su *implementación interna* por una
llamada a un nuevo módulo `app/optimizacion/asignacion_astar.py`, manteniendo
la misma firma (`categoria -> responsable`) o ampliándola a
(`solicitud_id, categoria -> funcionario_id`) si se quiere optimizar en lote:

```
chains/tools.py  (Tool, sin cambiar su interfaz hacia LangChain)
        │
        ▼
optimizacion/asignacion_astar.py   <-- NUEVO módulo
        │   - construye el grafo de estados (solicitudes × funcionarios candidatos)
        │   - corre A* con heap de prioridad (heapq) sobre f(n)
        │   - devuelve el funcionario óptimo
        ▼
repositories/solicitud_repository.py
        │   - obtener_funcionarios_con_carga() (nueva query: cuenta
        │     asignaciones activas por funcionario)
        ▼
Supabase: tabla `funcionarios` ganaría una columna `carga_actual` o se
calcula con un COUNT sobre `asignaciones` + `solicitudes.estado`.
```

**Por qué esto no obliga a rediseñar nada hoy:**
- La cadena LCEL (`clasificacion_chain.py`) no cambia: sigue clasificando con
  el LLM igual que ahora.
- El servicio (`solicitud_service.py`) no cambia: sigue llamando a
  `asignar_responsable_seguro(categoria)`.
- Solo cambia *qué hay dentro* de la Tool, y se añade una tabla/columna para
  medir carga. Es exactamente el punto de extensión que el patrón Tool de
  LangChain está diseñado para ofrecer.

---

## 9. Resumen de cumplimiento

| Requisito pedido | Estado |
|---|---|
| Recibir solicitudes universitarias | ✅ implementado |
| Clasificarlas | ✅ implementado (LLM + LCEL) |
| Asignar prioridad | ✅ implementado (mismo paso) |
| Consultar funcionarios disponibles | ✅ implementado (Tool → Supabase) |
| Asignar un responsable | ✅ implementado (regla fija hoy) |
| Guardar en PostgreSQL/Supabase | ✅ implementado y probado en vivo |
| Retornar JSON | ✅ implementado (`SolicitudResponse`) |
| Integración futura de A* | 📐 diseñada en este documento, no implementada todavía |
