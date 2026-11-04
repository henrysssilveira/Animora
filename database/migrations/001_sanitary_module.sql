-- ============================================================================
-- BoviTrack — Módulo de Gestão Sanitária e Vacinação Inteligente
-- Migration 001: Estrutura Multi-Propriedade, Protocolos, Vacinas, Campanhas,
--                Agendamentos, Registros Sanitários e Políticas RLS
-- ============================================================================
-- Seguro para execução em bancos que já possuem a tabela `public.animals`.
-- Execute este script no SQL Editor do painel do Supabase.
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ----------------------------------------------------------------------------
-- 1. Organizações e Membros (Base para isolamento multi-organização e RLS)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.organizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(150) NOT NULL,
    slug VARCHAR(100) NOT NULL UNIQUE,
    document VARCHAR(30),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE public.organizations IS 'Organizações ou grupos rurais titulares das propriedades no BoviTrack.';

-- ----------------------------------------------------------------------------
-- 2. Propriedades Rurais e Lotes de Manejo
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.properties (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES public.organizations(id) ON DELETE RESTRICT,
    name VARCHAR(150) NOT NULL,
    code VARCHAR(50),
    municipality VARCHAR(100),
    state CHAR(2),
    production_focus VARCHAR(20) NOT NULL DEFAULT 'corte'
        CHECK (production_focus IN ('corte', 'leite', 'misto')),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_properties_org ON public.properties (organization_id);

COMMENT ON TABLE public.properties IS 'Propriedades rurais (fazendas/sítios) vinculadas a uma organização.';

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
CREATE INDEX IF NOT EXISTS idx_org_members_org ON public.organization_members (organization_id);

CREATE TABLE IF NOT EXISTS public.lots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES public.organizations(id) ON DELETE RESTRICT,
    property_id UUID NOT NULL REFERENCES public.properties(id) ON DELETE CASCADE,
    name VARCHAR(120) NOT NULL,
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (property_id, name)
);

CREATE INDEX IF NOT EXISTS idx_lots_property ON public.lots (property_id);
CREATE INDEX IF NOT EXISTS idx_lots_org ON public.lots (organization_id);

COMMENT ON TABLE public.lots IS 'Lotes de manejo de bovinos dentro de cada propriedade.';

-- ----------------------------------------------------------------------------
-- 3. Faixas Etárias Configuráveis
-- ----------------------------------------------------------------------------
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

CREATE INDEX IF NOT EXISTS idx_age_classifications_org ON public.age_classifications (organization_id, sort_order);

COMMENT ON TABLE public.age_classifications IS 'Faixas etárias configuráveis para classificação dinâmica dos animais.';

-- ----------------------------------------------------------------------------
-- 4. Adaptação da tabela existente `public.animals` (sem perda de dados)
-- ----------------------------------------------------------------------------
ALTER TABLE public.animals
    ADD COLUMN IF NOT EXISTS organization_id UUID REFERENCES public.organizations(id) ON DELETE RESTRICT,
    ADD COLUMN IF NOT EXISTS property_id UUID REFERENCES public.properties(id) ON DELETE RESTRICT,
    ADD COLUMN IF NOT EXISTS lot_id UUID REFERENCES public.lots(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS status VARCHAR(30) NOT NULL DEFAULT 'ativo',
    ADD COLUMN IF NOT EXISTS origin_type VARCHAR(30) NOT NULL DEFAULT 'nascido_propriedade',
    ADD COLUMN IF NOT EXISTS sanitary_onboarding_mode VARCHAR(40) NOT NULL DEFAULT 'acompanhamento_nascimento',
    ADD COLUMN IF NOT EXISTS inclusion_date DATE NOT NULL DEFAULT CURRENT_DATE,
    ADD COLUMN IF NOT EXISTS initial_sanitary_notes TEXT;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'chk_animals_status'
    ) THEN
        ALTER TABLE public.animals
            ADD CONSTRAINT chk_animals_status
            CHECK (status IN ('ativo', 'inativo', 'vendido', 'obito'));
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'chk_animals_origin_type'
    ) THEN
        ALTER TABLE public.animals
            ADD CONSTRAINT chk_animals_origin_type
            CHECK (origin_type IN ('nascido_propriedade', 'adquirido_externo', 'pre_existente'));
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'chk_animals_onboarding_mode'
    ) THEN
        ALTER TABLE public.animals
            ADD CONSTRAINT chk_animals_onboarding_mode
            CHECK (sanitary_onboarding_mode IN (
                'acompanhamento_nascimento',
                'historico_conhecido',
                'historico_desconhecido',
                'avaliacao_inicial',
                'inicio_inclusao'
            ));
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_animals_org ON public.animals (organization_id);
CREATE INDEX IF NOT EXISTS idx_animals_property ON public.animals (property_id);
CREATE INDEX IF NOT EXISTS idx_animals_lot ON public.animals (lot_id);
CREATE INDEX IF NOT EXISTS idx_animals_birth_date ON public.animals (birth_date);
CREATE INDEX IF NOT EXISTS idx_animals_status ON public.animals (status);

-- ----------------------------------------------------------------------------
-- 5. Catálogo de Vacinas (`vaccines`)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.vaccines (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES public.organizations(id) ON DELETE RESTRICT,
    commercial_name VARCHAR(150) NOT NULL,
    manufacturer VARCHAR(150) NOT NULL,
    description TEXT,
    administration_route VARCHAR(80) NOT NULL,
    dosage_unit VARCHAR(30) NOT NULL DEFAULT 'mL',
    notes TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_vaccines_org ON public.vaccines (organization_id);
CREATE INDEX IF NOT EXISTS idx_vaccines_active ON public.vaccines (is_active);

COMMENT ON TABLE public.vaccines IS 'Catálogo de vacinas utilizado pelos protocolos sanitários, campanhas e registros.';

-- ----------------------------------------------------------------------------
-- 6. Protocolos Sanitários (`sanitary_protocols`) e Regras (`sanitary_protocol_rules`)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.sanitary_protocols (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES public.organizations(id) ON DELETE RESTRICT,
    property_id UUID NOT NULL REFERENCES public.properties(id) ON DELETE RESTRICT,
    name VARCHAR(160) NOT NULL,
    description TEXT,
    animal_category VARCHAR(40) NOT NULL DEFAULT 'todas'
        CHECK (animal_category IN ('todas', 'recem_nascido', 'bezerro', 'jovem', 'adulto')),
    purpose VARCHAR(20) NOT NULL
        CHECK (purpose IN ('corte', 'leite')),
    validated_by VARCHAR(150),
    validated_at TIMESTAMPTZ,
    is_validated BOOLEAN NOT NULL DEFAULT FALSE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_protocols_property ON public.sanitary_protocols (property_id);
CREATE INDEX IF NOT EXISTS idx_protocols_org ON public.sanitary_protocols (organization_id);
CREATE INDEX IF NOT EXISTS idx_protocols_active_valid ON public.sanitary_protocols (property_id, is_active, is_validated);

COMMENT ON TABLE public.sanitary_protocols IS 'Protocolos sanitários configuráveis e validados pelo responsável técnico de cada propriedade.';

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

CREATE INDEX IF NOT EXISTS idx_protocol_rules_protocol ON public.sanitary_protocol_rules (protocol_id);
CREATE INDEX IF NOT EXISTS idx_protocol_rules_vaccine ON public.sanitary_protocol_rules (vaccine_id);

COMMENT ON TABLE public.sanitary_protocol_rules IS 'Regras de vacinação por faixa de idade (dias), dose e intervalo vinculadas a um protocolo.';

-- ----------------------------------------------------------------------------
-- 7. Vínculo entre Animais e Protocolos (`animal_protocols`)
-- ----------------------------------------------------------------------------
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

CREATE INDEX IF NOT EXISTS idx_animal_protocols_animal ON public.animal_protocols (animal_id);
CREATE INDEX IF NOT EXISTS idx_animal_protocols_protocol ON public.animal_protocols (protocol_id);

COMMENT ON TABLE public.animal_protocols IS 'Vínculo entre cada animal e os protocolos sanitários acompanhados na propriedade.';

-- ----------------------------------------------------------------------------
-- 8. Campanhas de Vacinação (`vaccination_campaigns`)
-- ----------------------------------------------------------------------------
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

CREATE INDEX IF NOT EXISTS idx_campaigns_property ON public.vaccination_campaigns (property_id);
CREATE INDEX IF NOT EXISTS idx_campaigns_date ON public.vaccination_campaigns (scheduled_date);
CREATE INDEX IF NOT EXISTS idx_campaigns_status ON public.vaccination_campaigns (status);

COMMENT ON TABLE public.vaccination_campaigns IS 'Campanhas e cartelas coletivas de vacinação por propriedade/lote ou seleção manual.';

-- ----------------------------------------------------------------------------
-- 9. Agendamentos Individuais (`vaccination_schedules`)
-- ----------------------------------------------------------------------------
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

CREATE INDEX IF NOT EXISTS idx_schedules_animal ON public.vaccination_schedules (animal_id);
CREATE INDEX IF NOT EXISTS idx_schedules_property_date ON public.vaccination_schedules (property_id, scheduled_date);
CREATE INDEX IF NOT EXISTS idx_schedules_campaign ON public.vaccination_schedules (campaign_id);
CREATE INDEX IF NOT EXISTS idx_schedules_status ON public.vaccination_schedules (status);
CREATE INDEX IF NOT EXISTS idx_schedules_vaccine ON public.vaccination_schedules (vaccine_id);

-- Restrições parciais anti-duplicação
CREATE UNIQUE INDEX IF NOT EXISTS idx_uq_schedule_animal_rule_dose
    ON public.vaccination_schedules (animal_id, protocol_rule_id, dose_number)
    WHERE protocol_rule_id IS NOT NULL AND status <> 'cancelada';

CREATE UNIQUE INDEX IF NOT EXISTS idx_uq_schedule_campaign_animal
    ON public.vaccination_schedules (campaign_id, animal_id)
    WHERE campaign_id IS NOT NULL AND status <> 'cancelada';

COMMENT ON TABLE public.vaccination_schedules IS 'Agendamentos individuais de vacinação gerados por protocolos, campanhas ou reforços.';

-- ----------------------------------------------------------------------------
-- 10. Registros Efetivos de Aplicações (`vaccination_records` — Histórico Permanente)
-- ----------------------------------------------------------------------------
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
    dosage NUMERIC(8, 2) NOT NULL CHECK (dosage > 0),
    dosage_unit VARCHAR(30) NOT NULL,
    administration_route VARCHAR(80) NOT NULL,
    manufacturer VARCHAR(150) NOT NULL,
    product_batch VARCHAR(100),
    product_expiry DATE,
    applied_by VARCHAR(150) NOT NULL,
    next_dose_date DATE,
    is_historical_record BOOLEAN NOT NULL DEFAULT FALSE,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_vac_records_animal ON public.vaccination_records (animal_id, applied_at DESC);
CREATE INDEX IF NOT EXISTS idx_vac_records_property ON public.vaccination_records (property_id, applied_at DESC);
CREATE INDEX IF NOT EXISTS idx_vac_records_schedule ON public.vaccination_records (schedule_id);
CREATE INDEX IF NOT EXISTS idx_vac_records_campaign ON public.vaccination_records (campaign_id);

COMMENT ON TABLE public.vaccination_records IS 'Registros permanentes e imutáveis de vacinações efetivamente aplicadas ou histórico anterior informado.';

-- ----------------------------------------------------------------------------
-- 11. Ocorrências Sanitárias e Registros Veterinários (`health_records`)
-- ----------------------------------------------------------------------------
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

CREATE INDEX IF NOT EXISTS idx_health_records_animal ON public.health_records (animal_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_health_records_property ON public.health_records (property_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_health_records_type ON public.health_records (record_type);

COMMENT ON TABLE public.health_records IS 'Histórico clínico, tratamentos, ocorrências sanitárias, avaliações iniciais e retificações auditáveis.';

-- ----------------------------------------------------------------------------
-- 12. Dados Estruturais Iniciais + Migração Automática de Animais Pré-Existentes
-- ----------------------------------------------------------------------------
INSERT INTO public.organizations (id, name, slug, document)
VALUES (
    '11111111-1111-4111-8111-111111111111',
    'Agropecuária BoviTrack',
    'agropecuaria-bovitrack',
    NULL
)
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

-- Faixas etárias iniciais configuráveis
INSERT INTO public.age_classifications (id, organization_id, slug, name, min_days, max_days, sort_order)
VALUES
    ('33333333-3333-4333-8333-000000000001', (SELECT id FROM public.organizations WHERE slug = 'agropecuaria-bovitrack' LIMIT 1), 'recem_nascido', 'Recém-nascido', 0, 30, 1),
    ('33333333-3333-4333-8333-000000000002', (SELECT id FROM public.organizations WHERE slug = 'agropecuaria-bovitrack' LIMIT 1), 'bezerro', 'Bezerro', 31, 180, 2),
    ('33333333-3333-4333-8333-000000000003', (SELECT id FROM public.organizations WHERE slug = 'agropecuaria-bovitrack' LIMIT 1), 'jovem', 'Jovem', 181, 365, 3),
    ('33333333-3333-4333-8333-000000000004', (SELECT id FROM public.organizations WHERE slug = 'agropecuaria-bovitrack' LIMIT 1), 'adulto', 'Adulto', 366, NULL, 4)
ON CONFLICT (id) DO NOTHING;

-- Vincula animais já existentes no banco à organização/propriedade padrão
-- tratando animais pré-existentes > 30 dias com histórico desconhecido (evitando falso atraso)
UPDATE public.animals
SET
    organization_id = COALESCE(
        organization_id,
        (SELECT id FROM public.organizations WHERE slug = 'agropecuaria-bovitrack' LIMIT 1)
    ),
    property_id = COALESCE(
        property_id,
        '22222222-2222-4222-8222-222222222222'::UUID
    ),
    origin_type = CASE
        WHEN property_id IS NULL THEN 'pre_existente'
        ELSE origin_type
    END,
    sanitary_onboarding_mode = CASE
        WHEN property_id IS NULL AND (CURRENT_DATE - birth_date) > 30 THEN 'historico_desconhecido'
        ELSE sanitary_onboarding_mode
    END
WHERE organization_id IS NULL OR property_id IS NULL;

-- ----------------------------------------------------------------------------
-- 13. Row Level Security (RLS) Multi-Organização e Multi-Propriedade
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.user_has_org_access(target_org_id UUID)
RETURNS BOOLEAN
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
    SELECT EXISTS (
        SELECT 1
        FROM public.organization_members om
        WHERE om.user_id = auth.uid()
          AND om.organization_id = target_org_id
          AND om.is_active = TRUE
    );
$$;

CREATE OR REPLACE FUNCTION public.user_has_property_access(target_org_id UUID, target_property_id UUID)
RETURNS BOOLEAN
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
    SELECT EXISTS (
        SELECT 1
        FROM public.organization_members om
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

-- Políticas por tabela (isolando acesso de usuários autenticados às suas organizações/propriedades
-- e impedindo acesso anônimo direto a tabelas veterinárias privadas; o backend Flask utiliza service_role)
DROP POLICY IF EXISTS "rls_organizations_member_select" ON public.organizations;
CREATE POLICY "rls_organizations_member_select" ON public.organizations
    FOR SELECT TO authenticated
    USING (public.user_has_org_access(id));

DROP POLICY IF EXISTS "rls_org_members_self_select" ON public.organization_members;
CREATE POLICY "rls_org_members_self_select" ON public.organization_members
    FOR SELECT TO authenticated
    USING (user_id = auth.uid() OR public.user_has_org_access(organization_id));

DROP POLICY IF EXISTS "rls_properties_access" ON public.properties;
CREATE POLICY "rls_properties_access" ON public.properties
    FOR ALL TO authenticated
    USING (public.user_has_property_access(organization_id, id))
    WITH CHECK (public.user_has_property_access(organization_id, id));

DROP POLICY IF EXISTS "rls_lots_access" ON public.lots;
CREATE POLICY "rls_lots_access" ON public.lots
    FOR ALL TO authenticated
    USING (public.user_has_property_access(organization_id, property_id))
    WITH CHECK (public.user_has_property_access(organization_id, property_id));

DROP POLICY IF EXISTS "rls_age_classifications_access" ON public.age_classifications;
CREATE POLICY "rls_age_classifications_access" ON public.age_classifications
    FOR ALL TO authenticated
    USING (organization_id IS NULL OR public.user_has_org_access(organization_id))
    WITH CHECK (public.user_has_org_access(organization_id));

DROP POLICY IF EXISTS "rls_animals_access" ON public.animals;
CREATE POLICY "rls_animals_access" ON public.animals
    FOR ALL TO authenticated
    USING (public.user_has_property_access(organization_id, property_id))
    WITH CHECK (public.user_has_property_access(organization_id, property_id));

DROP POLICY IF EXISTS "rls_vaccines_access" ON public.vaccines;
CREATE POLICY "rls_vaccines_access" ON public.vaccines
    FOR ALL TO authenticated
    USING (public.user_has_org_access(organization_id))
    WITH CHECK (public.user_has_org_access(organization_id));

DROP POLICY IF EXISTS "rls_protocols_access" ON public.sanitary_protocols;
CREATE POLICY "rls_protocols_access" ON public.sanitary_protocols
    FOR ALL TO authenticated
    USING (public.user_has_property_access(organization_id, property_id))
    WITH CHECK (public.user_has_property_access(organization_id, property_id));

DROP POLICY IF EXISTS "rls_protocol_rules_access" ON public.sanitary_protocol_rules;
CREATE POLICY "rls_protocol_rules_access" ON public.sanitary_protocol_rules
    FOR ALL TO authenticated
    USING (public.user_has_org_access(organization_id))
    WITH CHECK (public.user_has_org_access(organization_id));

DROP POLICY IF EXISTS "rls_animal_protocols_access" ON public.animal_protocols;
CREATE POLICY "rls_animal_protocols_access" ON public.animal_protocols
    FOR ALL TO authenticated
    USING (public.user_has_property_access(organization_id, property_id))
    WITH CHECK (public.user_has_property_access(organization_id, property_id));

DROP POLICY IF EXISTS "rls_campaigns_access" ON public.vaccination_campaigns;
CREATE POLICY "rls_campaigns_access" ON public.vaccination_campaigns
    FOR ALL TO authenticated
    USING (public.user_has_property_access(organization_id, property_id))
    WITH CHECK (public.user_has_property_access(organization_id, property_id));

DROP POLICY IF EXISTS "rls_schedules_access" ON public.vaccination_schedules;
CREATE POLICY "rls_schedules_access" ON public.vaccination_schedules
    FOR ALL TO authenticated
    USING (public.user_has_property_access(organization_id, property_id))
    WITH CHECK (public.user_has_property_access(organization_id, property_id));

DROP POLICY IF EXISTS "rls_vac_records_access" ON public.vaccination_records;
CREATE POLICY "rls_vac_records_access" ON public.vaccination_records
    FOR ALL TO authenticated
    USING (public.user_has_property_access(organization_id, property_id))
    WITH CHECK (public.user_has_property_access(organization_id, property_id));

DROP POLICY IF EXISTS "rls_health_records_access" ON public.health_records;
CREATE POLICY "rls_health_records_access" ON public.health_records
    FOR ALL TO authenticated
    USING (public.user_has_property_access(organization_id, property_id))
    WITH CHECK (public.user_has_property_access(organization_id, property_id));
