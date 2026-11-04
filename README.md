# Animora — Identificação QR Code & Manejo Multi-Espécie (Bovinos, Equinos & Ovinos)

Plataforma web responsiva desenvolvida em **Python + Flask** integrada ao **Supabase (PostgreSQL)** para identificação individual de **Bovinos, Equinos e Ovinos** por QR Code (brincos, colares, placas de baia/cocho e fichas cadastrais), controle de acesso em 3 níveis (`Common`, `Property` e `Admin`), planos individuais de cocho/arraçoamento, rotinas zootécnicas dedicadas e gestão sanitária/preventiva por propriedade.

---

## Principais Funcionalidades

1. **Manejo Multi-Espécie Integrado (`Bovino`, `Equino` e `Ovino`):** propriedades mistas ou especializadas (Fazendas, Haras e Cabanhas), com registro de pelagem, condição reprodutiva, microchip/registro oficial e alojamento (`Baia / Cocheira`, `Pasto / Piquete`, `Galpão / Aprisco` ou `Confinamento`).
2. **Placa de Baia / Cocho & Ficha Cadastral QR (`/animal/<token>/placa`):** emissão pronta para plastificar e fixar na porta da baia/cocho (modo público seguro) ou ficha cadastral interna com dieta de cocho para a equipe.
3. **Classificação Etária Neutra & Dinâmica:** cálculo automático em dias unificado para todas as espécies (`Recém-nascido 0–30d`, `Lactente / Filhote 31–180d`, `Jovem 181–365d` e `Adulto >365d`), mantendo compatibilidade retroativa com registros legados.
4. **Plano Individual de Cocho & Arraçoamento (`feeding_plans`):** definição de volumoso, concentrado/ração, suplemento mineral, horários de trato e orientações de água/cocho por animal (restrito a `Property`/`Admin`), com alertas automáticos por espécie (ex.: toxicidade por cobre em ovinos e fracionamento anti-cólica em equinos).
5. **Rotinas de Manejo por Espécie (`/sanitario/manejo`):** histórico e alertas de retorno automático para **Casqueamento**, **Ferrageamento** (equinos), **Tosquia** com peso de velo/lã (ovinos), **Avaliação Famacha 1–5** (ovinos), **Odontologia** (equinos) e **Pesagem Corporal**.
6. **Catálogo Preventivo Expandido (`/sanitario/vacinas`):** suporte a **Vacinas**, **Vermífugos / Antiparasitários** e **Exames Sanitários Periódicos** (ex.: AIE, Mormo, OPG, Brucelose) filtrados por `target_species`, com campo de resultado/laudo (`exam_result`).
7. **Protocolos Preventivos & Campanhas por Espécie:** agendamento automático estritamente compatível com a espécie do animal, impedindo que regras bovinas gerem pendências para equinos ou ovinos na mesma propriedade.
8. **Calendário Mensal Integrado (`/sanitario/calendario`):** visualização mensal unificando vacinas, vermífugos, exames, campanhas e retornos programados de manejo (cascos, ferraduras, tosquia, pesagem) com filtro por espécie.
9. **Impressão em Lote de Etiquetas QR Code (`/etiquetas`):** geração sequencial exclusiva do `Admin` com tokens UUID seguros, configurador milimétrico, exportação de PDF vetorial 1:1 (`ReportLab`) e ciclo de vida em `tag_units`.

---

## Estrutura Modular do Projeto

```text
AgroControl/
├── app.py                                # Aplicação Flask, rotas base, placa de baia e privacidade QR
├── config.py                             # Configurações de ambiente, PINs e faixas etárias neutras
├── requirements.txt                      # Dependências Python
├── blueprints/
│   ├── labels_bp.py                      # Geração em lote, PDF e controle de etiquetas QR (Admin)
│   └── sanitary_bp.py                    # Sanidade, Catálogo Preventivo, Manejo e Plano de Cocho
├── services/
│   ├── auth_service.py                   # Controle de permissão em 3 níveis (Common, Property, Admin)
│   ├── classification_service.py         # Cálculo dinâmico de idade neutra e filtros por espécie
│   ├── demo_cleanup_service.py           # Limpeza segura dos dados demonstrativos (`flask clean-demo`)
│   ├── label_pdf_service.py              # Exportação de PDF vetorial em escala milimétrica (ReportLab)
│   ├── label_service.py                  # Sequências, geometria em mm, tag_batches e tag_units
│   ├── management_service.py             # Rotinas de manejo (`management_records`) e planos de cocho (`feeding_plans`)
│   ├── qrcode_service.py                 # Geração de QR Codes exclusivos
│   ├── sanitary_service.py               # Catálogo preventivo, protocolos, campanhas, calendário e prontuário
│   ├── schedule_engine.py                # Motor de agendamento compatível por espécie e anti-duplicação
│   ├── species_service.py                # Metadados zootécnicos (Bovinos, Equinos, Ovinos), alojamentos e rotinas
│   └── supabase_service.py               # Cliente Supabase, tradução de erros e CRUD multi-espécie
├── database/
│   ├── schema.sql                        # Script consolidado para novos projetos do zero
│   ├── migrations/
│   │   ├── 001_sanitary_module.sql       # Módulo Sanitário, propriedades e lotes + RLS
│   │   ├── 003_tag_batches_and_units.sql # Lotes e unidades de etiquetas QR + RLS
│   │   └── 004_multi_species_management.sql # Expansão Multi-Espécie, Alojamento, Manejo e Plano de Cocho + RLS
│   └── seeds/
│       ├── 002_demo_data.sql             # Dados demonstrativos fictícios ([DEMO])
│       └── 003_clean_demo_data.sql       # Limpeza segura dos dados demo preservando cadastros reais
└── templates/                            # Templates Jinja2 responsivos com identidade visual Animora
```

---

## Passo a Passo de Configuração eMigrações no Supabase

1. Acesse o painel do seu projeto em [supabase.com](https://supabase.com) e abra o **SQL Editor**.
2. **Para projetos existentes (atualização sem perda de dados):** execute os scripts de migração na ordem:
   - `database/migrations/001_sanitary_module.sql`
   - `database/migrations/003_tag_batches_and_units.sql`
   - `database/migrations/004_multi_species_management.sql` *(expansão para Bovinos, Equinos e Ovinos, baias/alojamentos, catálogo preventivo expandido, rotinas de manejo e planos de cocho)*
3. *(Para projetos novos do zero, basta executar `database/schema.sql`, que já consolida todas as estruturas acima).*

---

## Níveis de Acesso (Common, Property e Admin)

1. **Common (Público, sem login):** acesso à **Consulta Pública QR** (`/`, `/consulta` e `/animal/<token>`), exibindo identificação, espécie, raça, pelagem, sexo, idade/faixa etária, origem e **alojamento/baia**. Planos de cocho/dieta, histórico sanitário e rotinas de manejo permanecem protegidos e ocultos.
2. **Property (`ANIMORA_PROPERTY_PIN`):** herda o nível `Common` + acesso ao Dashboard Multi-Espécie, Plantel (`/animals`), **atribuição de animais** (`/animals/new`), emissão de **Placa de Baia / Ficha QR** (`/animal/<token>/placa`), **Plano de Cocho**, **Rotinas de Manejo** (`/sanitario/manejo`) e **Gestão Sanitária** completa (`/sanitario/*`).
3. **Admin (`ANIMORA_ADMIN_PIN`):** acesso integral à plataforma + permissão exclusiva para **criação de lotes de QR Codes** (`/etiquetas`, layout milimétrico, PDF vetorial e descarte de etiquetas).
