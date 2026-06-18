# Sistema Inteligente de Clasificación, Priorización y Asignación de Solicitudes Universitarias

**Asignatura:** Sistemas Inteligentes 1 — Universidad de Caldas
**Nivel de rúbrica:** Nivel 2 (réplica en LangChain de la funcionalidad construida en N8N)

Sistema que recibe solicitudes universitarias por una API REST, las **clasifica**
(Académica, Financiera, Tecnológica, Administrativa), les asigna una **prioridad**
(Alta, Media, Baja) usando **Azure OpenAI + LangChain**, y determina un **responsable**
mediante una **Tool personalizada** que consulta Supabase. La arquitectura está
preparada para una futura integración con **RAG**.

---

## 1. Arquitectura

El sistema sigue una **arquitectura por capas** con separación estricta de
responsabilidades, lo que facilita el mantenimiento, las pruebas y la extensión
(p. ej. añadir RAG sin tocar la API ni la base de datos).

```
┌──────────────────────────────────────────────────────────────────┐
│                         CAPA API (FastAPI)                         │
│   routes_solicitudes.py  ·  main.py                                │
│   - Valida entrada (Pydantic) y serializa salida. Lógica delgada.  │
└───────────────┬────────────────────────────────────────────────────┘
                │
┌───────────────▼────────────────────────────────────────────────────┐
│                   CAPA SERVICIO (casos de uso)                      │
│   solicitud_service.py                                             │
│   - Orquesta: clasificar (IA) -> persistir -> devolver.            │
└───────────┬───────────────────────────────────┬────────────────────┘
            │                                   │
┌───────────▼───────────────┐     ┌──────────────▼───────────────────┐
│   CAPA IA (LangChain)      │     │   CAPA DATOS (Repository)         │
│   clasificacion_chain.py   │     │   solicitud_repository.py         │
│   prompts.py · llm.py      │     │   session.py (cliente Supabase)   │
│   tools.py (Tool custom)   │     │                                   │
│                            │     │   Supabase (supabase-py)          │
│   prompt | LLM | Tool      │     │   tablas: solicitudes,            │
│      (LCEL)                │     │           funcionarios,           │
│                            │     │           asignaciones            │
└───────────┬───────────────┘     └───────────────────────────────────┘
            │
       ┌──────────────┐
       │ Azure OpenAI │   (deployment configurable, salida estructurada)
       └──────────────┘
```

### Componentes y su justificación

| Componente | Archivo | Rol |
|---|---|---|
| **Configuración** | `core/config.py` | Lee y valida el `.env` con `pydantic-settings`. Única fuente de verdad de config. |
| **Esquemas / contratos** | `schemas/` | Modelos Pydantic + Enums. Garantizan datos válidos en API, IA y BD. |
| **LLM (Azure OpenAI)** | `chains/llm.py` | Aísla la creación del modelo. Cambiar de modelo = 1 archivo. |
| **Prompt** | `chains/prompts.py` | `ChatPromptTemplate` con definiciones explícitas de categorías y prioridades. |
| **Tool personalizada** | `chains/tools.py` | `asignar_responsable`: consulta Supabase y asigna área responsable. |
| **Cadena LCEL** | `chains/clasificacion_chain.py` | Pipeline `prompt \| LLM \| Tool`. Corazón de la IA. |
| **Repositorio** | `repositories/` | Encapsula el acceso a datos (patrón Repository). |
| **Servicio** | `services/` | Caso de uso: orquesta IA + persistencia. |
| **API** | `api/` + `main.py` | Endpoints REST y arranque de la app. |

---

## 2. Estructura de carpetas

```
Inteligentes Proyecto/
├── app/
│   ├── main.py                       # Punto de entrada FastAPI (lifespan, routers)
│   ├── api/
│   │   └── routes_solicitudes.py     # Endpoints REST
│   ├── core/
│   │   ├── config.py                 # Configuración (.env)
│   │   └── logging_config.py         # Logging centralizado
│   ├── schemas/
│   │   ├── enums.py                  # Categoria, Prioridad
│   │   └── solicitud.py              # Request / Result / Response
│   ├── chains/                       # ===== Núcleo LangChain =====
│   │   ├── llm.py                    # Fábrica de Azure OpenAI
│   │   ├── prompts.py                # ChatPromptTemplate
│   │   ├── tools.py                  # Tool personalizada (consulta Supabase)
│   │   └── clasificacion_chain.py    # Cadena LCEL completa
│   ├── repositories/
│   │   └── solicitud_repository.py   # Acceso a datos (supabase-py)
│   ├── services/
│   │   └── solicitud_service.py      # Caso de uso / orquestación
│   └── db/
│       ├── session.py                # Cliente de Supabase (create_client)
│       └── schema.sql                # SQL de tablas + seed (ejecutar en Supabase)
├── scripts/
│   └── probar_clasificacion.py       # Prueba la cadena sin levantar la API
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

---

## 3. Flujo de ejecución

```
Cliente
  │  POST /solicitudes { asunto, descripcion, solicitante }
  ▼
[API] routes_solicitudes.crear_solicitud
  │  valida con SolicitudRequest (Pydantic)
  ▼
[Servicio] SolicitudService.procesar
  │
  ├─► [Cadena LCEL] clasificar_solicitud(asunto, descripcion)
  │       1. ChatPromptTemplate  -> arma prompt
  │       2. Azure OpenAI (with_structured_output) -> ClasificacionResult
  │                                              {categoria, prioridad, razonamiento}
  │       3. RunnableLambda -> Tool asignar_responsable(categoria)
  │                            └─► consulta tabla `funcionarios` en Supabase
  │       └─► devuelve {categoria, prioridad, razonamiento, responsable}
  │
  ├─► [Repositorio] crear_solicitud()  -> INSERT en tabla `solicitudes`
  └─► [Repositorio] crear_asignacion() -> INSERT en tabla `asignaciones`
  ▼
[API] serializa con SolicitudResponse
  ▼
Cliente  ◄── 201 Created { id, categoria, prioridad, responsable, ... }
```

---

## 4. Requisitos previos

- **Python 3.12**
- Una cuenta de **Supabase** con un proyecto creado: https://supabase.com
- Un recurso de **Azure OpenAI** con un modelo desplegado (Azure AI Foundry)

Crea las tablas en Supabase (una sola vez): abre **SQL Editor → New query**,
pega el contenido de `_private/db/schema.sql` y ejecútalo. Esto
crea las tablas `solicitudes`, `funcionarios` y `asignaciones` y carga el
catálogo inicial de funcionarios.

Las credenciales de Supabase están en **Project Settings → API**:
- `SUPABASE_URL` = *Project URL*
- `SUPABASE_KEY` = *service_role* key (úsala solo en el backend).

Las credenciales de Azure OpenAI están en **Azure AI Foundry → tu proyecto →
"Models + endpoints"**:
- `AZURE_OPENAI_ENDPOINT` = endpoint del recurso (`https://<recurso>.openai.azure.com/`)
- `AZURE_OPENAI_API_KEY` = una de las dos API keys del recurso
- `AZURE_OPENAI_DEPLOYMENT` = nombre del **deployment** (no del modelo), visible
  en la sección "Deployments"

---

## 5. Instalación y ejecución

```powershell
# 1) Crear entorno virtual (Python 3.12)
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2) Instalar dependencias
pip install -r requirements.txt

# 3) Configurar variables de entorno
copy .env.example .env
#   Edita .env y coloca tus credenciales de Azure OpenAI y Supabase

# 4) Crear las tablas en Supabase (SQL Editor) con _private/db/schema.sql

# 5) Levantar la API
uvicorn app.main:app --reload
```

Abre la documentación interactiva en: **http://localhost:8000/docs**

### Probar la cadena de IA sin la API

```powershell
python -m scripts.probar_clasificacion
```

### Ejemplo de petición (curl)

```bash
curl -X POST http://localhost:8000/solicitudes \
  -H "Content-Type: application/json" \
  -d '{
        "asunto": "No puedo acceder a Moodle",
        "descripcion": "Error 500 al iniciar sesion y tengo examen manana.",
        "solicitante": "Juan Perez"
      }'
```

Respuesta esperada (201):

```json
{
  "id": 1,
  "asunto": "No puedo acceder a Moodle",
  "descripcion": "Error 500 al iniciar sesion y tengo examen manana.",
  "solicitante": "Juan Perez",
  "categoria": "Tecnológica",
  "prioridad": "Alta",
  "responsable": "Soporte de Tecnología (TI) (soporte.ti@ucaldas.edu.co)",
  "razonamiento": "Es un problema de acceso a una plataforma con impacto inmediato.",
  "creado_en": "2026-06-17T10:00:00Z"
}
```

---

## 6. Cumplimiento de los requisitos de LangChain

| Requisito de la rúbrica | Dónde se cumple |
|---|---|
| Usar un **LLM** (Azure OpenAI) | `chains/llm.py` (`AzureChatOpenAI`) |
| Usar **ChatPromptTemplate** | `chains/prompts.py` |
| **Tool personalizada** | `chains/tools.py` (`@tool asignar_responsable`, consulta Supabase) |
| **Chains / LCEL** | `chains/clasificacion_chain.py` (`prompt \| llm \| Tool`) |
| Arquitectura lista para **RAG** | Ver sección 7 |
| Código **modular y profesional** | Arquitectura por capas + patrón Repository |

---

## 7. Diseño orientado a RAG (extensión futura)

La cadena LCEL recibe el prompt ya construido. Para añadir RAG **no se reescribe
el pipeline**: se inserta un paso previo de recuperación (*retriever*) que aporta
contexto al prompt. El flujo quedaría:

```
pregunta -> retriever (normativa / solicitudes históricas)
         -> contexto + asunto + descripcion -> prompt -> Azure OpenAI -> Tool
```

Pasos concretos para implementarlo:
1. Añadir un *vector store* — Supabase incluye la extensión **pgvector**, así
   que el mismo proyecto sirve como base vectorial — y un modelo de
   *embeddings* de Azure OpenAI (`text-embedding-3-small`, por ejemplo).
2. Indexar normativa universitaria y solicitudes históricas resueltas.
3. Añadir una variable `{contexto}` al `ChatPromptTemplate`.
4. Anteponer el retriever en la cadena:
   `{"contexto": retriever, "asunto": ..., "descripcion": ...} | prompt | llm | tool`.

Como la lógica está aislada en capas, **API, servicio y base de datos no cambian**.

---

## 8. Justificación académica (para la presentación)

- **Problema:** la gestión manual de solicitudes universitarias es lenta,
  inconsistente y depende del criterio de quien las recibe.
- **Solución:** un sistema inteligente que automatiza clasificación, priorización
  y asignación, aplicando **IA generativa (Azure OpenAI)** orquestada con **LangChain**.
- **Por qué LangChain:** ofrece abstracciones estándar de la industria
  (ChatPromptTemplate, Tools, LCEL) que hacen el sistema **componible** y
  **extensible** — exactamente lo que pide el Nivel 2 al replicar y mejorar lo
  hecho en N8N con un enfoque de código profesional.
- **Por qué salida estructurada:** `with_structured_output` garantiza que el LLM
  devuelva siempre categoría y prioridad válidas (Enums), eliminando el parseo
  frágil de texto y haciendo el sistema **confiable**.
- **Por qué una Tool con Supabase:** demuestra el uso real de Tools de LangChain
  con **efecto sobre datos** y desacopla las reglas de asignación del código (se
  cambian en la tabla `funcionarios`, no en el código).
- **Optimización heurística:** la priorización (Alta/Media/Baja) actúa como
  heurística de ordenamiento de atención; la asignación basada en reglas por
  categoría es una heurística de *routing*. Esto conecta el componente de IA con
  el de **optimización** mencionado en el título del proyecto.

---

## 9. Recomendaciones para máxima calificación (Nivel 2)

1. **Demuestra cada requisito explícitamente** durante la sustentación: abre
   `tools.py` (Tool), `prompts.py` (ChatPromptTemplate) y `clasificacion_chain.py`
   (LCEL) y muestra el operador `|`.
2. **Muestra la salida estructurada** (`with_structured_output`) como diferencial
   técnico frente a la versión de N8N.
3. **Ejecuta `scripts/probar_clasificacion.py` en vivo** con los 3 ejemplos: cae
   bien mostrar el razonamiento del modelo.
4. **Enseña la base de datos** (tablas `solicitudes`, `funcionarios` y `asignaciones` en Supabase) para
   evidenciar la persistencia real y la Tool consultando datos.
5. **Explica la preparación para RAG** (sección 7): mostrar visión de futuro suele
   subir la nota.
6. **Resalta la arquitectura por capas y el patrón Repository** como evidencia de
   "código modular y profesional".
7. **Usa el Swagger en `/docs`** para la demo de la API: es visual y profesional.
8. **Ten un diagrama** (puedes usar el de la sección 1/3) en las diapositivas.
```
