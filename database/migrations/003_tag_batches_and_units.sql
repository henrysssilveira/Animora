-- ============================================================================
-- BoviTrack — Impressão em Lote de Etiquetas QR Code
-- Migration 003: Tabelas `tag_batches` (histórico de conjuntos) e `tag_units`
--                (controle individual de etiquetas exclusivas + RLS)
-- ============================================================================
-- Execute este script no SQL Editor do painel do Supabase.
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ----------------------------------------------------------------------------
-- 1. Conjuntos / Lotes de Impressão Gerados (`tag_batches`)
-- ----------------------------------------------------------------------------
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

CREATE INDEX IF NOT EXISTS idx_tag_batches_org_created
    ON public.tag_batches (organization_id, created_at DESC);

COMMENT ON TABLE public.tag_batches IS 'Histórico dos conjuntos de etiquetas QR Code gerados em lote e suas configurações de impressão.';

-- ----------------------------------------------------------------------------
-- 2. Controle Individual das Etiquetas (`tag_units`)
-- ----------------------------------------------------------------------------
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

CREATE INDEX IF NOT EXISTS idx_tag_units_org_status
    ON public.tag_units (organization_id, status);
CREATE INDEX IF NOT EXISTS idx_tag_units_batch
    ON public.tag_units (batch_id, tag_number);
CREATE INDEX IF NOT EXISTS idx_tag_units_qr_token
    ON public.tag_units (qr_token);
CREATE INDEX IF NOT EXISTS idx_tag_units_animal
    ON public.tag_units (animal_id);

COMMENT ON TABLE public.tag_units IS 'Etiquetas individuais de identificação BoviTrack com token QR exclusivo e controle de disponibilidade.';
COMMENT ON COLUMN public.tag_units.tag_number IS 'Numeração visível impressa na etiqueta (única por organização, ex.: BT-00001).';
COMMENT ON COLUMN public.tag_units.qr_token IS 'Token aleatório UUID exclusivo utilizado na URL do QR Code.';
COMMENT ON COLUMN public.tag_units.status IS 'Estado do ciclo de vida: available, assigned, activated ou retired.';

-- ----------------------------------------------------------------------------
-- 3. Políticas Row Level Security (RLS)
-- ----------------------------------------------------------------------------
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
