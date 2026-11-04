-- ============================================================================
-- BoviTrack — Limpeza Segura dos Dados Demonstrativos (Seed 002)
-- ============================================================================
-- Remove os dados fictícios inseridos por `database/seeds/002_demo_data.sql`
-- (animais DEMO-*, vacinas/protocolos/campanhas [DEMO], agendamentos, registros
-- clínicos de teste, além dos lotes demo e da propriedade "Estância Santa Clara"
-- caso não possuam vínculos com cadastros reais).
--
-- PRESERVA INTEGRALMENTE:
--   - Organização padrão ("Agropecuária BoviTrack") e "Fazenda Sede BoviTrack"
--   - Faixas etárias configuradas (`age_classifications`)
--   - Todos os animais, etiquetas, vacinas, protocolos e lotes reais criados por você
--
-- Pode ser executado quantas vezes desejar (idempotente) no SQL Editor do Supabase.
-- ============================================================================

BEGIN;

CREATE TEMP TABLE IF NOT EXISTS _demo_cleanup_report (
    ordem INT,
    etapa TEXT,
    registros_afetados INT,
    observacao TEXT
) ON COMMIT DROP;

TRUNCATE TABLE _demo_cleanup_report;

DO $$
DECLARE
    v_demo_animal_ids UUID[] := ARRAY[]::UUID[];
    v_demo_vaccine_ids UUID[] := ARRAY[]::UUID[];
    v_demo_protocol_ids UUID[] := ARRAY[]::UUID[];
    v_demo_rule_ids UUID[] := ARRAY[]::UUID[];
    v_demo_campaign_ids UUID[] := ARRAY[]::UUID[];
    v_count INT := 0;
    v_preserved_lots INT := 0;
    v_santa_clara_id CONSTANT UUID := '22222222-2222-4222-8222-222222222223';
    v_santa_clara_exists BOOLEAN := FALSE;
    v_santa_clara_in_use BOOLEAN := FALSE;
    v_tag_batch_refs INT := 0;
BEGIN
    IF to_regclass('public.animals') IS NULL THEN
        INSERT INTO _demo_cleanup_report VALUES (
            1, 'verificacao_inicial', 0, 'Tabela public.animals não encontrada. Nada a limpar.'
        );
        RETURN;
    END IF;

    -- 1. Identifica animais demonstrativos (IDs do seed 002 ou brinco DEMO-*)
    SELECT COALESCE(ARRAY_AGG(id), ARRAY[]::UUID[])
    INTO v_demo_animal_ids
    FROM public.animals
    WHERE id IN (
        '88888888-8888-4888-8888-000000000001',
        '88888888-8888-4888-8888-000000000002',
        '88888888-8888-4888-8888-000000000003',
        '88888888-8888-4888-8888-000000000004',
        '88888888-8888-4888-8888-000000000005'
    )
    OR ear_tag LIKE 'DEMO-%';

    -- 2. Se o Módulo Sanitário estiver instalado, remove dependências sanitárias na ordem das FKs
    IF to_regclass('public.vaccines') IS NOT NULL THEN
        SELECT COALESCE(ARRAY_AGG(id), ARRAY[]::UUID[])
        INTO v_demo_vaccine_ids
        FROM public.vaccines
        WHERE id IN (
            '55555555-5555-4555-8555-000000000001',
            '55555555-5555-4555-8555-000000000002',
            '55555555-5555-4555-8555-000000000003'
        )
        OR commercial_name ILIKE '%[DEMO]%';

        SELECT COALESCE(ARRAY_AGG(id), ARRAY[]::UUID[])
        INTO v_demo_protocol_ids
        FROM public.sanitary_protocols
        WHERE id IN (
            '66666666-6666-4666-8666-000000000001',
            '66666666-6666-4666-8666-000000000002'
        )
        OR name ILIKE '%[DEMO]%';

        SELECT COALESCE(ARRAY_AGG(id), ARRAY[]::UUID[])
        INTO v_demo_rule_ids
        FROM public.sanitary_protocol_rules
        WHERE id IN (
            '77777777-7777-4777-8777-000000000001',
            '77777777-7777-4777-8777-000000000002',
            '77777777-7777-4777-8777-000000000003',
            '77777777-7777-4777-8777-000000000004'
        )
        OR protocol_id = ANY(v_demo_protocol_ids)
        OR vaccine_id = ANY(v_demo_vaccine_ids);

        SELECT COALESCE(ARRAY_AGG(id), ARRAY[]::UUID[])
        INTO v_demo_campaign_ids
        FROM public.vaccination_campaigns
        WHERE id = 'aaaaaaaa-aaaa-4aaa-8aaa-000000000001'
        OR name ILIKE '%[DEMO]%'
        OR vaccine_id = ANY(v_demo_vaccine_ids);

        -- 2.1 Ocorrências e observações veterinárias (`health_records`)
        DELETE FROM public.health_records
        WHERE id IN (
            'dddddddd-dddd-4ddd-8ddd-000000000001',
            'dddddddd-dddd-4ddd-8ddd-000000000002'
        )
        OR animal_id = ANY(v_demo_animal_ids);
        GET DIAGNOSTICS v_count = ROW_COUNT;
        INSERT INTO _demo_cleanup_report VALUES (1, 'health_records', v_count, 'Ocorrências/avaliações clínicas demo removidas');

        -- 2.2 Registros de vacinação (`vaccination_records`)
        DELETE FROM public.vaccination_records
        WHERE id IN (
            'cccccccc-cccc-4ccc-8ccc-000000000001',
            'cccccccc-cccc-4ccc-8ccc-000000000002',
            'cccccccc-cccc-4ccc-8ccc-000000000003'
        )
        OR animal_id = ANY(v_demo_animal_ids)
        OR vaccine_id = ANY(v_demo_vaccine_ids)
        OR campaign_id = ANY(v_demo_campaign_ids);
        GET DIAGNOSTICS v_count = ROW_COUNT;
        INSERT INTO _demo_cleanup_report VALUES (2, 'vaccination_records', v_count, 'Aplicações vacinais demo removidas');

        -- 2.3 Agendamentos individuais (`vaccination_schedules`)
        DELETE FROM public.vaccination_schedules
        WHERE id IN (
            'bbbbbbbb-bbbb-4bbb-8bbb-000000000001',
            'bbbbbbbb-bbbb-4bbb-8bbb-000000000002',
            'bbbbbbbb-bbbb-4bbb-8bbb-000000000003',
            'bbbbbbbb-bbbb-4bbb-8bbb-000000000004',
            'bbbbbbbb-bbbb-4bbb-8bbb-000000000005',
            'bbbbbbbb-bbbb-4bbb-8bbb-000000000006',
            'bbbbbbbb-bbbb-4bbb-8bbb-000000000007',
            'bbbbbbbb-bbbb-4bbb-8bbb-000000000008'
        )
        OR animal_id = ANY(v_demo_animal_ids)
        OR campaign_id = ANY(v_demo_campaign_ids)
        OR protocol_id = ANY(v_demo_protocol_ids)
        OR protocol_rule_id = ANY(v_demo_rule_ids)
        OR vaccine_id = ANY(v_demo_vaccine_ids);
        GET DIAGNOSTICS v_count = ROW_COUNT;
        INSERT INTO _demo_cleanup_report VALUES (3, 'vaccination_schedules', v_count, 'Agendamentos sanitários demo removidos');

        -- 2.4 Campanhas de vacinação (`vaccination_campaigns`)
        DELETE FROM public.vaccination_campaigns
        WHERE id = ANY(v_demo_campaign_ids);
        GET DIAGNOSTICS v_count = ROW_COUNT;
        INSERT INTO _demo_cleanup_report VALUES (4, 'vaccination_campaigns', v_count, 'Campanhas [DEMO] removidas');

        -- 2.5 Vínculos animal x protocolo (`animal_protocols`)
        DELETE FROM public.animal_protocols
        WHERE animal_id = ANY(v_demo_animal_ids)
        OR protocol_id = ANY(v_demo_protocol_ids);
        GET DIAGNOSTICS v_count = ROW_COUNT;
        INSERT INTO _demo_cleanup_report VALUES (5, 'animal_protocols', v_count, 'Vínculos com protocolos [DEMO] removidos');

        -- 2.6 Regras de protocolos (`sanitary_protocol_rules`)
        DELETE FROM public.sanitary_protocol_rules
        WHERE id = ANY(v_demo_rule_ids);
        GET DIAGNOSTICS v_count = ROW_COUNT;
        INSERT INTO _demo_cleanup_report VALUES (6, 'sanitary_protocol_rules', v_count, 'Regras de protocolos [DEMO] removidas');

        -- 2.7 Protocolos sanitários (`sanitary_protocols`)
        DELETE FROM public.sanitary_protocols
        WHERE id = ANY(v_demo_protocol_ids);
        GET DIAGNOSTICS v_count = ROW_COUNT;
        INSERT INTO _demo_cleanup_report VALUES (7, 'sanitary_protocols', v_count, 'Protocolos [DEMO] removidos');

        -- 2.8 Catálogo de vacinas (`vaccines`)
        DELETE FROM public.vaccines
        WHERE id = ANY(v_demo_vaccine_ids);
        GET DIAGNOSTICS v_count = ROW_COUNT;
        INSERT INTO _demo_cleanup_report VALUES (8, 'vaccines', v_count, 'Vacinas fictícias [DEMO] removidas');
    END IF;

    -- 3. Libera etiquetas QR pré-impressas caso alguma tenha sido vinculada a animal demo
    IF to_regclass('public.tag_units') IS NOT NULL AND cardinality(v_demo_animal_ids) > 0 THEN
        UPDATE public.tag_units
        SET animal_id = NULL,
            status = 'available',
            assigned_at = NULL,
            activated_at = NULL
        WHERE animal_id = ANY(v_demo_animal_ids);
        GET DIAGNOSTICS v_count = ROW_COUNT;
        INSERT INTO _demo_cleanup_report VALUES (9, 'tag_units', v_count, 'Etiquetas desvinculadas de animais demo e devolvidas para disponível');
    END IF;

    -- 4. Bovinos demonstrativos (`animals`)
    DELETE FROM public.animals
    WHERE id = ANY(v_demo_animal_ids);
    GET DIAGNOSTICS v_count = ROW_COUNT;
    INSERT INTO _demo_cleanup_report VALUES (10, 'animals', v_count, 'Animais DEMO-* removidos');

    -- 5. Lotes do seed 002 (somente os que não possuem animais ou campanhas reais vinculados)
    IF to_regclass('public.lots') IS NOT NULL THEN
        DELETE FROM public.lots l
        WHERE l.id IN (
            '44444444-4444-4444-8444-000000000001',
            '44444444-4444-4444-8444-000000000002',
            '44444444-4444-4444-8444-000000000003',
            '44444444-4444-4444-8444-000000000004'
        )
        AND NOT EXISTS (SELECT 1 FROM public.animals a WHERE a.lot_id = l.id)
        AND NOT EXISTS (SELECT 1 FROM public.vaccination_campaigns c WHERE c.lot_id = l.id);
        GET DIAGNOSTICS v_count = ROW_COUNT;

        SELECT COUNT(*)
        INTO v_preserved_lots
        FROM public.lots l
        WHERE l.id IN (
            '44444444-4444-4444-8444-000000000001',
            '44444444-4444-4444-8444-000000000002',
            '44444444-4444-4444-8444-000000000003',
            '44444444-4444-4444-8444-000000000004'
        );

        INSERT INTO _demo_cleanup_report VALUES (
            11,
            'lots',
            v_count,
            CASE
                WHEN v_preserved_lots > 0 THEN format('Lotes demo sem uso removidos (%s preservado(s) por vínculo real)', v_preserved_lots)
                ELSE 'Lotes demonstrativos sem vínculo real removidos'
            END
        );
    END IF;

    -- 6. Propriedade extra do seed 002 ("Estância Santa Clara"), mantendo "Fazenda Sede BoviTrack"
    IF to_regclass('public.properties') IS NOT NULL THEN
        SELECT EXISTS (SELECT 1 FROM public.properties WHERE id = v_santa_clara_id)
        INTO v_santa_clara_exists;

        IF v_santa_clara_exists THEN
            IF to_regclass('public.tag_batches') IS NOT NULL THEN
                EXECUTE 'SELECT COUNT(*) FROM public.tag_batches WHERE property_id = $1'
                INTO v_tag_batch_refs
                USING v_santa_clara_id;
            END IF;

            SELECT (
                EXISTS (SELECT 1 FROM public.animals WHERE property_id = v_santa_clara_id)
                OR EXISTS (SELECT 1 FROM public.lots WHERE property_id = v_santa_clara_id)
                OR EXISTS (SELECT 1 FROM public.sanitary_protocols WHERE property_id = v_santa_clara_id)
                OR EXISTS (SELECT 1 FROM public.animal_protocols WHERE property_id = v_santa_clara_id)
                OR EXISTS (SELECT 1 FROM public.vaccination_campaigns WHERE property_id = v_santa_clara_id)
                OR EXISTS (SELECT 1 FROM public.vaccination_schedules WHERE property_id = v_santa_clara_id)
                OR EXISTS (SELECT 1 FROM public.vaccination_records WHERE property_id = v_santa_clara_id)
                OR EXISTS (SELECT 1 FROM public.health_records WHERE property_id = v_santa_clara_id)
                OR EXISTS (SELECT 1 FROM public.organization_members WHERE property_id = v_santa_clara_id)
                OR v_tag_batch_refs > 0
            )
            INTO v_santa_clara_in_use;

            IF NOT v_santa_clara_in_use THEN
                DELETE FROM public.properties WHERE id = v_santa_clara_id;
                GET DIAGNOSTICS v_count = ROW_COUNT;
                INSERT INTO _demo_cleanup_report VALUES (
                    12, 'properties', v_count, 'Estância Santa Clara removida (Fazenda Sede BoviTrack mantida)'
                );
            ELSE
                INSERT INTO _demo_cleanup_report VALUES (
                    12, 'properties', 0, 'Estância Santa Clara preservada por possuir registros reais vinculados'
                );
            END IF;
        ELSE
            INSERT INTO _demo_cleanup_report VALUES (
                12, 'properties', 0, 'Estância Santa Clara já não existia (Fazenda Sede BoviTrack mantida)'
            );
        END IF;
    END IF;
END $$;

SELECT etapa, registros_afetados, observacao
FROM _demo_cleanup_report
ORDER BY ordem;

COMMIT;
