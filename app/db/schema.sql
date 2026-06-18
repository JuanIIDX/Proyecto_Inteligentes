-- ============================================================
--  Esquema de base de datos para Supabase
--  Ejecuta este script en:  Supabase -> SQL Editor -> New query
-- ============================================================

-- ---- Tabla: funcionarios ----
-- Catálogo de funcionarios/áreas responsables por categoría.
-- 'categoria' NO es unique: puede haber varios funcionarios por categoría,
-- y el algoritmo A* (app/optimizacion/asignacion_astar.py) elige entre ellos.
create table if not exists public.funcionarios (
    id                        bigint generated always as identity primary key,
    nombre                    text not null,
    categoria                 text not null,      -- Académica | Financiera | Tecnológica | Administrativa
    especialidad              text,                -- normalmente = categoria
    correo                    text not null,
    carga_actual              integer not null default 0,  -- solicitudes activas hoy
    tiempo_promedio_respuesta numeric not null default 1,  -- en horas
    disponibilidad_horas      integer not null default 8,  -- capacidad para el lote de A*
    creado_en                 timestamptz not null default now()
);

-- ---- Tabla: solicitudes ----
-- Historial de solicitudes recibidas y clasificadas por la IA.
create table if not exists public.solicitudes (
    id            bigint generated always as identity primary key,
    asunto        text not null,
    descripcion   text not null,
    solicitante   text,
    categoria     text,                            -- la asigna la IA
    prioridad     text,                            -- Alta | Media | Baja
    razonamiento  text,
    estado        text not null default 'pendiente', -- pendiente | asignada | resuelta
    creado_en     timestamptz not null default now()
);

-- ---- Tabla: asignaciones ----
-- Relaciona cada solicitud con el funcionario responsable.
-- 'costo' y 'metodo' registran cómo se decidió esa asignación (regla fija
-- por categoría, o búsqueda A* con su costo f(n) final).
create table if not exists public.asignaciones (
    id              bigint generated always as identity primary key,
    solicitud_id    bigint not null references public.solicitudes(id) on delete cascade,
    funcionario_id  bigint references public.funcionarios(id) on delete set null,
    responsable     text not null,                 -- texto legible (área + correo)
    metodo          text not null default 'regla_fija',  -- regla_fija | astar
    costo           numeric,                        -- costo g(n) de A*, si aplica
    creado_en       timestamptz not null default now()
);

-- ---- Seed: catálogo inicial de funcionarios ----
insert into public.funcionarios (nombre, categoria, especialidad, correo, carga_actual, tiempo_promedio_respuesta, disponibilidad_horas) values
    ('Coordinación Académica',      'Académica',      'Académica',      'academica@ucaldas.edu.co',      0, 1, 8),
    ('Departamento Financiero',     'Financiera',     'Financiera',     'financiera@ucaldas.edu.co',     0, 1, 8),
    ('Soporte de Tecnología (TI)',  'Tecnológica',    'Tecnológica',    'soporte.ti@ucaldas.edu.co',     0, 1, 8),
    ('Secretaría Administrativa',   'Administrativa', 'Administrativa', 'administrativa@ucaldas.edu.co', 0, 1, 8);
