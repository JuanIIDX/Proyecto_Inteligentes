-- ============================================================
--  RESET completo de las tablas del proyecto en Supabase
--  ADVERTENCIA: esto borra TODOS los datos existentes en estas tablas.
--  Ejecuta este script en:  Supabase -> SQL Editor -> New query
-- ============================================================

-- ---- Borrar tablas existentes (orden por dependencias FK) ----
drop table if exists public.asignaciones cascade;
drop table if exists public.solicitudes cascade;
drop table if exists public.funcionarios cascade;

-- ---- Tabla: funcionarios ----
-- Catálogo de funcionarios/áreas responsables por categoría.
create table public.funcionarios (
    id          bigint generated always as identity primary key,
    nombre      text not null,
    categoria   text not null unique,            -- Académica | Financiera | Tecnológica | Administrativa
    correo      text not null,
    creado_en   timestamptz not null default now()
);

-- ---- Tabla: solicitudes ----
-- Historial de solicitudes recibidas y clasificadas por la IA.
create table public.solicitudes (
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
create table public.asignaciones (
    id              bigint generated always as identity primary key,
    solicitud_id    bigint not null references public.solicitudes(id) on delete cascade,
    funcionario_id  bigint references public.funcionarios(id) on delete set null,
    responsable     text not null,                 -- texto legible (área + correo)
    creado_en       timestamptz not null default now()
);

-- ---- Seed: catálogo inicial de funcionarios ----
insert into public.funcionarios (nombre, categoria, correo) values
    ('Coordinación Académica',      'Académica',      'academica@ucaldas.edu.co'),
    ('Departamento Financiero',     'Financiera',     'financiera@ucaldas.edu.co'),
    ('Soporte de Tecnología (TI)',  'Tecnológica',    'soporte.ti@ucaldas.edu.co'),
    ('Secretaría Administrativa',   'Administrativa', 'administrativa@ucaldas.edu.co');

-- ---- Refrescar el cache de esquema de PostgREST ----
notify pgrst, 'reload schema';
