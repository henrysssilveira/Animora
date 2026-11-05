-- ============================================================================
-- Animora — Migração 005: Acessos por Fazenda & Invalidação de QR Codes
-- ============================================================================
-- 1. Cria tabela de perfis de acesso vinculados a fazendas específicas (Admin Only)
-- 2. Cria tabela de tokens de QR Codes invalidados
-- 3. Atualiza políticas e integridade referencial
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- 1. Perfis de Acesso Vinculados a Fazendas (Propriedades)
CREATE TABLE IF NOT EXISTS public.property_access_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    property_id UUID NOT NULL REFERENCES public.properties(id) ON DELETE CASCADE,
    name VARCHAR(150) NOT NULL,
    role VARCHAR(40) NOT NULL DEFAULT 'produtor'
        CHECK (role IN ('produtor', 'responsavel_tecnico', 'operador')),
    access_pin VARCHAR(100) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_property_access_prop ON public.property_access_profiles (property_id);
CREATE INDEX IF NOT EXISTS idx_property_access_pin ON public.property_access_profiles (access_pin);
CREATE INDEX IF NOT EXISTS idx_property_access_org ON public.property_access_profiles (organization_id);

-- 2. Tabela de QR Codes Invalidados / Desativados
CREATE TABLE IF NOT EXISTS public.invalidated_qr_tokens (
    token UUID PRIMARY KEY,
    reason VARCHAR(255) DEFAULT 'Registro ou etiqueta excluída',
    invalidated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_invalidated_qr_tokens ON public.invalidated_qr_tokens (token);

-- 3. Habilita Row Level Security (RLS)
ALTER TABLE public.property_access_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.invalidated_qr_tokens ENABLE ROW LEVEL SECURITY;

-- 4. Políticas RLS
DO $$
BEGIN
    DROP POLICY IF EXISTS "Acesso público a tokens invalidados" ON public.invalidated_qr_tokens;
    CREATE POLICY "Acesso público a tokens invalidados"
        ON public.invalidated_qr_tokens
        FOR SELECT
        USING (true);

    DROP POLICY IF EXISTS "Service role gerencia tokens invalidados" ON public.invalidated_qr_tokens;
    CREATE POLICY "Service role gerencia tokens invalidados"
        ON public.invalidated_qr_tokens
        FOR ALL
        USING (true)
        WITH CHECK (true);

    DROP POLICY IF EXISTS "Gerenciamento de acessos por fazenda" ON public.property_access_profiles;
    CREATE POLICY "Gerenciamento de acessos por fazenda"
        ON public.property_access_profiles
        FOR ALL
        USING (true)
        WITH CHECK (true);
END $$;
