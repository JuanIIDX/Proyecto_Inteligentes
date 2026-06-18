-- ============================================================
--  Migración: soporte para asignación óptima con A*
--  Ejecuta este script en:  Supabase -> SQL Editor -> New query
--  NO es destructivo: agrega columnas y datos, no borra nada existente.
-- ============================================================

-- ---- 1) Permitir varios funcionarios por categoría ----
-- Antes 'categoria' era UNIQUE (1 funcionario fijo por categoría).
-- A* necesita poder elegir entre VARIOS funcionarios candidatos.
alter table public.funcionarios drop constraint if exists funcionarios_categoria_key;

-- ---- 2) Nuevas columnas que necesita A* para calcular costo ----
alter table public.funcionarios
    add column if not exists especialidad text,                        -- normalmente = categoria
    add column if not exists carga_actual integer not null default 0,  -- solicitudes activas hoy
    add column if not exists tiempo_promedio_respuesta numeric not null default 1,  -- en horas
    add column if not exists disponibilidad_horas integer not null default 8;       -- capacidad del lote

-- Por defecto la especialidad coincide con la categoría ya cargada.
update public.funcionarios set especialidad = categoria where especialidad is null;

-- ---- 2.1) Columnas en 'asignaciones' para trazar el método y el costo ----
alter table public.asignaciones
    add column if not exists metodo text not null default 'regla_fija',  -- regla_fija | astar
    add column if not exists costo numeric;

-- ---- 3) Más funcionarios por categoría (para que A* tenga candidatos reales) ----
insert into public.funcionarios (nombre, categoria, especialidad, correo, carga_actual, tiempo_promedio_respuesta, disponibilidad_horas) values
    ('Ana Torres - Académica',        'Académica',      'Académica',      'ana.torres@ucaldas.edu.co',        2, 1.5, 8),
    ('Luis Gómez - Académica',        'Académica',      'Académica',      'luis.gomez@ucaldas.edu.co',         5, 3.0, 6),
    ('Marta Ruiz - Financiera',       'Financiera',     'Financiera',     'marta.ruiz@ucaldas.edu.co',         1, 2.0, 8),
    ('Carlos Pena - Financiera',      'Financiera',     'Financiera',     'carlos.pena@ucaldas.edu.co',        4, 1.0, 4),
    ('Diana Rios - Tecnológica',      'Tecnológica',    'Tecnológica',    'diana.rios@ucaldas.edu.co',         3, 0.8, 8),
    ('Pedro Salas - Tecnológica',     'Tecnológica',    'Tecnológica',    'pedro.salas@ucaldas.edu.co',        1, 1.2, 5),
    ('Sofía Lara - Administrativa',   'Administrativa', 'Administrativa', 'sofia.lara@ucaldas.edu.co',         2, 2.5, 8),
    ('Jorge Vega - Administrativa',   'Administrativa', 'Administrativa', 'jorge.vega@ucaldas.edu.co',         6, 4.0, 3)
on conflict do nothing;

-- ---- 4) Refrescar el caché de esquema de PostgREST ----
notify pgrst, 'reload schema';
