-- RaUP MVP · esquema de base de datos
-- Ejecutar en el editor SQL de Supabase (Proyecto > SQL Editor) sobre un proyecto nuevo.
--
-- Nota de seguridad (ver DECISIONS.md D-010): estas tablas se crean SIN Row Level Security.
-- Es una decisión consciente para el MVP: no hay login de profesional, el único control de
-- acceso es el código de sesión, y solo se usan datos sintéticos (ver D-003). No usar este
-- esquema tal cual con datos reales de pacientes sin añadir antes políticas RLS.

create extension if not exists pgcrypto;

-- ─────────────────────────────────────────────────────────────────────────
-- sesiones: una fila por cuestionario de preconsulta generado por el profesional
create table if not exists sesiones (
    id              uuid primary key default gen_random_uuid(),
    codigo          text not null unique,
    modo            text not null check (modo in ('primera_consulta', 'seguimiento')),
    -- texto libre a propósito (no un enum cerrado): el piloto es de nutrición,
    -- pero el profesional puede escribir cualquier otra especialidad (Paso 5).
    especialidad    text not null default 'Nutrición',
    motivo_consulta text,
    estado          text not null default 'creada'
                        check (estado in ('creada', 'en_curso', 'completada')),
    creado_en       timestamptz not null default now(),
    completado_en   timestamptz
);

-- migración idempotente por si la tabla ya existía sin esta columna
alter table sesiones add column if not exists especialidad text not null default 'Nutrición';

create index if not exists idx_sesiones_codigo on sesiones (codigo);

-- ─────────────────────────────────────────────────────────────────────────
-- respuestas: cada par pregunta/respuesta del cuestionario adaptativo
create table if not exists respuestas (
    id         uuid primary key default gen_random_uuid(),
    sesion_id  uuid not null references sesiones (id) on delete cascade,
    orden      integer not null,
    pregunta   text not null,
    respuesta  text not null,
    creado_en  timestamptz not null default now(),
    unique (sesion_id, orden)
);

create index if not exists idx_respuestas_sesion on respuestas (sesion_id);

-- ─────────────────────────────────────────────────────────────────────────
-- documentos: solo metadatos. El fichero en sí vive en Supabase Storage (bucket "documentos")
-- y no se lee ni se procesa (fuera de alcance del MVP).
create table if not exists documentos (
    id             uuid primary key default gen_random_uuid(),
    sesion_id      uuid not null references sesiones (id) on delete cascade,
    nombre_archivo text not null,
    ruta_storage   text not null,
    tipo_mime      text,
    tamano_bytes   bigint,
    subido_en      timestamptz not null default now()
);

create index if not exists idx_documentos_sesion on documentos (sesion_id);

-- ─────────────────────────────────────────────────────────────────────────
-- informes: el resultado para el profesional. Un informe por sesión.
-- "alertas" y "areas_a_profundizar" son listas (jsonb) — ver raup/models.py.
create table if not exists informes (
    id                    uuid primary key default gen_random_uuid(),
    sesion_id             uuid not null unique references sesiones (id) on delete cascade,
    resumen_ejecutivo     text not null,
    alertas               jsonb not null default '[]'::jsonb,
    areas_a_profundizar   jsonb not null default '[]'::jsonb,
    generado_en           timestamptz not null default now()
);

-- ─────────────────────────────────────────────────────────────────────────
-- Storage: bucket privado para los documentos subidos por el paciente.
insert into storage.buckets (id, name, public)
values ('documentos', 'documentos', false)
on conflict (id) do nothing;

-- Políticas de acceso al bucket (Paso 5). Igual que el resto del esquema
-- (ver D-010), sin restricciones finas: el único control de acceso es el
-- código de sesión, y solo se usan datos sintéticos. No apto para datos
-- reales de pacientes sin políticas más estrictas.
drop policy if exists "anon puede subir documentos" on storage.objects;
create policy "anon puede subir documentos"
    on storage.objects for insert
    to anon
    with check (bucket_id = 'documentos');

drop policy if exists "anon puede leer documentos" on storage.objects;
create policy "anon puede leer documentos"
    on storage.objects for select
    to anon
    using (bucket_id = 'documentos');
