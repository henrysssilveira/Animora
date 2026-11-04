-- ============================================================================
-- BoviTrack — Script Consolidado de Banco de Dados (Supabase PostgreSQL)
-- Inclui: Cadastro de Bovinos + QR Code + Módulo de Gestão Sanitária + RLS
-- ============================================================================
-- Para projetos novos: execute este arquivo no SQL Editor do Supabase.
-- Para projetos que já possuem a tabela `animals`: execute
-- `database/migrations/001_sanitary_module.sql` (ou este próprio script,
-- pois todas as instruções são idempotentes).
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- 1. Organizações
CREATE TABLE IF NOT EXISTS public.organizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(150) NOT NULL,
    slug VARCHAR(100) NOT NULL UNIQUE,
    document VARCHAR(30),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 2. Propriedades Rurais
CREATE TABLE IF NOT EXISTS public.properties (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES public.organizations(id) ON DELETE RESTRICT,
    name VARCHAR(150) NOT NULL,
    code VARCHAR(50),
    municipality VARCHAR(100),
    state CHAR(2),
    production_focus VARCHAR(40) NOT NULL DEFAULT 'misto'
        CHECK (production_focus IN ('corte', 'leite', 'misto', 'haras', 'cabanha', 'esporte_reproducao')),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_properties_org ON public.properties (organization_id);

-- 3. Membros da Organização (controle de acesso RLS)
CREATE TABLE IF NOT EXISTS public.organization_members (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    property_id UUID REFERENCES public.properties(id) ON DELETE CASCADE,
    user_id UUID NOT NULL,
    role VARCHAR(40) NOT NULL DEFAULT 'produtor'
        CHECK (role IN ('admin', 'produtor', 'responsavel_tecnico', 'operador')),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (organization_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_org_members_user ON public.organization_members (user_id);

-- 4. Lotes de Manejo
CREATE TABLE IF NOT EXISTS public.lots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES public.organizations(id) ON DELETE RESTRICT,
    property_id UUID NOT NULL REFERENCES public.properties(id) ON DELETE CASCADE,
    name VARCHAR(120) NOT NULL,
    target_species VARCHAR(20) NOT NULL DEFAULT 'todas'
        CHECK (target_species IN ('todas', 'bovino', 'equino', 'ovino')),
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (property_id, name)
);

CREATE INDEX IF NOT EXISTS idx_lots_property ON public.lots (property_id);

-- 5. Faixas Etárias Configuráveis
CREATE TABLE IF NOT EXISTS public.age_classifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID REFERENCES public.organizations(id) ON DELETE CASCADE,
    slug VARCHAR(40) NOT NULL,
    name VARCHAR(80) NOT NULL,
    min_days INTEGER NOT NULL CHECK (min_days >= 0),
    max_days INTEGER CHECK (max_days IS NULL OR max_days >= min_days),
    sort_order INTEGER NOT NULL DEFAULT 1,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 6. Animais Multi-Espécie (`animals` — Bovinos, Equinos e Ovinos)
CREATE TABLE IF NOT EXISTS public.animals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ear_tag VARCHAR(100) NOT NULL UNIQUE,
    name VARCHAR(150),
    species VARCHAR(20) NOT NULL DEFAULT 'bovino'
        CHECK (species IN ('bovino', 'equino', 'ovino')),
    sex VARCHAR(20) NOT NULL CHECK (sex IN ('Macho', 'Fêmea')),
    breed VARCHAR(100) NOT NULL,
    coat_color VARCHAR(80),
    secondary_id VARCHAR(100),
    reproductive_status VARCHAR(30) DEFAULT 'nao_informado'
        CHECK (reproductive_status IS NULL OR reproductive_status IN ('nao_informado', 'inteiro', 'castrado', 'matriz', 'reprodutor')),
    accommodation_type VARCHAR(30)
        CHECK (accommodation_type IS NULL OR accommodation_type IN ('pasto_piquete', 'baia_cocheira', 'galpao_aprisco', 'confinamento')),
    accommodation_name VARCHAR(120),
    birth_date DATE NOT NULL,
    initial_weight NUMERIC(8, 2) CHECK (initial_weight IS NULL OR initial_weight >= 0),
    notes TEXT,
    qr_code_token UUID NOT NULL UNIQUE DEFAULT gen_random_uuid(),
    organization_id UUID REFERENCES public.organizations(id) ON DELETE RESTRICT,
    property_id UUID REFERENCES public.properties(id) ON DELETE RESTRICT,
    lot_id UUID REFERENCES public.lots(id) ON DELETE SET NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'ativo'
        CHECK (status IN ('ativo', 'inativo', 'vendido', 'obito')),
    origin_type VARCHAR(30) NOT NULL DEFAULT 'nascido_propriedade'
        CHECK (origin_type IN ('nascido_propriedade', 'adquirido_externo', 'pre_existente')),
    sanitary_onboarding_mode VARCHAR(40) NOT NULL DEFAULT 'acompanhamento_nascimento'
        CHECK (sanitary_onboarding_mode IN (
            'acompanhamento_nascimento',
            'historico_conhecido',
            'historico_desconhecido',
            'avaliacao_inicial',
            'inicio_inclusao'
        )),
    inclusion_date DATE NOT NULL DEFAULT CURRENT_DATE,
    initial_sanitary_notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE public.animals
    ADD COLUMN IF NOT EXISTS organization_id UUID REFERENCES public.organizations(id) ON DELETE RESTRICT,
    ADD COLUMN IF NOT EXISTS property_id UUID REFERENCES public.properties(id) ON DELETE RESTRICT,
    ADD COLUMN IF NOT EXISTS lot_id UUID REFERENCES public.lots(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS status VARCHAR(30) NOT NULL DEFAULT 'ativo',
    ADD COLUMN IF NOT EXISTS origin_type VARCHAR(30) NOT NULL DEFAULT 'nascido_propriedade',
    ADD COLUMN IF NOT EXISTS sanitary_onboarding_mode VARCHAR(40) NOT NULL DEFAULT 'acompanhamento_nascimento',
    ADD COLUMN IF NOT EXISTS inclusion_date DATE NOT NULL DEFAULT CURRENT_DATE,
    ADD COLUMN IF NOT EXISTS initial_sanitary_notes TEXT;

CREATE INDEX IF NOT EXISTS idx_animals_ear_tag ON public.animals (ear_tag);
CREATE INDEX IF NOT EXISTS idx_animals_qr_code_token ON public.animals (qr_code_token);
CREATE INDEX IF NOT EXISTS idx_animals_created_at ON public.animals (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_animals_property ON public.animals (property_id);
CREATE INDEX IF NOT EXISTS idx_animals_lot ON public.animals (lot_id);

-- 7. Catálogo Preventivo (`vaccines` — Vacinas, Vermífugos e Exames Sanitários)
CREATE TABLE IF NOT EXISTS public.vaccines (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES public.organizations(id) ON DELETE RESTRICT,
    commercial_name VARCHAR(150) NOT NULL,
    manufacturer VARCHAR(150) NOT NULL,
    item_type VARCHAR(30) NOT NULL DEFAULT 'vacina'
        CHECK (item_type IN ('vacina', 'vermifugo', 'exame_preventivo')),
    target_species VARCHAR(20) NOT NULL DEFAULT 'todas'
        CHECK (target_species IN ('todas', 'bovino', 'equino', 'ovino')),
    description TEXT,
    administration_route VARCHAR(80) NOT NULL,
    dosage_unit VARCHAR(30) NOT NULL DEFAULT 'mL',
    notes TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 8. Protocolos Sanitários (`sanitary_protocols`)
CREATE TABLE IF NOT EXISTS public.sanitary_protocols (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES public.organizations(id) ON DELETE RESTRICT,
    property_id UUID NOT NULL REFERENCES public.properties(id) ON DELETE RESTRICT,
    name VARCHAR(160) NOT NULL,
    description TEXT,
    target_species VARCHAR(20) NOT NULL DEFAULT 'bovino'
        CHECK (target_species IN ('todas', 'bovino', 'equino', 'ovino')),
    animal_category VARCHAR(40) NOT NULL DEFAULT 'todas'
        CHECK (animal_category IN ('todas', 'recem_nascido', 'lactente', 'bezerro', 'jovem', 'adulto')),
    purpose VARCHAR(40) NOT NULL
        CHECK (purpose IN ('corte', 'leite', 'reproducao', 'esporte_trabalho', 'la', 'geral')),
    validated_by VARCHAR(150),
    validated_at TIMESTAMPTZ,
    is_validated BOOLEAN NOT NULL DEFAULT FALSE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 9. Regras dos Protocolos (`sanitary_protocol_rules`)
CREATE TABLE IF NOT EXISTS public.sanitary_protocol_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES public.organizations(id) ON DELETE RESTRICT,
    protocol_id UUID NOT NULL REFERENCES public.sanitary_protocols(id) ON DELETE CASCADE,
    vaccine_id UUID NOT NULL REFERENCES public.vaccines(id) ON DELETE RESTRICT,
    min_age_days INTEGER NOT NULL CHECK (min_age_days >= 0),
    max_age_days INTEGER NOT NULL CHECK (max_age_days >= min_age_days),
    dose_number INTEGER NOT NULL DEFAULT 1 CHECK (dose_number >= 1),
    booster_interval_days INTEGER CHECK (booster_interval_days IS NULL OR booster_interval_days > 0),
    notes TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 10. Vínculo Animal x Protocolo (`animal_protocols`)
CREATE TABLE IF NOT EXISTS public.animal_protocols (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES public.organizations(id) ON DELETE RESTRICT,
    property_id UUID NOT NULL REFERENCES public.properties(id) ON DELETE RESTRICT,
    animal_id UUID NOT NULL REFERENCES public.animals(id) ON DELETE CASCADE,
    protocol_id UUID NOT NULL REFERENCES public.sanitary_protocols(id) ON DELETE RESTRICT,
    onboarding_mode VARCHAR(40) NOT NULL DEFAULT 'acompanhamento_nascimento'
        CHECK (onboarding_mode IN (
            'acompanhamento_nascimento',
            'historico_conhecido',
            'historico_desconhecido',
            'avaliacao_inicial',
            'inicio_inclusao'
        )),
    reference_date DATE NOT NULL DEFAULT CURRENT_DATE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (animal_id, protocol_id)
);

-- 11. Campanhas de Vacinação (`vaccination_campaigns`)
CREATE TABLE IF NOT EXISTS public.vaccination_campaigns (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES public.organizations(id) ON DELETE RESTRICT,
    property_id UUID NOT NULL REFERENCES public.properties(id) ON DELETE RESTRICT,
    lot_id UUID REFERENCES public.lots(id) ON DELETE SET NULL,
    vaccine_id UUID NOT NULL REFERENCES public.vaccines(id) ON DELETE RESTRICT,
    selection_mode VARCHAR(20) NOT NULL DEFAULT 'lote'
        CHECK (selection_mode IN ('lote', 'manual')),
    name VARCHAR(160) NOT NULL,
    scheduled_date DATE NOT NULL,
    description TEXT,
    notes TEXT,
    status VARCHAR(30) NOT NULL DEFAULT 'programada'
        CHECK (status IN ('programada', 'em_andamento', 'concluida', 'cancelada')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 12. Agendamentos Individuais (`vaccination_schedules`)
CREATE TABLE IF NOT EXISTS public.vaccination_schedules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES public.organizations(id) ON DELETE RESTRICT,
    property_id UUID NOT NULL REFERENCES public.properties(id) ON DELETE RESTRICT,
    animal_id UUID NOT NULL REFERENCES public.animals(id) ON DELETE CASCADE,
    vaccine_id UUID NOT NULL REFERENCES public.vaccines(id) ON DELETE RESTRICT,
    protocol_id UUID REFERENCES public.sanitary_protocols(id) ON DELETE SET NULL,
    protocol_rule_id UUID REFERENCES public.sanitary_protocol_rules(id) ON DELETE SET NULL,
    campaign_id UUID REFERENCES public.vaccination_campaigns(id) ON DELETE SET NULL,
    origin_type VARCHAR(30) NOT NULL DEFAULT 'protocolo'
        CHECK (origin_type IN ('protocolo', 'campanha', 'reforco', 'manual', 'avaliacao_inicial')),
    dose_number INTEGER NOT NULL DEFAULT 1 CHECK (dose_number >= 1),
    scheduled_date DATE NOT NULL,
    window_end_date DATE,
    status VARCHAR(30) NOT NULL DEFAULT 'pendente'
        CHECK (status IN (
            'pendente',
            'proxima_aplicacao',
            'atrasada',
            'aplicada',
            'nao_realizada',
            'historico_desconhecido',
            'cancelada'
        )),
    status_reason TEXT,
    notes TEXT,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (window_end_date IS NULL OR window_end_date >= scheduled_date)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_uq_schedule_animal_rule_dose
    ON public.vaccination_schedules (animal_id, protocol_rule_id, dose_number)
    WHERE protocol_rule_id IS NOT NULL AND status <> 'cancelada';

CREATE UNIQUE INDEX IF NOT EXISTS idx_uq_schedule_campaign_animal
    ON public.vaccination_schedules (campaign_id, animal_id)
    WHERE campaign_id IS NOT NULL AND status <> 'cancelada';

-- 13. Registros Efetivos de Aplicações (`vaccination_records`)
CREATE TABLE IF NOT EXISTS public.vaccination_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES public.organizations(id) ON DELETE RESTRICT,
    property_id UUID NOT NULL REFERENCES public.properties(id) ON DELETE RESTRICT,
    animal_id UUID NOT NULL REFERENCES public.animals(id) ON DELETE RESTRICT,
    vaccine_id UUID NOT NULL REFERENCES public.vaccines(id) ON DELETE RESTRICT,
    schedule_id UUID REFERENCES public.vaccination_schedules(id) ON DELETE SET NULL,
    campaign_id UUID REFERENCES public.vaccination_campaigns(id) ON DELETE SET NULL,
    dose_number INTEGER NOT NULL DEFAULT 1 CHECK (dose_number >= 1),
    applied_at TIMESTAMPTZ NOT NULL,
    dosage NUMERIC(8, 2) NOT NULL CHECK (dosage >= 0),
    dosage_unit VARCHAR(30) NOT NULL,
    administration_route VARCHAR(80) NOT NULL,
    manufacturer VARCHAR(150) NOT NULL,
    product_batch VARCHAR(100),
    product_expiry DATE,
    exam_result VARCHAR(100),
    applied_by VARCHAR(150) NOT NULL,
    next_dose_date DATE,
    is_historical_record BOOLEAN NOT NULL DEFAULT FALSE,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 14. Ocorrências Sanitárias e Registros Veterinários (`health_records`)
CREATE TABLE IF NOT EXISTS public.health_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES public.organizations(id) ON DELETE RESTRICT,
    property_id UUID NOT NULL REFERENCES public.properties(id) ON DELETE RESTRICT,
    animal_id UUID NOT NULL REFERENCES public.animals(id) ON DELETE RESTRICT,
    related_vaccination_record_id UUID REFERENCES public.vaccination_records(id) ON DELETE SET NULL,
    related_schedule_id UUID REFERENCES public.vaccination_schedules(id) ON DELETE SET NULL,
    record_type VARCHAR(40) NOT NULL
        CHECK (record_type IN (
            'tratamento',
            'ocorrencia',
            'observacao_veterinaria',
            'avaliacao_inicial',
            'correcao_historico'
        )),
    title VARCHAR(160) NOT NULL,
    description TEXT NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    veterinarian_or_responsible VARCHAR(150),
    medication_applied VARCHAR(150),
    dosage_info VARCHAR(100),
    is_private BOOLEAN NOT NULL DEFAULT TRUE,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Dados estruturais mínimos iniciais
INSERT INTO public.organizations (id, name, slug)
VALUES ('11111111-1111-4111-8111-111111111111', 'Agropecuária BoviTrack', 'agropecuaria-bovitrack')
ON CONFLICT (slug) DO NOTHING;

INSERT INTO public.properties (id, organization_id, name, code, municipality, state, production_focus)
VALUES (
    '22222222-2222-4222-8222-222222222222',
    (SELECT id FROM public.organizations WHERE slug = 'agropecuaria-bovitrack' LIMIT 1),
    'Fazenda Sede BoviTrack',
    'FAZ-01',
    'Uberaba',
    'MG',
    'corte'
)
ON CONFLICT (id) DO NOTHING;

INSERT INTO public.age_classifications (id, organization_id, slug, name, min_days, max_days, sort_order)
VALUES
    ('33333333-3333-4333-8333-000000000001', (SELECT id FROM public.organizations WHERE slug = 'agropecuaria-bovitrack' LIMIT 1), 'recem_nascido', 'Recém-nascido', 0, 30, 1),
    ('33333333-3333-4333-8333-000000000002', (SELECT id FROM public.organizations WHERE slug = 'agropecuaria-bovitrack' LIMIT 1), 'lactente', 'Lactente / Filhote', 31, 180, 2),
    ('33333333-3333-4333-8333-000000000003', (SELECT id FROM public.organizations WHERE slug = 'agropecuaria-bovitrack' LIMIT 1), 'jovem', 'Jovem', 181, 365, 3),
    ('33333333-3333-4333-8333-000000000004', (SELECT id FROM public.organizations WHERE slug = 'agropecuaria-bovitrack' LIMIT 1), 'adulto', 'Adulto', 366, NULL, 4)
ON CONFLICT (id) DO NOTHING;

-- Funções e Políticas RLS
CREATE OR REPLACE FUNCTION public.user_has_org_access(target_org_id UUID)
RETURNS BOOLEAN
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
    SELECT EXISTS (
        SELECT 1 FROM public.organization_members om
        WHERE om.user_id = auth.uid() AND om.organization_id = target_org_id AND om.is_active = TRUE
    );
$$;

CREATE OR REPLACE FUNCTION public.user_has_property_access(target_org_id UUID, target_property_id UUID)
RETURNS BOOLEAN
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
    SELECT EXISTS (
        SELECT 1 FROM public.organization_members om
        WHERE om.user_id = auth.uid()
          AND om.organization_id = target_org_id
          AND om.is_active = TRUE
          AND (om.property_id IS NULL OR om.property_id = target_property_id)
    );
$$;

ALTER TABLE public.organizations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.organization_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.properties ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.lots ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.age_classifications ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.animals ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.vaccines ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.sanitary_protocols ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.sanitary_protocol_rules ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.animal_protocols ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.vaccination_campaigns ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.vaccination_schedules ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.vaccination_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.health_records ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "rls_organizations_member_select" ON public.organizations;
CREATE POLICY "rls_organizations_member_select" ON public.organizations FOR SELECT TO authenticated USING (public.user_has_org_access(id));

DROP POLICY IF EXISTS "rls_org_members_self_select" ON public.organization_members;
CREATE POLICY "rls_org_members_self_select" ON public.organization_members FOR SELECT TO authenticated USING (user_id = auth.uid() OR public.user_has_org_access(organization_id));

DROP POLICY IF EXISTS "rls_properties_access" ON public.properties;
CREATE POLICY "rls_properties_access" ON public.properties FOR ALL TO authenticated USING (public.user_has_property_access(organization_id, id)) WITH CHECK (public.user_has_property_access(organization_id, id));

DROP POLICY IF EXISTS "rls_lots_access" ON public.lots;
CREATE POLICY "rls_lots_access" ON public.lots FOR ALL TO authenticated USING (public.user_has_property_access(organization_id, property_id)) WITH CHECK (public.user_has_property_access(organization_id, property_id));

DROP POLICY IF EXISTS "rls_age_classifications_access" ON public.age_classifications;
CREATE POLICY "rls_age_classifications_access" ON public.age_classifications FOR ALL TO authenticated USING (organization_id IS NULL OR public.user_has_org_access(organization_id)) WITH CHECK (public.user_has_org_access(organization_id));

DROP POLICY IF EXISTS "rls_animals_access" ON public.animals;
CREATE POLICY "rls_animals_access" ON public.animals FOR ALL TO authenticated USING (public.user_has_property_access(organization_id, property_id)) WITH CHECK (public.user_has_property_access(organization_id, property_id));

DROP POLICY IF EXISTS "rls_vaccines_access" ON public.vaccines;
CREATE POLICY "rls_vaccines_access" ON public.vaccines FOR ALL TO authenticated USING (public.user_has_org_access(organization_id)) WITH CHECK (public.user_has_org_access(organization_id));

DROP POLICY IF EXISTS "rls_protocols_access" ON public.sanitary_protocols;
CREATE POLICY "rls_protocols_access" ON public.sanitary_protocols FOR ALL TO authenticated USING (public.user_has_property_access(organization_id, property_id)) WITH CHECK (public.user_has_property_access(organization_id, property_id));

DROP POLICY IF EXISTS "rls_protocol_rules_access" ON public.sanitary_protocol_rules;
CREATE POLICY "rls_protocol_rules_access" ON public.sanitary_protocol_rules FOR ALL TO authenticated USING (public.user_has_org_access(organization_id)) WITH CHECK (public.user_has_org_access(organization_id));

DROP POLICY IF EXISTS "rls_animal_protocols_access" ON public.animal_protocols;
CREATE POLICY "rls_animal_protocols_access" ON public.animal_protocols FOR ALL TO authenticated USING (public.user_has_property_access(organization_id, property_id)) WITH CHECK (public.user_has_property_access(organization_id, property_id));

DROP POLICY IF EXISTS "rls_campaigns_access" ON public.vaccination_campaigns;
CREATE POLICY "rls_campaigns_access" ON public.vaccination_campaigns FOR ALL TO authenticated USING (public.user_has_property_access(organization_id, property_id)) WITH CHECK (public.user_has_property_access(organization_id, property_id));

DROP POLICY IF EXISTS "rls_schedules_access" ON public.vaccination_schedules;
CREATE POLICY "rls_schedules_access" ON public.vaccination_schedules FOR ALL TO authenticated USING (public.user_has_property_access(organization_id, property_id)) WITH CHECK (public.user_has_property_access(organization_id, property_id));

DROP POLICY IF EXISTS "rls_vac_records_access" ON public.vaccination_records;
CREATE POLICY "rls_vac_records_access" ON public.vaccination_records FOR ALL TO authenticated USING (public.user_has_property_access(organization_id, property_id)) WITH CHECK (public.user_has_property_access(organization_id, property_id));

DROP POLICY IF EXISTS "rls_health_records_access" ON public.health_records;
CREATE POLICY "rls_health_records_access" ON public.health_records FOR ALL TO authenticated USING (public.user_has_property_access(organization_id, property_id)) WITH CHECK (public.user_has_property_access(organization_id, property_id));


-- ============================================================================
-- 15. Impressão em Lote e Controle de Etiquetas QR Code (`tag_batches`, `tag_units`)
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.tag_batches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES public.organizations(id) ON DELETE RESTRICT,
    property_id UUID REFERENCES public.properties(id) ON DELETE SET NULL,
    batch_name VARCHAR(160) NOT NULL,
    prefix VARCHAR(30) NOT NULL DEFAULT 'BT-',
    padding_digits INTEGER NOT NULL DEFAULT 5 CHECK (padding_digits BETWEEN 1 AND 12),
    start_number INTEGER NOT NULL CHECK (start_number >= 0),
    end_number INTEGER NOT NULL CHECK (end_number >= start_number),
    quantity INTEGER NOT NULL CHECK (quantity >= 1),
    custom_text VARCHAR(120),
    layout_config JSONB NOT NULL DEFAULT '{}'::JSONB,
    created_by VARCHAR(150),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.tag_units (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES public.organizations(id) ON DELETE RESTRICT,
    batch_id UUID REFERENCES public.tag_batches(id) ON DELETE SET NULL,
    animal_id UUID REFERENCES public.animals(id) ON DELETE SET NULL,
    tag_number VARCHAR(100) NOT NULL,
    qr_token UUID NOT NULL UNIQUE DEFAULT gen_random_uuid(),
    status VARCHAR(20) NOT NULL DEFAULT 'available'
        CHECK (status IN ('available', 'assigned', 'activated', 'retired')),
    custom_text VARCHAR(120),
    assigned_at TIMESTAMPTZ,
    activated_at TIMESTAMPTZ,
    retired_at TIMESTAMPTZ,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (organization_id, tag_number)
);

CREATE INDEX IF NOT EXISTS idx_tag_units_org_status ON public.tag_units (organization_id, status);
CREATE INDEX IF NOT EXISTS idx_tag_units_qr_token ON public.tag_units (qr_token);

ALTER TABLE public.tag_batches ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.tag_units ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "rls_tag_batches_access" ON public.tag_batches;
CREATE POLICY "rls_tag_batches_access" ON public.tag_batches
    FOR ALL TO authenticated
    USING (public.user_has_org_access(organization_id))
    WITH CHECK (public.user_has_org_access(organization_id));

DROP POLICY IF EXISTS "rls_tag_units_access" ON public.tag_units;
CREATE POLICY "rls_tag_units_access" ON public.tag_units
    FOR ALL TO authenticated
    USING (public.user_has_org_access(organization_id))
    WITH CHECK (public.user_has_org_access(organization_id));


-- ============================================================================
-- 16. Rotinas de Manejo por Espécie (`management_records`) e Cocho (`feeding_plans`)
-- ============================================================================
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
