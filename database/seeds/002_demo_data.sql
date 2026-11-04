-- ============================================================================
-- BoviTrack — Dados Demonstrativos para Teste do Módulo Sanitário (Seed 002)
-- ============================================================================
-- IMPORTANTE: Todos os nomes de vacinas, janelas e protocolos abaixo são
-- exemplos estritamente FICTÍCIOS ([DEMO]) apenas para validação técnica das
-- telas, filtros, calendário, cartelas e carteira sanitária do sistema.
-- Em uso real, todo protocolo deve ser preenchido e validado pelo Responsável
-- Técnico da propriedade.
-- ============================================================================

-- 1. Organização e Propriedades Demonstrativas
INSERT INTO public.organizations (id, name, slug)
VALUES ('11111111-1111-4111-8111-111111111111', 'Agropecuária BoviTrack', 'agropecuaria-bovitrack')
ON CONFLICT (slug) DO NOTHING;

INSERT INTO public.properties (id, organization_id, name, code, municipality, state, production_focus)
VALUES
    ('22222222-2222-4222-8222-222222222222', (SELECT id FROM public.organizations WHERE slug = 'agropecuaria-bovitrack' LIMIT 1), 'Fazenda Sede BoviTrack', 'FAZ-01', 'Uberaba', 'MG', 'corte'),
    ('22222222-2222-4222-8222-222222222223', (SELECT id FROM public.organizations WHERE slug = 'agropecuaria-bovitrack' LIMIT 1), 'Estância Santa Clara', 'FAZ-02', 'Patos de Minas', 'MG', 'leite')
ON CONFLICT (id) DO NOTHING;

-- 2. Lotes de Manejo
INSERT INTO public.lots (id, organization_id, property_id, name, description)
VALUES
    ('44444444-4444-4444-8444-000000000001', (SELECT id FROM public.organizations WHERE slug = 'agropecuaria-bovitrack' LIMIT 1), '22222222-2222-4222-8222-222222222222', 'Lote Maternidade & Bezerros', 'Animais nascidos na propriedade em acompanhamento inicial'),
    ('44444444-4444-4444-8444-000000000002', (SELECT id FROM public.organizations WHERE slug = 'agropecuaria-bovitrack' LIMIT 1), '22222222-2222-4222-8222-222222222222', 'Lote Recria Pasto Norte', 'Novilhos e animais jovens em recria'),
    ('44444444-4444-4444-8444-000000000003', (SELECT id FROM public.organizations WHERE slug = 'agropecuaria-bovitrack' LIMIT 1), '22222222-2222-4222-8222-222222222222', 'Lote Matrizes Adultas', 'Matrizes adultas da Fazenda Sede'),
    ('44444444-4444-4444-8444-000000000004', (SELECT id FROM public.organizations WHERE slug = 'agropecuaria-bovitrack' LIMIT 1), '22222222-2222-4222-8222-222222222223', 'Lote Lactação Principal', 'Rebanho leiteiro da Estância Santa Clara')
ON CONFLICT (id) DO NOTHING;

-- 3. Catálogo Demonstrativo de Vacinas (Fictícias para teste)
INSERT INTO public.vaccines (id, organization_id, commercial_name, manufacturer, description, administration_route, dosage_unit, notes, is_active)
VALUES
    ('55555555-5555-4555-8555-000000000001', (SELECT id FROM public.organizations WHERE slug = 'agropecuaria-bovitrack' LIMIT 1), 'NeonatProtect Inicial [DEMO]', 'VetSul Laboratórios (Fictício)', 'Item demonstrativo para teste de regra neonatal.', 'Subcutânea', 'mL', 'Conservar conforme orientação técnica da propriedade.', TRUE),
    ('55555555-5555-4555-8555-000000000002', (SELECT id FROM public.organizations WHERE slug = 'agropecuaria-bovitrack' LIMIT 1), 'ImunoBov Polivalente [DEMO]', 'LabVet Brasil (Fictício)', 'Item demonstrativo para teste de protocolo em bezerros e reforço.', 'Subcutânea', 'mL', 'Cadastro demonstrativo do catálogo.', TRUE),
    ('55555555-5555-4555-8555-000000000003', (SELECT id FROM public.organizations WHERE slug = 'agropecuaria-bovitrack' LIMIT 1), 'BoviShield Reprodutiva [DEMO]', 'AgroBio Saúde Animal (Fictício)', 'Item demonstrativo para campanhas de matrizes e animais jovens.', 'Intramuscular', 'mL', 'Cadastro demonstrativo do catálogo.', TRUE)
ON CONFLICT (id) DO NOTHING;

-- 4. Protocolos Sanitários Demonstrativos (Validados por RT fictício de teste)
INSERT INTO public.sanitary_protocols (
    id, organization_id, property_id, name, description,
    animal_category, purpose, validated_by, validated_at, is_validated, is_active
)
VALUES
    (
        '66666666-6666-4666-8666-000000000001',
        (SELECT id FROM public.organizations WHERE slug = 'agropecuaria-bovitrack' LIMIT 1),
        '22222222-2222-4222-8222-222222222222',
        'Protocolo Base Cria & Recria [DEMO]',
        'Protocolo fictício de demonstração configurado para testar geração automática por idade na Fazenda Sede.',
        'todas',
        'corte',
        'Dra. Helena Prado — CRMV-MG 00000 (Demo)',
        NOW(),
        TRUE,
        TRUE
    ),
    (
        '66666666-6666-4666-8666-000000000002',
        (SELECT id FROM public.organizations WHERE slug = 'agropecuaria-bovitrack' LIMIT 1),
        '22222222-2222-4222-8222-222222222223',
        'Protocolo Bezerras Leiteiras [DEMO]',
        'Protocolo fictício para propriedade de leite Estância Santa Clara.',
        'bezerro',
        'leite',
        'Dr. Marcos Andrade — CRMV-MG 00001 (Demo)',
        NOW(),
        TRUE,
        TRUE
    )
ON CONFLICT (id) DO NOTHING;

-- 5. Regras dos Protocolos Demonstrativos
INSERT INTO public.sanitary_protocol_rules (
    id, organization_id, protocol_id, vaccine_id,
    min_age_days, max_age_days, dose_number, booster_interval_days, notes, is_active
)
VALUES
    (
        '77777777-7777-4777-8777-000000000001',
        (SELECT id FROM public.organizations WHERE slug = 'agropecuaria-bovitrack' LIMIT 1),
        '66666666-6666-4666-8666-000000000001',
        '55555555-5555-4555-8555-000000000001',
        5, 25, 1, NULL,
        'Regra demonstrativa para recém-nascidos (5 a 25 dias).',
        TRUE
    ),
    (
        '77777777-7777-4777-8777-000000000002',
        (SELECT id FROM public.organizations WHERE slug = 'agropecuaria-bovitrack' LIMIT 1),
        '66666666-6666-4666-8666-000000000001',
        '55555555-5555-4555-8555-000000000002',
        90, 150, 1, 30,
        'Regra demonstrativa para bezerros (90 a 150 dias) com intervalo de 30 dias para próxima dose.',
        TRUE
    ),
    (
        '77777777-7777-4777-8777-000000000003',
        (SELECT id FROM public.organizations WHERE slug = 'agropecuaria-bovitrack' LIMIT 1),
        '66666666-6666-4666-8666-000000000001',
        '55555555-5555-4555-8555-000000000003',
        210, 300, 1, NULL,
        'Regra demonstrativa para animais jovens em recria (210 a 300 dias).',
        TRUE
    ),
    (
        '77777777-7777-4777-8777-000000000004',
        (SELECT id FROM public.organizations WHERE slug = 'agropecuaria-bovitrack' LIMIT 1),
        '66666666-6666-4666-8666-000000000002',
        '55555555-5555-4555-8555-000000000002',
        60, 120, 1, 30,
        'Regra demonstrativa exclusiva da Estância Santa Clara.',
        TRUE
    )
ON CONFLICT (id) DO NOTHING;

-- 6. Animais Demonstrativos cobrindo todas as faixas etárias e cenários de histórico
INSERT INTO public.animals (
    id, ear_tag, name, sex, breed, birth_date, initial_weight, notes,
    qr_code_token, organization_id, property_id, lot_id,
    status, origin_type, sanitary_onboarding_mode, inclusion_date, initial_sanitary_notes
)
VALUES
    -- Recém-nascido (12 dias) — dentro da janela 5..25d (Pendente)
    (
        '88888888-8888-4888-8888-000000000001',
        'DEMO-RN01', 'Alvorada', 'Fêmea', 'Nelore',
        (CURRENT_DATE - INTERVAL '12 days')::DATE, 34.50,
        'Bezerra nascida no piquete maternidade.',
        '99999999-9999-4999-8999-000000000001',
        (SELECT id FROM public.organizations WHERE slug = 'agropecuaria-bovitrack' LIMIT 1),
        '22222222-2222-4222-8222-222222222222',
        '44444444-4444-4444-8444-000000000001',
        'ativo', 'nascido_propriedade', 'acompanhamento_nascimento',
        (CURRENT_DATE - INTERVAL '12 days')::DATE, NULL
    ),
    -- Bezerro (110 dias) — janela 5..25d já aplicada; janela 90..150d atual (Pendente)
    (
        '88888888-8888-4888-8888-000000000002',
        'DEMO-BZ02', 'Trovão', 'Macho', 'Angus',
        (CURRENT_DATE - INTERVAL '110 days')::DATE, 39.00,
        'Acompanhamento sanitário desde o nascimento.',
        '99999999-9999-4999-8999-000000000002',
        (SELECT id FROM public.organizations WHERE slug = 'agropecuaria-bovitrack' LIMIT 1),
        '22222222-2222-4222-8222-222222222222',
        '44444444-4444-4444-8444-000000000001',
        'ativo', 'nascido_propriedade', 'acompanhamento_nascimento',
        (CURRENT_DATE - INTERVAL '110 days')::DATE, NULL
    ),
    -- Jovem (240 dias) — em recria, com uma dose anterior atrasada para demonstração de alerta
    (
        '88888888-8888-4888-8888-000000000003',
        'DEMO-JV03', 'Valente', 'Macho', 'Tabapuã',
        (CURRENT_DATE - INTERVAL '240 days')::DATE, 41.20,
        'Animal jovem em lote de recria.',
        '99999999-9999-4999-8999-000000000003',
        (SELECT id FROM public.organizations WHERE slug = 'agropecuaria-bovitrack' LIMIT 1),
        '22222222-2222-4222-8222-222222222222',
        '44444444-4444-4444-8444-000000000002',
        'ativo', 'nascido_propriedade', 'acompanhamento_nascimento',
        (CURRENT_DATE - INTERVAL '240 days')::DATE, NULL
    ),
    -- Adulto (920 dias) — pré-existente com HISTÓRICO DESCONHECIDO (NÃO classificado como atrasado!)
    (
        '88888888-8888-4888-8888-000000000004',
        'DEMO-AD04', 'Serena', 'Fêmea', 'Nelore',
        (CURRENT_DATE - INTERVAL '920 days')::DATE, 460.00,
        'Matriz já existente antes da implantação do BoviTrack.',
        '99999999-9999-4999-8999-000000000004',
        (SELECT id FROM public.organizations WHERE slug = 'agropecuaria-bovitrack' LIMIT 1),
        '22222222-2222-4222-8222-222222222222',
        '44444444-4444-4444-8444-000000000003',
        'ativo', 'pre_existente', 'historico_desconhecido',
        CURRENT_DATE,
        'Animal adulto pré-existente sem comprovantes anteriores; incluído na campanha atual do lote.'
    ),
    -- Adulto (1150 dias) — adquirido com histórico conhecido informado
    (
        '88888888-8888-4888-8888-000000000005',
        'DEMO-AD05', 'Marquesa', 'Fêmea', 'Brahman',
        (CURRENT_DATE - INTERVAL '1150 days')::DATE, 495.00,
        'Matriz adquirida com atestado sanitário de origem.',
        '99999999-9999-4999-8999-000000000005',
        (SELECT id FROM public.organizations WHERE slug = 'agropecuaria-bovitrack' LIMIT 1),
        '22222222-2222-4222-8222-222222222222',
        '44444444-4444-4444-8444-000000000003',
        'ativo', 'adquirido_externo', 'historico_conhecido',
        CURRENT_DATE,
        'Histórico vacinal de origem conferido na entrada.'
    )
ON CONFLICT (ear_tag) DO NOTHING;

-- 7. Campanha Demonstrativa (Cartela de Vacinação)
INSERT INTO public.vaccination_campaigns (
    id, organization_id, property_id, lot_id, vaccine_id,
    selection_mode, name, scheduled_date, description, notes, status
)
VALUES (
    'aaaaaaaa-aaaa-4aaa-8aaa-000000000001',
    (SELECT id FROM public.organizations WHERE slug = 'agropecuaria-bovitrack' LIMIT 1),
    '22222222-2222-4222-8222-222222222222',
    '44444444-4444-4444-8444-000000000003',
    '55555555-5555-4555-8555-000000000003',
    'lote',
    'Campanha Matrizes Fazenda Sede [DEMO]',
    (CURRENT_DATE + INTERVAL '3 days')::DATE,
    'Campanha demonstrativa vinculada ao Lote Matrizes Adultas.',
    'Separar o lote no curral principal pela manhã.',
    'em_andamento'
)
ON CONFLICT (id) DO NOTHING;

-- 8. Agendamentos e Aplicações Demonstrativas
INSERT INTO public.vaccination_schedules (
    id, organization_id, property_id, animal_id, vaccine_id,
    protocol_id, protocol_rule_id, campaign_id, origin_type,
    dose_number, scheduled_date, window_end_date, status, notes, completed_at
)
VALUES
    -- Alvorada (RN): Pendente hoje na janela neonatal + Próxima aplicação aos 90d
    (
        'bbbbbbbb-bbbb-4bbb-8bbb-000000000001',
        (SELECT id FROM public.organizations WHERE slug = 'agropecuaria-bovitrack' LIMIT 1),
        '22222222-2222-4222-8222-222222222222',
        (SELECT id FROM public.animals WHERE ear_tag = 'DEMO-RN01' LIMIT 1),
        '55555555-5555-4555-8555-000000000001',
        '66666666-6666-4666-8666-000000000001',
        '77777777-7777-4777-8777-000000000001',
        NULL, 'protocolo', 1,
        (CURRENT_DATE - INTERVAL '7 days')::DATE,
        (CURRENT_DATE + INTERVAL '13 days')::DATE,
        'pendente', 'Gerado automaticamente pelo protocolo para recém-nascido.', NULL
    ),
    (
        'bbbbbbbb-bbbb-4bbb-8bbb-000000000002',
        (SELECT id FROM public.organizations WHERE slug = 'agropecuaria-bovitrack' LIMIT 1),
        '22222222-2222-4222-8222-222222222222',
        (SELECT id FROM public.animals WHERE ear_tag = 'DEMO-RN01' LIMIT 1),
        '55555555-5555-4555-8555-000000000002',
        '66666666-6666-4666-8666-000000000001',
        '77777777-7777-4777-8777-000000000002',
        NULL, 'protocolo', 1,
        (CURRENT_DATE + INTERVAL '78 days')::DATE,
        (CURRENT_DATE + INTERVAL '138 days')::DATE,
        'proxima_aplicacao', 'Agendamento futuro automático.', NULL
    ),
    -- Trovão (Bezerro): Dose neonatal já aplicada + Dose bezerro pendente
    (
        'bbbbbbbb-bbbb-4bbb-8bbb-000000000003',
        (SELECT id FROM public.organizations WHERE slug = 'agropecuaria-bovitrack' LIMIT 1),
        '22222222-2222-4222-8222-222222222222',
        (SELECT id FROM public.animals WHERE ear_tag = 'DEMO-BZ02' LIMIT 1),
        '55555555-5555-4555-8555-000000000001',
        '66666666-6666-4666-8666-000000000001',
        '77777777-7777-4777-8777-000000000001',
        NULL, 'protocolo', 1,
        (CURRENT_DATE - INTERVAL '95 days')::DATE,
        (CURRENT_DATE - INTERVAL '85 days')::DATE,
        'aplicada', 'Confirmada dentro da janela.', (NOW() - INTERVAL '92 days')
    ),
    (
        'bbbbbbbb-bbbb-4bbb-8bbb-000000000004',
        (SELECT id FROM public.organizations WHERE slug = 'agropecuaria-bovitrack' LIMIT 1),
        '22222222-2222-4222-8222-222222222222',
        (SELECT id FROM public.animals WHERE ear_tag = 'DEMO-BZ02' LIMIT 1),
        '55555555-5555-4555-8555-000000000002',
        '66666666-6666-4666-8666-000000000001',
        '77777777-7777-4777-8777-000000000002',
        NULL, 'protocolo', 1,
        (CURRENT_DATE - INTERVAL '20 days')::DATE,
        (CURRENT_DATE + INTERVAL '40 days')::DATE,
        'pendente', '1ª dose dentro da janela etária de bezerro.', NULL
    ),
    -- Valente (Jovem): Dose de 90..150d vencida (Atrasada) + Dose jovem 210..300d Pendente
    (
        'bbbbbbbb-bbbb-4bbb-8bbb-000000000005',
        (SELECT id FROM public.organizations WHERE slug = 'agropecuaria-bovitrack' LIMIT 1),
        '22222222-2222-4222-8222-222222222222',
        (SELECT id FROM public.animals WHERE ear_tag = 'DEMO-JV03' LIMIT 1),
        '55555555-5555-4555-8555-000000000002',
        '66666666-6666-4666-8666-000000000001',
        '77777777-7777-4777-8777-000000000002',
        NULL, 'protocolo', 1,
        (CURRENT_DATE - INTERVAL '150 days')::DATE,
        (CURRENT_DATE - INTERVAL '90 days')::DATE,
        'atrasada', 'Janela encerrada sem confirmação de aplicação.', NULL
    ),
    -- Serena (Adulta - Histórico Desconhecido): Registro de histórico desconhecido + Agendamento na Campanha
    (
        'bbbbbbbb-bbbb-4bbb-8bbb-000000000006',
        (SELECT id FROM public.organizations WHERE slug = 'agropecuaria-bovitrack' LIMIT 1),
        '22222222-2222-4222-8222-222222222222',
        (SELECT id FROM public.animals WHERE ear_tag = 'DEMO-AD04' LIMIT 1),
        '55555555-5555-4555-8555-000000000002',
        '66666666-6666-4666-8666-000000000001',
        '77777777-7777-4777-8777-000000000002',
        NULL, 'protocolo', 1,
        CURRENT_DATE, CURRENT_DATE,
        'historico_desconhecido', 'Animal adulto pré-existente sem histórico de fases anteriores.', NULL
    ),
    (
        'bbbbbbbb-bbbb-4bbb-8bbb-000000000007',
        (SELECT id FROM public.organizations WHERE slug = 'agropecuaria-bovitrack' LIMIT 1),
        '22222222-2222-4222-8222-222222222222',
        (SELECT id FROM public.animals WHERE ear_tag = 'DEMO-AD04' LIMIT 1),
        '55555555-5555-4555-8555-000000000003',
        NULL, NULL,
        'aaaaaaaa-aaaa-4aaa-8aaa-000000000001',
        'campanha', 1,
        (CURRENT_DATE + INTERVAL '3 days')::DATE,
        (CURRENT_DATE + INTERVAL '3 days')::DATE,
        'proxima_aplicacao', 'Agendamento individual da Campanha Matrizes.', NULL
    ),
    -- Marquesa (Adulta): Agendamento da Campanha já confirmado!
    (
        'bbbbbbbb-bbbb-4bbb-8bbb-000000000008',
        (SELECT id FROM public.organizations WHERE slug = 'agropecuaria-bovitrack' LIMIT 1),
        '22222222-2222-4222-8222-222222222222',
        (SELECT id FROM public.animals WHERE ear_tag = 'DEMO-AD05' LIMIT 1),
        '55555555-5555-4555-8555-000000000003',
        NULL, NULL,
        'aaaaaaaa-aaaa-4aaa-8aaa-000000000001',
        'campanha', 1,
        (CURRENT_DATE + INTERVAL '3 days')::DATE,
        (CURRENT_DATE + INTERVAL '3 days')::DATE,
        'aplicada', 'Aplicação antecipada confirmada na triagem.', NOW()
    )
ON CONFLICT (id) DO NOTHING;

-- 9. Registros Efetivos de Vacinação (`vaccination_records`)
INSERT INTO public.vaccination_records (
    id, organization_id, property_id, animal_id, vaccine_id,
    schedule_id, campaign_id, dose_number, applied_at,
    dosage, dosage_unit, administration_route, manufacturer,
    product_batch, product_expiry, applied_by, next_dose_date,
    is_historical_record, notes
)
VALUES
    (
        'cccccccc-cccc-4ccc-8ccc-000000000001',
        (SELECT id FROM public.organizations WHERE slug = 'agropecuaria-bovitrack' LIMIT 1),
        '22222222-2222-4222-8222-222222222222',
        (SELECT id FROM public.animals WHERE ear_tag = 'DEMO-BZ02' LIMIT 1),
        '55555555-5555-4555-8555-000000000001',
        'bbbbbbbb-bbbb-4bbb-8bbb-000000000003',
        NULL, 1,
        (NOW() - INTERVAL '92 days'),
        2.00, 'mL', 'Subcutânea', 'VetSul Laboratórios (Fictício)',
        'LT-2026-08A', (CURRENT_DATE + INTERVAL '280 days')::DATE,
        'João Carlos (Capataz)', NULL,
        FALSE, 'Animal reagiu bem, sem edema local.'
    ),
    (
        'cccccccc-cccc-4ccc-8ccc-000000000002',
        (SELECT id FROM public.organizations WHERE slug = 'agropecuaria-bovitrack' LIMIT 1),
        '22222222-2222-4222-8222-222222222222',
        (SELECT id FROM public.animals WHERE ear_tag = 'DEMO-AD05' LIMIT 1),
        '55555555-5555-4555-8555-000000000003',
        'bbbbbbbb-bbbb-4bbb-8bbb-000000000008',
        'aaaaaaaa-aaaa-4aaa-8aaa-000000000001', 1,
        NOW(),
        5.00, 'mL', 'Intramuscular', 'AgroBio Saúde Animal (Fictício)',
        'LT-9941-B', (CURRENT_DATE + INTERVAL '365 days')::DATE,
        'Dra. Helena Prado (CRMV-MG 00000 Demo)', NULL,
        FALSE, 'Aplicação realizada durante avaliação de entrada no lote.'
    ),
    (
        'cccccccc-cccc-4ccc-8ccc-000000000003',
        (SELECT id FROM public.organizations WHERE slug = 'agropecuaria-bovitrack' LIMIT 1),
        '22222222-2222-4222-8222-222222222222',
        (SELECT id FROM public.animals WHERE ear_tag = 'DEMO-AD05' LIMIT 1),
        '55555555-5555-4555-8555-000000000002',
        NULL, NULL, 1,
        (NOW() - INTERVAL '180 days'),
        5.00, 'mL', 'Subcutânea', 'LabVet Brasil (Fictício)',
        'ORIGEM-EXT', NULL,
        'Histórico de Origem Informado', NULL,
        TRUE, 'Registro anterior constante na guia sanitária de aquisição.'
    )
ON CONFLICT (id) DO NOTHING;

-- 10. Ocorrências e Observações Veterinárias Privadas (`health_records`)
INSERT INTO public.health_records (
    id, organization_id, property_id, animal_id,
    record_type, title, description, occurred_at,
    veterinarian_or_responsible, medication_applied, dosage_info, is_private, notes
)
VALUES
    (
        'dddddddd-dddd-4ddd-8ddd-000000000001',
        (SELECT id FROM public.organizations WHERE slug = 'agropecuaria-bovitrack' LIMIT 1),
        '22222222-2222-4222-8222-222222222222',
        (SELECT id FROM public.animals WHERE ear_tag = 'DEMO-AD04' LIMIT 1),
        'avaliacao_inicial',
        'Avaliação Sanitária Inicial de Implantação',
        'Animal adulto pré-existente inspecionado na implantação do BoviTrack. Bom escore corporal (ECC 3.5), mucosas coradas, sem histórico vacinal documental anterior.',
        (NOW() - INTERVAL '2 days'),
        'Dra. Helena Prado — CRMV-MG 00000 (Demo)',
        NULL, NULL, TRUE,
        'Incluída na campanha atual do lote de matrizes.'
    ),
    (
        'dddddddd-dddd-4ddd-8ddd-000000000002',
        (SELECT id FROM public.organizations WHERE slug = 'agropecuaria-bovitrack' LIMIT 1),
        '22222222-2222-4222-8222-222222222222',
        (SELECT id FROM public.animals WHERE ear_tag = 'DEMO-RN01' LIMIT 1),
        'observacao_veterinaria',
        'Cura de umbigo e colostragem conferidas',
        'Ingestão adequada de colostro nas primeiras horas e cicatrização umbilical normal.',
        (NOW() - INTERVAL '11 days'),
        'João Carlos (Equipe Campo)',
        'Solução antisséptica tópica [DEMO]', 'Aplicação tópica diária por 3 dias', TRUE,
        NULL
    )
ON CONFLICT (id) DO NOTHING;
