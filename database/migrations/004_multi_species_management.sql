-- ============================================================================
-- Animora — Manejo Multi-Espécie (Bovinos, Equinos e Ovinos)
-- Migration 004:
--   1. Descentralização por espécie em `animals`, `lots`, `properties`,
--      `vaccines` e `sanitary_protocols` (sem perda de dados existentes)
--   2. Padronização das faixas etárias neutras (`lactente` / Lactente / Filhote)
--   3. Catálogo preventivo com `item_type` (Vacina, Vermífugo, Exame Sanitário)
--      e `exam_result` em `vaccination_records`
--   4. Novas tabelas `management_records` (Casqueamento, Ferrageamento, Tosquia,
--      Pesagem, Odontologia, Famacha) e `feeding_plans` (Cocho / Arraçoamento)
--   5. Políticas Row Level Security (RLS)
-- ============================================================================
-- Execute este script no SQL Editor do painel do Supabase.
-- Totalmente idempotente (pode ser executado com segurança mais de uma vez).
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Helper utilitário para remover CHECK constraints legadas por expressão/coluna
DO $$
DECLARE
    r RECORD;
BEGIN
    -- Remove CHECK antiga de properties.production_focus
    FOR r IN (
        SELECT con.conname
        FROM pg_constraint con
        JOIN pg_class rel ON rel.oid = con.conrelid
        JOIN pg_namespace nsp ON nsp.oid = rel.relnamespace
        WHERE nsp.nspname = 'public'
          AND rel.relname = 'properties'
          AND con.contype = 'c'
          AND pg_get_constraintdef(con.oid) ILIKE '%production_focus%'
    ) LOOP
        EXECUTE format('ALTER TABLE public.properties DROP CONSTRAINT IF EXISTS %I', r.conname);
    END LOOP;

    -- Remove CHECKs antigas de sanitary_protocols (animal_category e purpose)
    FOR r IN (
        SELECT con.conname
        FROM pg_constraint con
        JOIN pg_class rel ON rel.oid = con.conrelid
        JOIN pg_namespace nsp ON nsp.oid = rel.relnamespace
        WHERE nsp.nspname = 'public'
          AND rel.relname = 'sanitary_protocols'
          AND con.contype = 'c'
          AND (
              pg_get_constraintdef(con.oid) ILIKE '%animal_category%'
              OR pg_get_constraintdef(con.oid) ILIKE '%purpose%'
          )
    ) LOOP
        EXECUTE format('ALTER TABLE public.sanitary_protocols DROP CONSTRAINT IF EXISTS %I', r.conname);
    END LOOP;

    -- Remove CHECK antiga de vaccination_records.dosage (para permitir 0 ou 1 un em exames preventivos)
    FOR r IN (
        SELECT con.conname
        FROM pg_constraint con
        JOIN pg_class rel ON rel.oid = con.conrelid
        JOIN pg_namespace nsp ON nsp.oid = rel.relnamespace
        WHERE nsp.nspname = 'public'
          AND rel.relname = 'vaccination_records'
          AND con.contype = 'c'
          AND pg_get_constraintdef(con.oid) ILIKE '%dosage%'
    ) LOOP
        EXECUTE format('ALTER TABLE public.vaccination_records DROP CONSTRAINT IF EXISTS %I', r.conname);
    END LOOP;
END $$;

-- ----------------------------------------------------------------------------
-- 1. Propriedades Rurais e Lotes Multi-Espécie
-- ----------------------------------------------------------------------------
ALTER TABLE public.properties
    ALTER COLUMN production_focus TYPE VARCHAR(40),
    ALTER COLUMN production_focus SET DEFAULT 'misto';

ALTER TABLE public.properties
    DROP CONSTRAINT IF EXISTS chk_properties_production_focus;

ALTER TABLE public.properties
    ADD CONSTRAINT chk_properties_production_focus
    CHECK (production_focus IN ('corte', 'leite', 'misto', 'haras', 'cabanha', 'esporte_reproducao'));

ALTER TABLE public.lots
    ADD COLUMN IF NOT EXISTS target_species VARCHAR(20) NOT NULL DEFAULT 'todas';

ALTER TABLE public.lots
    DROP CONSTRAINT IF EXISTS chk_lots_target_species;

ALTER TABLE public.lots
    ADD CONSTRAINT chk_lots_target_species
    CHECK (target_species IN ('todas', 'bovino', 'equino', 'ovino'));

-- ----------------------------------------------------------------------------
-- 2. Faixas Etárias Neutras (`age_classifications`)
-- ----------------------------------------------------------------------------
UPDATE public.age_classifications
SET slug = 'lactente',
    name = 'Lactente / Filhote'
WHERE slug = 'bezerro';

-- ----------------------------------------------------------------------------
-- 3. Animais Multi-Espécie, Pelagem e Alojamento/Baia (`animals`)
-- ----------------------------------------------------------------------------
ALTER TABLE public.animals
    ADD COLUMN IF NOT EXISTS species VARCHAR(20) NOT NULL DEFAULT 'bovino',
    ADD COLUMN IF NOT EXISTS coat_color VARCHAR(80),
    ADD COLUMN IF NOT EXISTS secondary_id VARCHAR(100),
    ADD COLUMN IF NOT EXISTS reproductive_status VARCHAR(30) DEFAULT 'nao_informado',
    ADD COLUMN IF NOT EXISTS accommodation_type VARCHAR(30),
    ADD COLUMN IF NOT EXISTS accommodation_name VARCHAR(120);

ALTER TABLE public.animals
    DROP CONSTRAINT IF EXISTS chk_animals_species,
    DROP CONSTRAINT IF EXISTS chk_animals_reproductive_status,
    DROP CONSTRAINT IF EXISTS chk_animals_accommodation_type;

ALTER TABLE public.animals
    ADD CONSTRAINT chk_animals_species
        CHECK (species IN ('bovino', 'equino', 'ovino')),
    ADD CONSTRAINT chk_animals_reproductive_status
        CHECK (reproductive_status IS NULL OR reproductive_status IN ('nao_informado', 'inteiro', 'castrado', 'matriz', 'reprodutor')),
    ADD CONSTRAINT chk_animals_accommodation_type
        CHECK (accommodation_type IS NULL OR accommodation_type IN ('pasto_piquete', 'baia_cocheira', 'galpao_aprisco', 'confinamento'));

CREATE INDEX IF NOT EXISTS idx_animals_species ON public.animals (species);
CREATE INDEX IF NOT EXISTS idx_animals_accommodation ON public.animals (property_id, accommodation_name);

-- ----------------------------------------------------------------------------
-- 4. Catálogo Preventivo (Vacinas, Vermífugos e Exames) & Protocolos por Espécie
-- ----------------------------------------------------------------------------
ALTER TABLE public.vaccines
    ADD COLUMN IF NOT EXISTS item_type VARCHAR(30) NOT NULL DEFAULT 'vacina',
    ADD COLUMN IF NOT EXISTS target_species VARCHAR(20) NOT NULL DEFAULT 'todas';

ALTER TABLE public.vaccines
    DROP CONSTRAINT IF EXISTS chk_vaccines_item_type,
    DROP CONSTRAINT IF EXISTS chk_vaccines_target_species;

ALTER TABLE public.vaccines
    ADD CONSTRAINT chk_vaccines_item_type
        CHECK (item_type IN ('vacina', 'vermifugo', 'exame_preventivo')),
    ADD CONSTRAINT chk_vaccines_target_species
        CHECK (target_species IN ('todas', 'bovino', 'equino', 'ovino'));

ALTER TABLE public.vaccination_records
    ADD COLUMN IF NOT EXISTS exam_result VARCHAR(100);

ALTER TABLE public.vaccination_records
    DROP CONSTRAINT IF EXISTS chk_vac_records_dosage_nonneg;

ALTER TABLE public.vaccination_records
    ADD CONSTRAINT chk_vac_records_dosage_nonneg
    CHECK (dosage >= 0);

ALTER TABLE public.sanitary_protocols
    ADD COLUMN IF NOT EXISTS target_species VARCHAR(20) NOT NULL DEFAULT 'bovino';

ALTER TABLE public.sanitary_protocols
    ALTER COLUMN purpose TYPE VARCHAR(40);

UPDATE public.sanitary_protocols
SET animal_category = 'lactente'
WHERE animal_category = 'bezerro';

ALTER TABLE public.sanitary_protocols
    DROP CONSTRAINT IF EXISTS chk_protocols_target_species,
    DROP CONSTRAINT IF EXISTS chk_protocols_animal_category,
    DROP CONSTRAINT IF EXISTS chk_protocols_purpose;

ALTER TABLE public.sanitary_protocols
    ADD CONSTRAINT chk_protocols_target_species
        CHECK (target_species IN ('todas', 'bovino', 'equino', 'ovino')),
    ADD CONSTRAINT chk_protocols_animal_category
        CHECK (animal_category IN ('todas', 'recem_nascido', 'lactente', 'bezerro', 'jovem', 'adulto')),
    ADD CONSTRAINT chk_protocols_purpose
        CHECK (purpose IN ('corte', 'leite', 'reproducao', 'esporte_trabalho', 'la', 'geral'));

CREATE INDEX IF NOT EXISTS idx_protocols_species ON public.sanitary_protocols (property_id, target_species);

-- ----------------------------------------------------------------------------
-- 5. Rotinas de Manejo por Espécie (`management_records`)
--    Casqueamento, Ferrageamento, Tosquia, Pesagem, Odontologia e Escore/Famacha
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.management_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES public.organizations(id) ON DELETE RESTRICT,
    property_id UUID NOT NULL REFERENCES public.properties(id) ON DELETE RESTRICT,
    animal_id UUID NOT NULL REFERENCES public.animals(id) ON DELETE CASCADE,
    routine_type VARCHAR(40) NOT NULL
        CHECK (routine_type IN (
            'casqueamento',
            'ferrageamento',
            'tosquia',
            'pesagem',
            'odontologia',
            'escore_famacha'
        )),
    performed_at DATE NOT NULL DEFAULT CURRENT_DATE,
    next_due_date DATE,
    weight_kg NUMERIC(8, 2) CHECK (weight_kg IS NULL OR weight_kg >= 0),
    fleece_weight_kg NUMERIC(6, 2) CHECK (fleece_weight_kg IS NULL OR fleece_weight_kg >= 0),
    famacha_score SMALLINT CHECK (famacha_score IS NULL OR famacha_score BETWEEN 1 AND 5),
    hoof_condition VARCHAR(120),
    specialist_or_responsible VARCHAR(150),
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (next_due_date IS NULL OR next_due_date >= performed_at)
);

CREATE INDEX IF NOT EXISTS idx_mgmt_records_animal ON public.management_records (animal_id, performed_at DESC);
CREATE INDEX IF NOT EXISTS idx_mgmt_records_due ON public.management_records (organization_id, next_due_date);

COMMENT ON TABLE public.management_records IS 'Histórico e alertas de rotinas zootécnicas por espécie (casqueamento, ferrageamento, tosquia, pesagem, odontologia, Famacha).';

-- ----------------------------------------------------------------------------
-- 6. Plano de Cocho / Arraçoamento por Animal (`feeding_plans`)
--    Restrito aos níveis Property e Admin
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.feeding_plans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES public.organizations(id) ON DELETE RESTRICT,
    property_id UUID NOT NULL REFERENCES public.properties(id) ON DELETE RESTRICT,
    animal_id UUID NOT NULL REFERENCES public.animals(id) ON DELETE CASCADE,
    plan_name VARCHAR(150) NOT NULL DEFAULT 'Dieta Padrão de Cocho',
    roughage VARCHAR(200),
    concentrate VARCHAR(200),
    supplement_mineral VARCHAR(200),
    feeding_schedule VARCHAR(160),
    water_and_trough_notes TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    updated_by VARCHAR(150),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (animal_id)
);

CREATE INDEX IF NOT EXISTS idx_feeding_plans_property ON public.feeding_plans (property_id, is_active);

COMMENT ON TABLE public.feeding_plans IS 'Plano individual de cocho, volumoso, concentrado, suplementação e horários de trato.';

-- ----------------------------------------------------------------------------
-- 7. Políticas Row Level Security (RLS)
-- ----------------------------------------------------------------------------
ALTER TABLE public.management_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.feeding_plans ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "rls_management_records_access" ON public.management_records;
CREATE POLICY "rls_management_records_access" ON public.management_records
    FOR ALL TO authenticated
    USING (public.user_has_property_access(organization_id, property_id))
    WITH CHECK (public.user_has_property_access(organization_id, property_id));

DROP POLICY IF EXISTS "rls_feeding_plans_access" ON public.feeding_plans;
CREATE POLICY "rls_feeding_plans_access" ON public.feeding_plans
    FOR ALL TO authenticated
    USING (public.user_has_property_access(organization_id, property_id))
    WITH CHECK (public.user_has_property_access(organization_id, property_id));
