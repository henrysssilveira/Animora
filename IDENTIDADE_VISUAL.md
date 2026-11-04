# Manual de Identidade Visual e Design System — Animora

Este documento especifica integralmente a identidade visual, os fundamentos cromáticos, a tipografia, a geometria de superfícies, os estados interativos, a codificação semântica de dados e os padrões de mídia impressa da plataforma **Animora**.

---

## 1. Essência Visual e Diretrizes Estéticas

A identidade visual da **Animora** foi projetada para unir **precisão técnica contemporânea** e **alta legibilidade operacional no campo** (currais, cocheiras, baias, apriscos e escritórios rurais):

- **Clareza sob luz intensa:** contraste rigoroso entre superfícies claras frias (`Ghost White` e branco puro) e tipografia profunda (`Pitch Black`), garantindo leitura imediata em telas de celulares no campo e em placas impressas.
- **Assinatura cromática autoral:** substituição do clichê monocromático rural tradicional por uma tríade principal marcante (**Bubblegum Pink**, **Pitch Black** e **Ghost White**), equilibrada por dois tons funcionais orgânicos (**Fern** e **Mustard**).
- **Proporção de aplicação cromática (Regra 60–25–10–5):**
  - **~60% Superfícies Claras (`Ghost White` `#F7F7FF` + Branco `#FFFFFF`):** planos de fundo, cartões de conteúdo, áreas de respiro e tabelas.
  - **~25% Estrutura e Contraste (`Pitch Black` `#070600` + Neutros Acinzentados):** barra superior, rodapé, títulos, códigos de identificação, QR Codes e textos corridos.
  - **~10% Cor de Marca e Ação Primária (`Bubblegum Pink` `#EA526F`):** botões principais, estados ativos, destaques de foco, filetes estruturais e indicadores críticos.
  - **~5% Cores Funcionais de Apoio (`Fern` `#4A7856` e `Mustard` `#FCDC4D`):** confirmações sanitárias, níveis de permissão, janelas de atenção e categorização multi-espécie.

---

## 2. Paleta Cromática Oficial

### 2.1. Cores Principais (Tríade Identitária)

| Nome Oficial | HEX | RGB | HSL (aprox.) | Papel na Identidade Visual |
| :--- | :--- | :--- | :--- | :--- |
| **Bubblegum Pink** | `#EA526F` | `rgb(234, 82, 111)` | `hsl(349°, 78%, 62%)` | Cor primária de destaque, botões de ação principal (CTA), estados selecionados, anéis de foco, filetes de assinatura e alertas de atraso. |
| **Pitch Black** | `#070600` | `rgb(7, 6, 0)` | `hsl(51°, 100%, 1%)` | Cor estrutural escura, texto primário de máxima nitidez, cabeçalho, rodapé, badges de numeração de etiqueta e módulos de QR Code. |
| **Ghost White** | `#F7F7FF` | `rgb(247, 247, 255)` | `hsl(240°, 100%, 98%)` | Plano de fundo geral da aplicação (`canvas`), fundo de campos de formulário em repouso, caixas internas de metadados e texto claro sobre fundos escuros. |

### 2.2. Cores Secundárias e Funcionais de Apoio

| Nome Oficial | HEX | RGB | HSL (aprox.) | Papel na Identidade Visual |
| :--- | :--- | :--- | :--- | :--- |
| **Mustard** | `#FCDC4D` | `rgb(252, 220, 77)` | `hsl(49°, 97%, 65%)` | Sinalização de atenção preventiva, agendamento pendente na janela, identificação do nível de acesso `Admin`, ovinocultura e blocos de dieta/cocho. |
| **Fern** | `#4A7856` | `rgb(74, 120, 86)` | `hsl(136°, 24%, 38%)` | Confirmação positiva, registros sanitários concluídos, botões secundários sólidos, identificação do nível `Property`, bovinocultura e procedência verificada. |

---

## 3. Paleta Estendida, Tons Derivados e Design Tokens (`:root`)

Para suportar estados de interação (`:hover`, `:focus`, `:active`), fundos suaves de leitura e bordas sutis sem descaracterizar as 5 cores oficiais, o sistema utiliza os seguintes tokens derivados:

### 3.1. Variações de Estado, Fundos Suaves e Bordas

| Token CSS | Valor HEX / RGBA | Família | Uso Específico |
| :--- | :--- | :--- | :--- |
| `--animora-pink` | `#EA526F` | Bubblegum Pink | Cor base de ação primária e destaques `.text-brand`. |
| `--animora-pink-hover` | `#D43B59` | Bubblegum Pink | Estado `:hover` / `:focus` de botões primários e textos de alto contraste sobre rosa suave. |
| `--animora-pink-soft` | `#FDECEF` | Bubblegum Pink | Fundo suave de cartões selecionados, badges femininos, recém-nascidos e itens atrasados. |
| `--animora-pink-border` | `#F8C6D0` | Bubblegum Pink | Bordas sutis de elementos rosa, moldura tracejada de QR Code e hover de KPIs. |
| `--animora-black` | `#070600` | Pitch Black | Texto principal, barra de navegação, rodapé e contorno de placas físicas. |
| `--animora-black-soft` | `#181712` | Pitch Black | Superfícies escuras secundárias de transição. |
| `--animora-ghost` | `#F7F7FF` | Ghost White | Fundo global (`body`), inputs em repouso, `.detail-field` e `.timeline-card`. |
| `--animora-ghost-alt` | `#EFEFF9` | Ghost White | Cabeçalho de tabelas (`.table-agro thead`), divisórias internas e células inativas. |
| `--animora-white` | `#FFFFFF` | Neutro Puro | Superfície elevada de cartões (`.card-agro`, `.stat-card`, `.kpi-mini-card`), modais e área interna de QR Codes. |
| `--animora-border` | `#DFDFF0` | Neutro Frio | Borda estrutural padrão de cartões, tabelas, inputs e linha vertical de timeline. |
| `--animora-muted` | `#5A5A6E` | Neutro Frio | Textos secundários, subtítulos, rótulos em caixa-alta e links inativos de sub-navegação. |
| `--animora-mustard` | `#FCDC4D` | Mustard | Cor base de avisos, botões `.btn-mustard` e badge `Admin`. |
| *(Hover Mustard)* | `#F4CF2C` | Mustard | Estado `:hover` e `:focus` do botão `.btn-mustard`. |
| `--animora-mustard-soft` | `#FFF9DB` | Mustard | Fundo suave de alertas pendentes, faixa etária jovem e dia selecionado no calendário. |
| `--animora-mustard-ink` | `#524300` | Mustard | Tinta escura obrigatória para textos sobre `--animora-mustard-soft` (garantia de leitura WCAG AA/AAA). |
| `--animora-fern` | `#4A7856` | Fern | Cor base de sucesso/conclusão, botões `.btn-olive`, `.text-fern` e badge `Property`. |
| `--animora-fern-hover` | `#3B6145` | Fern | Estado `:hover` de botões `.btn-olive` e tinta de leitura sobre `--animora-fern-soft`. |
| `--animora-fern-soft` | `#EAF3EC` | Fern | Fundo suave de status aplicado/concluído e faixa etária lactente/filhote. |

### 3.2. Harmonização com Variáveis do Bootstrap 5.3

```css
:root {
    --bs-body-bg: #F7F7FF;
    --bs-body-color: #070600;
    --bs-primary: #EA526F;
    --bs-primary-rgb: 234, 82, 111;
    --bs-success: #4A7856;
    --bs-success-rgb: 74, 120, 86;
    --bs-success-bg-subtle: #EAF3EC;
    --bs-success-border-subtle: #C5DEC9;
    --bs-success-text-emphasis: #2D4D35;
    --bs-warning: #FCDC4D;
    --bs-warning-rgb: 252, 220, 77;
    --bs-warning-bg-subtle: #FFF9DB;
    --bs-warning-border-subtle: #F7E48B;
    --bs-warning-text-emphasis: #594800;
}
```

---

## 4. Gradientes, Atmosfera e Padrões de Superfície

A identidade evita gradientes excessivos, reservando-os para três pontos focais bem definidos:

1. **Banner Principal de Destaque (`.hero-banner`):**
   - Combina iluminação radial quente no canto superior direito com fundo escuro profundo:
     ```css
     background:
         radial-gradient(circle at top right, rgba(234, 82, 111, 0.38), transparent 48%),
         linear-gradient(135deg, #070600 0%, #1C161D 65%, #2D1620 100%);
     ```
   - Texto em `Ghost White` (`#F7F7FF`) e borda sutil `1px solid rgba(234, 82, 111, 0.30)`.

2. **Barra de Progresso de Campanhas e Metas (`.progress-agro .progress-bar`):**
   - Transição horizontal contínua entre a ação inicial (`Bubblegum Pink`) e a conclusão sanitária (`Fern`):
     ```css
     background: linear-gradient(90deg, #EA526F 0%, #4A7856 100%);
     ```
   - Aplicada sobre trilho `#EFEFF9` de `10px` de altura com extremidades totalmente arredondadas (`999px`).

3. **Palco Técnico de Pré-visualização de Impressão (`.label-sheet-preview-stage`):**
   - Textura geométrica diagonal suave que diferencia a área técnica da folha de papel branca:
     ```css
     background: repeating-linear-gradient(
         45deg,
         #EFEFF9,
         #EFEFF9 12px,
         #E7E7F5 12px,
         #E7E7F5 24px
     );
     ```

---

## 5. Tipografia e Hierarquia de Leitura

### 5.1. Famílias Tipográficas

- **Interface Web e Mobile:** `'Plus Jakarta Sans'` (sans-serif geométrica humanista de alta abertura nos caracteres e excelente distinção entre números como `0`, `6`, `8` e `9`).
  - Pilha de fallback: `system-ui, -apple-system, "Segoe UI", Roboto, sans-serif`.
- **Documentos Físicos e Etiquetas Vetoriais (PDF):** `'Helvetica'` e `'Helvetica-Bold'`, selecionadas pela fidelidade milimétrica em impressoras térmicas, laser e jato de tinta mesmo em corpos reduzidos (`5.5pt` a `8.5pt`).
- **Códigos Técnicos, Tokens UUID e URLs Públicas:** fonte monoespaçada padrão do sistema (`<code>`), exibida em `#070600` sobre pílulas `#F7F7FF` com borda `#DFDFF0`.

### 5.2. Pesos Tipográficos Carregados

| Peso | Nome | Aplicação na Plataforma |
| :--- | :--- | :--- |
| `400` | Regular | Textos descritivos longos, observações clínicas, parágrafos explicativos e placeholders. |
| `500` | Medium | Links da barra de navegação principal em estado padrão. |
| `600` | SemiBold | Botões de ação, rótulos de formulário (`.form-label`), valores de campos na ficha do animal, links de sub-navegação e pílulas de faixa etária. |
| `700` | Bold | Títulos de páginas e seções (`h1`–`h6`), cabeçalhos de tabela, rótulos caixa-alta (`.detail-field-label`), números de etiquetas (`.badge-ear-tag`) e badges de espécie/status. |
| `800` | ExtraBold | Indicadores numéricos de KPI (`.kpi-mini-value`), badge `Admin`, cabeçalhos de placas físicas de baia e numeração principal em etiquetas impressas. |

### 5.3. Escala Tipográfica e Espaçamento entre Letras

| Elemento | Tamanho | Peso | Transformação / Tracking | Cor Padrão |
| :--- | :--- | :--- | :--- | :--- |
| Título de Página (`h1.h3`) | `1.75rem` (~28px) | `700` | Normal | `#070600` |
| Número de KPI (`.kpi-mini-value`) | `1.75rem` (~28px) | `800` | `line-height: 1.1` | `#070600` |
| Título de Cartão / Modal (`h5`) | `1.25rem` (~20px) | `700` | Normal | `#070600` |
| Valor de Campo (`.detail-field-value`) | `1.05rem` (~16.8px) | `600` | Normal (`word-break: break-word`) | `#070600` |
| Rótulo de Input (`.form-label`) | `0.92rem` (~14.7px) | `600` | Normal | `#070600` |
| Sub-navegação (`.sanitary-subnav-link`) | `0.90rem` (~14.4px) | `600` | Normal | `#5A5A6E` (ativo: `#FFFFFF`) |
| Código de Etiqueta (`.badge-ear-tag`) | `0.88rem` (~14px) | `700` | `letter-spacing: 0.03em` | `#F7F7FF` sobre `#070600` |
| Cabeçalho de Tabela (`thead th`) | `0.82rem` (~13.1px) | `700` | `UPPERCASE`, `letter-spacing: 0.04em` | `#070600` |
| Badges de Status e Faixa Etária | `0.78rem` (~12.5px) | `600`–`700` | Normal | Semântica (ver Seção 9) |
| Rótulo de Metadado (`.detail-field-label`) | `0.76rem` (~12.1px) | `700` | `UPPERCASE`, `letter-spacing: 0.05em` | `#5A5A6E` |
| Badges de Nível de Acesso | `0.72rem` (~11.5px) | `700`–`800` | `UPPERCASE`, `letter-spacing: 0.04em` | Semântica (ver Seção 9) |
| Pílulas de Calendário (`.calendar-pill`) | `0.70rem` (~11.2px) | `600` | Reticências automáticas (`ellipsis`) | Semântica |

---

## 6. Geometria, Raios de Borda e Linhas Estruturais

A linguagem geométrica da Animora adota **cantos generosamente arredondados** nas superfícies externas e **raios progressivamente menores** nos elementos internos (aninhamento concêntrico harmônico):

### 6.1. Escala de Arredondamento (`border-radius`)

| Raio | Componentes Aplicados |
| :--- | :--- |
| `3px` | Cartões individuais de etiquetas na pré-visualização de folha de corte (`.label-preview-card`). |
| `6px` | Badges de sexo (`.badge-sex-male`, `.badge-sex-female`) e pílulas compactas de eventos no calendário (`.calendar-pill`). |
| `8px` | Identificador principal de etiqueta/brinco (`.badge-ear-tag`) e todos os 7 badges de status de agendamento sanitário. |
| `9px` – `10px` | Links da barra superior (`.nav-link`), botões (`.btn-agro`, `.btn-olive`, `.btn-mustard`, `.btn-outline-agro`), inputs (`.form-control`, `.form-select`) e abas da sub-navegação. |
| `12px` | Caixas de informação da ficha individual (`.detail-field`), células diárias do calendário (`.calendar-day-cell`), cartões da linha do tempo (`.timeline-card`) e caixas da placa de baia (`.stall-field-box`). |
| `14px` | Mini-cards de KPI (`.kpi-mini-card`), contêiner da sub-navegação (`.sanitary-subnav`) e cartões seletores de nível de acesso (`.access-level-card`). |
| `16px` | Cartões estruturais principais (`.card-agro`, `.stat-card`), molduras de QR Code (`.qr-frame`, `.stall-plaque-qr-box`), janelas modais e palco de impressão. |
| `20px` | Banner principal (`.hero-banner`) e folha externa da Placa de Baia / Ficha Cadastral (`.stall-plaque-sheet`). |
| `999px` (Pílula) | Badges de nível de acesso, espécies, faixas etárias, tipos de item preventivo, rotinas de manejo, abas em pílula (`nav-pills`) e barras de progresso. |

### 6.2. Espessuras e Estilos de Borda

- **Bordas sutis de contenção (`1px solid #DFDFF0`):** cartões brancos, caixas `.detail-field`, células de calendário e divisórias de tabela.
- **Bordas de controle interativo (`1.5px solid`):** campos de formulário (`#DFDFF0` em repouso; `#EA526F` em foco) e botões vazados `.btn-outline-agro` (`#EA526F`).
- **Bordas de seleção de estado (`2px solid`):** cartões de escolha de espécie/acesso, destaque do dia atual no calendário (`2px solid #EA526F`) e assinatura horizontal na barra superior (`border-bottom: 2px solid rgba(234, 82, 111, 0.45)`) e no rodapé (`border-top: 2px solid rgba(234, 82, 111, 0.35)`).
- **Bordas tracejadas (`dashed`):**
  - Moldura de leitura do QR Code na ficha web (`.qr-frame`): `2px dashed #F8C6D0`.
  - Badge de "Histórico Desconhecido" (`.badge-status-unknown`): `1px dashed #BFC0D6` (comunica incerteza documental sem parecer erro).
  - Guia de recorte de etiquetas: `1px dashed #C6C6DC` (web) / `#D2D2E4` (PDF).
- **Bordas físicas reforçadas para campo (`3px` e `5px`):** Placa de Baia com moldura externa `3px solid #070600` e faixa divisória de cabeçalho `5px solid #EA526F`.

---

## 7. Elevação, Sombras e Micro-interações

As sombras utilizam sempre a base `Pitch Black` (`rgb(7, 6, 0)`) em baixíssima opacidade para superfícies neutras, e `Bubblegum Pink` (`rgb(234, 82, 111)`) difuso para estados interativos em `:hover` ou `:focus`:

| Contexto | Valor de `box-shadow` | Transformação Associada |
| :--- | :--- | :--- |
| Cartão padrão em repouso (`.card-agro`) | `0 6px 22px rgba(7, 6, 0, 0.04)` | Nenhuma |
| Barra de navegação superior | `0 4px 18px rgba(7, 6, 0, 0.22)` | Nenhuma |
| Hero Banner (`.hero-banner`) | `0 12px 28px rgba(7, 6, 0, 0.16)` | Nenhuma |
| Simulação de folha A4/Térmica (`.label-sheet-paper`) | `0 12px 32px rgba(7, 6, 0, 0.14)` | Nenhuma |
| Botão primário em `:hover` (`.btn-agro:hover`) | `0 6px 16px rgba(234, 82, 111, 0.28)` | `translateY(-1px)` |
| Stat Card em `:hover` (`.stat-card:hover`) | `0 8px 22px rgba(234, 82, 111, 0.10)` | `translateY(-2px)` |
| KPI Mini-Card em `:hover` (`.kpi-mini-card:hover`) | `0 6px 16px rgba(234, 82, 111, 0.10)` | `translateY(-2px)` |
| Aba ativa na sub-navegação | `0 3px 10px rgba(234, 82, 111, 0.26)` | Nenhuma |
| Anel de foco de inputs (`.form-control:focus`) | `0 0 0 0.22rem rgba(234, 82, 111, 0.18)` | Fundo muda de `#F7F7FF` para `#FFFFFF` |

- **Curva e tempo de transição padrão:** `0.16s` a `0.20s ease`, mantendo resposta ágil sem atraso perceptível no uso repetitivo.

---

## 8. Anatomia dos Componentes de Interface

### 8.1. Barra de Navegação Superior e Rodapé
- **Cabeçalho (`.navbar-animora`):** fundo sólido `#070600`, espaçamento vertical `0.85rem` e linha inferior `2px solid rgba(234, 82, 111, 0.45)`.
  - Links inativos: `rgba(247, 247, 255, 0.82)`.
  - Links em `:hover`: `#F7F7FF` sobre fundo translúcido `rgba(247, 247, 255, 0.10)`.
  - Link da página ativa (`.active`): `#F7F7FF` sobre fundo `rgba(234, 82, 111, 0.22)` com borda interna `inset 0 0 0 1px rgba(234, 82, 111, 0.55)`.
- **Rodapé (`.footer-animora`):** fundo `#070600`, borda superior `2px solid rgba(234, 82, 111, 0.35)` e texto discreto em `rgba(247, 247, 255, 0.72)` (`0.88rem`).

### 8.2. Hierarquia de Botões
1. **Primário (`.btn-agro` / `.btn-animora`):** fundo `#EA526F`, texto `#FFFFFF`, peso `600`, raio `10px`, padding `0.6rem 1.25rem`. Reservado para a ação principal da tela (ex.: *Salvar*, *Confirmar*, *Atribuir Animal*, *Emitir Placa*).
2. **Secundário Sólido (`.btn-olive`):** fundo `#4A7856` (`Fern`), hover `#3B6145`, texto `#FFFFFF`, peso `600`. Usado para ações operacionais complementares, navegação de retorno qualificada e registros de manejo/clínica.
3. **Destaque Funcional (`.btn-mustard`):** fundo `#FCDC4D`, hover `#F4CF2C`, texto obrigatório em `#070600` (`Pitch Black`), peso `700`.
4. **Secundário Vazado (`.btn-outline-agro`):** fundo transparente, borda `1.5px solid #EA526F`, texto `#EA526F`; preenche com `#EA526F` e texto `#FFFFFF` no `:hover`.
5. **Neutro Auxiliar (`.btn-outline-secondary`):** usado para *Cancelar*, *Fechar* ou ações terciárias discretas.

### 8.3. Formulários e Cartões Seletores
- **Campos de texto e seleção (`.form-control`, `.form-select`):** iniciam com fundo levemente tonalizado (`#F7F7FF`) e borda `1.5px solid #DFDFF0` para se destacarem sobre cartões brancos (`#FFFFFF`). Ao receber foco, o fundo torna-se branco puro (`#FFFFFF`), a borda assume `#EA526F` e surge o halo `rgba(234, 82, 111, 0.18)`.
- **Cartões de Seleção de Espécie e Acesso (`.species-selector-card`, `.access-level-card`):** caixas clicáveis com borda de `2px`. Quando selecionadas, recebem borda `#EA526F`, fundo suave rosado (`#FDECEF` ou `rgba(234, 82, 111, 0.06)`) e sombra difusa rosa.

### 8.4. Tabelas Operacionais (`.table-agro`)
- **Cabeçalho (`thead th`):** superfície `#EFEFF9`, texto `#070600` em caixa-alta (`0.82rem`, peso `700`, `letter-spacing: 0.04em`), padding `0.9rem 1rem`.
- **Corpo (`tbody td`):** fundo branco, alinhamento vertical centralizado (`middle`), linhas separadas por filete suave `1px solid #EFEFF9`, padding `0.95rem 1rem`.
- **Hover de linha (`tbody tr:hover`):** `#FAFAFF`.

### 8.5. Calendário Mensal e Linha do Tempo Sanitária
- **Grade de Calendário (`.calendar-grid`):** 7 colunas iguais com `gap: 0.5rem` (`0.3rem` no mobile).
  - *Dia comum do mês:* fundo `#FFFFFF`, borda `1px solid #DFDFF0`, altura mínima `104px` (`70px` no mobile).
  - *Dia fora do mês (`.outside-month`):* fundo `#EFEFF9` com `opacity: 0.52`.
  - *Dia de hoje (`.is-today`):* borda `2px solid #EA526F` e fundo `#FFF9FA`.
  - *Dia inspecionado/selecionado (`.selected-day`):* contorno `outline: 2px solid #070600` e fundo `#FFF9DB` (`Mustard Soft`).
- **Linha do Tempo (`.sanitary-timeline`):** eixo vertical contínuo de `2px` em `#DFDFF0` à esquerda, com pontos nodais circulares de `22px` em `#EA526F`, borda branca interna de `2px` e anel externo `#F8C6D0`, acompanhados por cartões `.timeline-card` em `#F7F7FF`.

---

## 9. Sistema de Codificação Semântica (Badges e Pílulas)

Toda categorização visual na Animora segue pares estritos de fundo + texto + borda para manter significado consistente em todas as telas:

### 9.1. Níveis de Acesso (Exibidos sobre fundo escuro na barra superior)

| Nível | Classe CSS | Fundo | Texto | Borda |
| :--- | :--- | :--- | :--- | :--- |
| **Common** (Público) | `.badge-level-common` | `rgba(247, 247, 255, 0.14)` | `#F7F7FF` | `1px solid rgba(247, 247, 255, 0.28)` |
| **Property** (Equipe) | `.badge-level-property` | `#4A7856` (`Fern`) | `#F7F7FF` | Sem borda |
| **Admin** (Gestão QR) | `.badge-level-admin` | `#FCDC4D` (`Mustard`) | `#070600` (`Pitch Black`) | Sem borda (peso `800`) |

### 9.2. Identificação do Animal, Sexo e Espécie

| Categoria | Classe CSS | Fundo | Texto | Borda |
| :--- | :--- | :--- | :--- | :--- |
| **Código / Brinco / Placa** | `.badge-ear-tag` | `#070600` | `#F7F7FF` | `1px solid #070600` |
| **Sexo: Macho** | `.badge-sex-male` | `#EFEFF9` | `#070600` | `1px solid #DFDFF0` |
| **Sexo: Fêmea** | `.badge-sex-female` | `#FDECEF` | `#D43B59` | `1px solid #F8C6D0` |
| **Espécie: Bovino** | `.badge-species-bovino` | `rgba(74, 120, 86, 0.15)` | `#2D5237` | `1px solid rgba(74, 120, 86, 0.35)` |
| **Espécie: Equino** | `.badge-species-equino` | `rgba(234, 82, 111, 0.14)` | `#B82D48` | `1px solid rgba(234, 82, 111, 0.35)` |
| **Espécie: Ovino** | `.badge-species-ovino` | `rgba(252, 220, 77, 0.32)` | `#5C4B00` | `1px solid rgba(220, 185, 30, 0.55)` |

### 9.3. Faixas Etárias Neutras (Multi-Espécie)

| Faixa Etária | Janela | Classe CSS | Fundo | Texto | Borda |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Recém-nascido** | `0 a 30 dias` | `.badge-age-newborn` | `#FDECEF` | `#D43B59` | `1px solid #F8C6D0` |
| **Lactente / Filhote** | `31 a 180 dias` | `.badge-age-calf` | `#EAF3EC` | `#3B6145` | `1px solid #C5DEC9` |
| **Jovem** | `181 a 365 dias` | `.badge-age-young` | `#FFF9DB` | `#524300` | `1px solid #F3DC75` |
| **Adulto** | `> 365 dias` | `.badge-age-adult` | `#EFEFF9` | `#070600` | `1px solid #CFCFE6` |

### 9.4. Os 7 Estados de Agendamento Sanitário e Retornos

| Situação | Classe CSS | Fundo | Texto | Borda / Estilo Especial |
| :--- | :--- | :--- | :--- | :--- |
| **Pendente (na janela)** | `.badge-status-pending` | `#FFF9DB` | `#524300` | `1px solid #F3DC75` |
| **Próxima Aplicação (futura)** | `.badge-status-upcoming` | `#EFEFF9` | `#2B2B4F` | `1px solid #CFCFE8` |
| **Atrasada** | `.badge-status-overdue` | `#FDECEF` | `#B42340` | `1px solid #F8C6D0` |
| **Aplicada / Realizada** | `.badge-status-applied` | `#EAF3EC` | `#3B6145` | `1px solid #BFE0C6` |
| **Não Realizada** | `.badge-status-not-done` | `#F3EFEA` | `#5E503F` | `1px solid #DED5CA` |
| **Histórico Desconhecido** | `.badge-status-unknown` | `#EFEFF9` | `#5A5A6E` | `1px dashed #BFC0D6` |
| **Cancelada** | `.badge-status-cancelled` | `#F1F1F5` | `#6C757D` | `1px solid #DCDCE6` + texto tachado (`line-through`) |

### 9.5. Catálogo Preventivo e Rotinas Zootécnicas

| Tipo | Classe CSS | Fundo | Texto |
| :--- | :--- | :--- | :--- |
| **Vacina** | `.badge-item-vacina` | `rgba(74, 120, 86, 0.15)` | `#2D5237` |
| **Vermífugo / Antiparasitário** | `.badge-item-vermifugo` | `rgba(252, 220, 77, 0.35)` | `#5C4B00` |
| **Exame Sanitário / Preventivo** | `.badge-item-exame` | `rgba(234, 82, 111, 0.14)` | `#B82D48` |
| **Rotinas de Manejo** (Cascos, Ferrageamento, Tosquia, Pesagem, Odontologia, Famacha) | `.badge-routine-*` | `rgba(7, 6, 0, 0.07)` | `#070600` |

---

## 10. Identidade para Mídia Impressa e Sinalização Física

Como a Animora conecta o mundo físico (baias, cochos, brincos e fichas plastificadas) ao digital via QR Code, as peças impressas seguem regras específicas de contraste e acabamento:

### 10.1. Padrão Óptico do QR Code
- **Módulos escuros:** sempre renderizados em `Pitch Black` (`#070600`).
- **Zona de silêncio e fundo:** sempre em branco puro (`#FFFFFF`), nunca sobre fundos coloridos ou acinzentados, assegurando leitura instantânea mesmo em câmeras simples, plásticos laminados ou baixa iluminação de galpão.
- **Correção de erro:** nível **Q** (até 25% de recuperação de dano/sujeira) em etiquetas vetoriais PDF.

### 10.2. Placa de Baia / Cocho & Ficha Cadastral (`.stall-plaque-sheet`)
- **Folha externa:** fundo `#FFFFFF`, largura máxima `820px`, raio `20px` e borda estrutural espessa `3px solid #070600`.
- **Cabeçalho institucional (`.stall-plaque-header`):** fundo sólido `#070600`, texto `#F7F7FF` e faixa inferior de assinatura em `5px solid #EA526F`.
- **Quadro do QR Code (`.stall-plaque-qr-box`):** `210px × 210px`, fundo `#FFFFFF`, borda sólida `2px solid #070600` e raio `16px`.
- **Blocos de dados (`.stall-field-box`):** fundo `#F7F7FF`, borda `1px solid #DCDCEB`, rótulos em `#575666` (`0.72rem`, caixa-alta) e valores em `#070600` (`1.05rem`, peso `800`).
- **Destaque de Plano de Cocho (na Ficha Interna):** fundo creme quente `#FFFDF2` com borda `#E8C735` derivada de `Mustard`, separando visualmente a prescrição alimentar dos dados cadastrais fixos.
- **Fidelidade de cor na impressora:** aplicação explícita de `-webkit-print-color-adjust: exact` e `print-color-adjust: exact`.

### 10.3. Etiquetas de Lote em PDF Vetorial (`/etiquetas`)
- **Assinatura textual superior/lateral:** caixa-alta `ANIMORA` em `Helvetica-Bold` na cor `Bubblegum Pink` (`#EA526F`), acompanhada no layout horizontal por uma barra vertical sólida de `1.8pt` em `#EA526F`.
- **Numeração sequencial principal:** `Helvetica-Bold` em `Pitch Black` (`#070600`), sublinhada no modo horizontal por um filete de `0.7pt` em `#EA526F`.
- **Texto complementar da propriedade:** `Helvetica` regular na cor `Fern` (`#4A7856`).
- **Guia de corte opcional:** retângulo de cantos arredondados (`2.5mm`) tracejado (`dash 2, 2`) em `#D2D2E4` com espessura de `0.5pt`.

---

## 11. Regras de Contraste, Acessibilidade e Uso Correto

1. **Proibição de texto branco sobre `Mustard` (`#FCDC4D`):** devido à alta luminância do amarelo mostarda, todo texto sobre `#FCDC4D` ou `#FFF9DB` deve utilizar obrigatoriamente `Pitch Black` (`#070600`) ou `Mustard Ink` (`#524300` / `#594800`).
2. **Uso controlado do `Bubblegum Pink` (`#EA526F`):** reservar o preenchimento sólido `#EA526F` para ações primárias, marcadores focais e filetes de identidade; em áreas extensas de fundo (como alertas ou tabelas), utilizar sempre a variação suave `#FDECEF` combinada com texto escuro `#B42340` ou `#D43B59`.
3. **Diferenciação além da cor:** estados críticos ou especiais combinam cor + peso tipográfico + estilo de borda/texto (por exemplo, `Cancelada` usa texto tachado `line-through`; `Histórico Desconhecido` usa borda tracejada `dashed`; `Hoje` no calendário usa borda dupla de `2px`).
4. **Limpeza em modo de impressão (`@media print`):** barras de navegação, rodapés, alertas flutuantes, botões `.no-print` e modais são automaticamente suprimidos, convertendo o fundo da página para `#FFFFFF` puro para evitar desperdício de tinta e garantir nitidez documental.
