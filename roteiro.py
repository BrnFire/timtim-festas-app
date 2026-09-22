-- ==============================================================
-- Roteiro do Dia v3 — TimTim Festas
-- Tabela de apoio com cronômetro (chegada/saída reais).
-- Rode uma única vez no SQL Editor do Supabase.
-- Não altera nenhuma tabela existente do app.
-- ==============================================================

-- 1) Cria a tabela (caso ainda não exista)
create table if not exists public.roteiro_status (
    id_parada     uuid primary key default gen_random_uuid(),
    reserva_id    bigint not null,
    tipo          text   not null check (tipo in ('Entrega', 'Retirada')),
    data          date   not null,
    concluida     boolean not null default false,
    atualizado_em timestamptz default now(),
    constraint roteiro_status_unico unique (reserva_id, tipo, data)
);

-- 2) NOVO na v3: horários reais (texto 'HH:MM')
alter table public.roteiro_status
    add column if not exists chegada_real text;

alter table public.roteiro_status
    add column if not exists saida_real text;

-- 3) Índices
create index if not exists idx_roteiro_status_data
    on public.roteiro_status (data);

create index if not exists idx_roteiro_status_tipo_data
    on public.roteiro_status (tipo, data);

-- 4) Acesso (mesmo padrão das demais tabelas do app)
alter table public.roteiro_status enable row level security;

drop policy if exists "roteiro_status_full_access" on public.roteiro_status;
create policy "roteiro_status_full_access"
    on public.roteiro_status
    for all
    using (true)
    with check (true);

-- ==============================================================
-- Consulta útil: seu tempo real médio por tipo de serviço
-- ==============================================================
-- select
--     tipo,
--     count(*) as registros,
--     round(avg(
--         extract(epoch from (saida_real::time - chegada_real::time)) / 60
--     )) as media_min
-- from public.roteiro_status
-- where chegada_real is not null
--   and saida_real is not null
-- group by tipo;
