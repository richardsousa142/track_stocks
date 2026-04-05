# Prompt — Site Luria: Plataforma de Análise de Ativos B3

## Contexto do projeto

Construir um **web app React** chamado **Luria** para acompanhamento de ações e FIIs
da bolsa brasileira (B3). Os dados vêm de um banco PostgreSQL com a view
`track_stocks.vw_indicadores_historicos` que expõe X indicadores por ativo,
incluindo fundamentalistas (BP, DRE, DFC, CMB, HST) e quantitativos rolling
(MKT com janelas 21d, 63d, 126d, 252d).

O arquivo `exemplo_indicadores_wege3.csv` mostra a estrutura real dos dados:
- **Colunas**: `empresa, ticker, freq, ano, trimestre, mes, dt_referencia, bloco, camada, unidade, indicador_codigo, indicador_nome, valor`
- **Frequências**: `A` (anual), `T` (trimestral), `M` (mensal — só indicadores MKT)
- **Blocos**: `BP` (Balanço Patrimonial), `DRE`, `DFC`, `CMB` (Combinado), `HST` (Histórico), `MKT` (Quantitativos)
- **Unidades**: `RATIO`, `PERCENTUAL`, `MOEDA`, `INDICE`, `OUTRO`

---

## Stack técnica

- **Framework**: React 18 + Vite
- **Linguagem**: TypeScript
- **Charts**: Recharts
- **Estilo**: Tailwind CSS
- **Roteamento**: React Router v6
- **Estado global**: Zustand
- **Data fetching**: TanStack Query (React Query)
- **Backend**: API REST (FastAPI ou Express) conectando ao PostgreSQL
- **Banco**: PostgreSQL com schema `track_stocks`

---

## Estrutura de pastas

```
luria/
├── src/
│   ├── api/
│   │   ├── ativos.ts          # busca de ativos, indicadores, ranking
│   │   ├── fiis.ts            # busca de FIIs
│   │   └── client.ts          # axios instance base
│   ├── components/
│   │   ├── charts/
│   │   │   ├── MainChart.tsx       # gráfico central grande
│   │   │   ├── MiniChart.tsx       # mini gráfico com limiar
│   │   │   └── Sparkline.tsx       # linha minúscula para cards
│   │   ├── home/
│   │   │   ├── SearchBar.tsx
│   │   │   └── StockCard.tsx
│   │   ├── asset/
│   │   │   ├── AssetHeader.tsx
│   │   │   ├── KPIStrip.tsx
│   │   │   ├── AIAnalysis.tsx
│   │   │   └── IndicatorSelector.tsx
│   │   └── ui/
│   │       ├── Badge.tsx
│   │       ├── ScoreRing.tsx
│   │       └── TabBar.tsx
│   ├── pages/
│   │   ├── HomePage.tsx
│   │   └── AssetPage.tsx
│   ├── hooks/
│   │   ├── useIndicadores.ts   # busca e normaliza dados de indicadores
│   │   ├── useRanking.ts       # ranking dos melhores ativos
│   │   └── useAIAnalysis.ts    # análise textual gerada por LLM
│   ├── config/
│   │   └── indicators.ts       # catálogo: limiar, direção, bloco, formato
│   ├── types/
│   │   └── index.ts
│   └── App.tsx
```

---

## Página 1 — Home (`/`)

### Layout geral
Fundo escuro (#080d1a). wide deixando espaçamentos nas laterais.

### Header
- Esquerda: logo "Luria" com gradiente text (azul → verde)
- Direita: ícone circular de usuário + hamburger menu (3 linhas)

### Tabs de navegação
Dois botões centralizados: **Ações** | **FIIs**
- Tab ativa: borda azul + fundo azul translúcido + texto azul
- Tab inativa: borda sutil + texto cinza

### Barra de busca
- Ícone de lupa inline à esquerda
- Placeholder: "Buscar ativo... ex: WEGE3, VALE3"
- Ao digitar, exibe dropdown com sugestões de tickers + nome da empresa
- Ao clicar numa sugestão, navega para `/ativo/:ticker`
- A busca deve funcionar por ticker e por razão social

### Seção "Melhores Ativos"
- Título: "Melhores Ações" ou "Melhores FIIs" dependendo da tab ativa
- Subtítulo: "Rankeados por score composto — fundamentalistas + quantitativos"
- Grid 2 colunas de cards

### StockCard
Cada card deve conter:
- **Ticker** (fonte grande, bold) + **Score** (número dentro de um círculo colorido)
  - Score ≥ 85: verde | Score 70-84: amarelo | Score < 70: vermelho
- **Razão social** (texto pequeno cinza)
- **Preço atual** + **Variação 1d** (badge verde ou vermelho)
- **Sparkline** (mini gráfico de linha, 80×32px, mostrando os últimos 30 pregões)
- **Tag de setor** (chip pequeno cinza)
- Hover: borda muda para azul com transição suave

### Lógica de ranking
O score é calculado no backend com base em:
- Média ponderada de indicadores-chave normalizados (0–100)
- Pesos: BP 25% | DRE 30% | DFC 20% | CMB 15% | MKT 10%
- Indicadores que ultrapassam o limiar somam pontos; abaixo subtraem

---

## Página 2 — Ativo (`/ativo/:ticker`)

### Header da página
- Botão "← Voltar" à esquerda
- Razão social + ticker (badge azul) + setor + câmbio atual

### KPI Strip
cards horizontais, exemplo:
- **Score Geral** (número grande, cor verde/amarelo/vermelho)
- **Retorno 12m** (percentual, verde se positivo)
- **Sharpe 252d** (número, azul)
- **Sortino 252d** (número, azul)

### Texto de análise (AI Analysis)
- Caixa com borda e fundo em gradiente azul-verde translúcido
- Ícone ✦ + label "Análise Luria"
- Texto gerado dinamicamente pela API de LLM baseado nos indicadores do ativo
- Deve mencionar os pontos mais fortes e fracos, comparando com os limiares
- Tom: analista financeiro profissional, objetivo, sem exageros

### Gráfico Principal (MainChart)
**Controles:**
- Dropdown para selecionar o indicador (todos os 219+ indicadores, agrupados por bloco como `<optgroup>`)
- Botões tipo/linha: `〜 Linha` | `▊ Barra`

**Gráfico de Linha (Recharts AreaChart):**
- `type="monotone"` para curva suavizada (sem picos angulosos)
- Gradiente vertical sob a linha (cor do estado → transparente)
- Zona de fundo colorida por threshold:
  - Para `higherBetter=true`: fundo vermelho translúcido abaixo do limiar, verde acima
  - Para `higherBetter=false`: fundo verde translúcido abaixo do limiar, vermelho acima
- Linha tracejada amarela no limiar com label "limiar"
- Eixo X: labels de período (T1/24 para trimestral, MM/AAAA para mensal, AAAA para anual)
- Eixo Y: valores formatados conforme unidade
- Tooltip customizado: data + valor formatado + limiar

**Gráfico de Barra (Recharts BarChart):**
- Bordas arredondadas no topo: `radius={[4,4,0,0]}`
- Cada barra colorida individualmente:
  - Verde se o valor está no lado bom em relação ao limiar
  - Vermelho se está no lado ruim
  - Sem limiar definido: azul padrão
- Linha tracejada amarela no limiar
- Tooltip idêntico ao de linha

**Abaixo do gráfico:**
- Indicador de status: ponto verde/vermelho + texto "Acima do limiar" / "Abaixo do limiar"
- Valor do limiar referenciado

### Seletor de Mini Gráficos
- Header: "Indicadores · N selecionados" + botão "＋ Selecionar" / "✕ Fechar"
- Painel (ao abrir):
  - Campo de busca filtro
  - Indicadores agrupados por bloco (BP, DRE, DFC, CMB, MKT)
  - Nome do bloco em cor (BP=azul, DRE=roxo, DFC=amarelo, CMB=verde, MKT=vermelho)
  - Chips clicáveis para toggle: selecionado = borda e texto na cor do bloco; não selecionado = cinza
- Seleção padrão inicial: 6 indicadores mais relevantes

### Grid de Mini Gráficos (colunas baseadas na largura da tela)
Cada MiniChart contém:

**Header do mini gráfico:**
- Label do bloco (cor do bloco, uppercase, pequeno)
- Nome do indicador
- Valor atual (grande, colorido: verde/vermelho baseado no limiar)
- Seta indicando direção boa (↑ maior=melhor | ↓ menor=melhor)

**Gráfico (Recharts AreaChart, 80px de altura):**
- `type="monotone"` — linha suavizada
- Gradiente vertical (cor do estado → transparente)
- `ReferenceArea` para zonas verde/vermelha do limiar (igual ao MainChart mas menor)
- `ReferenceLine` tracejada amarela no limiar
- Sem eixos visíveis (apenas a linha e as zonas de fundo)
- Tooltip minimalista: data + valor

**Footer do mini gráfico:**
- Linha tracejada amarela 12px + texto "limiar X.XX"

**Comportamento especial por unidade:**
- `PERCENTUAL`: os valores são decimais (0.15 = 15%), formatar com `(val*100).toFixed(1)%`
- `MOEDA`: formatar em R$ milhões ou bilhões
- `RATIO`: `val.toFixed(2)`
- `INDICE`: `val.toFixed(3)`

---

## Catálogo de indicadores (`src/config/indicators.ts`)

Definir interface e objeto com todos os indicadores conhecidos:

```typescript
interface IndicatorConfig {
  name: string;        // nome legível em português
  bloco: string;       // BP | DRE | DFC | CMB | HST | MKT
  unit: string;        // RATIO | PERCENTUAL | MOEDA | INDICE | OUTRO
  threshold?: number;  // limiar de referência (undefined = sem limiar)
  higherBetter: boolean; // true = maior é melhor; false = menor é melhor
  description?: string;
}
```

Incluir pelo menos os seguintes com limiares definidos:

| Código | Nome | Bloco | Limiar | Direção |
|--------|------|-------|--------|---------|
| bp_liquidez_corrente | Liquidez Corrente | BP | 1.5 | ↑ |
| bp_liquidez_seca | Liquidez Seca | BP | 1.0 | ↑ |
| bp_passivo_sobre_ativo | Passivo / Ativo | BP | 0.65 | ↓ |
| bp_pl_sobre_ativo | PL / Ativo | BP | 0.35 | ↑ |
| bp_equity_multiplier | Equity Multiplier | BP | 2.5 | ↓ |
| dre_margem_bruta | Margem Bruta | DRE | 0.25 | ↑ |
| dre_margem_ebit | Margem EBIT | DRE | 0.10 | ↑ |
| dre_margem_liquida | Margem Líquida | DRE | 0.08 | ↑ |
| dre_cobertura_juros | Cobertura de Juros | DRE | 3.0 | ↑ |
| dfc_accrual_ratio | Accrual Ratio | DFC | 0.05 | ↓ |
| cmb_roe | ROE | CMB | 0.15 | ↑ |
| cmb_roa | ROA | CMB | 0.08 | ↑ |
| cmb_roic | ROIC | CMB | 0.12 | ↑ |
| mkt_sharpe_252d | Sharpe 252d | MKT | 0.5 | ↑ |
| mkt_sortino_252d | Sortino 252d | MKT | 0.8 | ↑ |
| mkt_beta_252d | Beta 252d | MKT | 1.0 | ↓ |
| mkt_max_drawdown_252d | Max Drawdown 252d | MKT | 0.20 | ↓ |
| mkt_jensen_alpha_252d | Alpha Jensen 252d | MKT | 0.0 | ↑ |
| mkt_calmar_ratio_252d | Calmar Ratio 252d | MKT | 1.0 | ↑ |
| mkt_omega_ratio_252d | Omega Ratio 252d | MKT | 1.0 | ↑ |
| mkt_var_252d | VaR 252d | MKT | 0.025 | ↓ |
| mkt_information_ratio_252d | Information Ratio 252d | MKT | 0.3 | ↑ |
| mkt_volatility_252d | Volatilidade 252d | MKT | 0.30 | ↓ |

Para indicadores sem limiar definido (ex: valores de moeda absolutos), exibir apenas a evolução temporal sem coloração de zona.

---

## API Backend necessária

### Endpoints mínimos

```
GET /api/ativos?tipo=acoes|fiis&limit=20&offset=0
  → lista paginada com ticker, empresa, setor, score, preco, var1d, sparkline[]

GET /api/ativos/busca?q=WEGE3
  → busca por ticker ou razão social

GET /api/ativos/:ticker/indicadores?freq=T|A|M&indicador=bp_liquidez_corrente
  → série histórica de um indicador: [{dt_referencia, valor}]

GET /api/ativos/:ticker/todos-indicadores?freq=T
  → todos os indicadores mais recentes do ativo (para KPIs e análise AI)

GET /api/ativos/:ticker/analise
  → texto de análise gerado por LLM (cache de 24h)
```

### Query SQL base para indicadores

Database URL = "postgresql://postgres:postgres@localhost:5432/track_stocks"
para mais informações do banco de dados acesse a pasta /sql
```sql
SELECT
  dt_referencia,
  indicador_codigo,
  indicador_nome,
  bloco,
  unidade,
  valor,
  freq,
  ano,
  trimestre,
  mes
FROM track_stocks.vw_indicadores_historicos
WHERE ticker = $1
  AND indicador_codigo = $2
  AND freq = $3
ORDER BY dt_referencia ASC;
```

---

## Design system

### Cores (CSS variables ou Tailwind theme)
```css
--bg-primary: #080d1a;
--bg-surface: #0f1629;
--bg-card: #111e36;
--border: #1e2d4a;
--border-hover: #253a5e;
--text-primary: #f1f5f9;
--text-secondary: #94a3b8;
--text-muted: #374151;
--green: #10b981;
--red: #ef4444;
--yellow: #eab308;
--blue: #0ea5e9;
--bloco-bp: #3b82f6;
--bloco-dre: #a78bfa;
--bloco-dfc: #f59e0b;
--bloco-cmb: #10b981;
--bloco-mkt: #f43f5e;
--bloco-hst: #64748b;
```

### Tipografia
- Font family: `-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif`
- Valores numéricos grandes: `font-weight: 900`
- Labels de bloco: `font-weight: 800, letter-spacing: 0.5px, text-transform: uppercase`
- Body: `font-weight: 400, line-height: 1.7`

### Bordas e raios
- Cards: `border-radius: 12px, border: 1px solid var(--border)`
- Badges: `border-radius: 20px`
- Botões: `border-radius: 8px` ou `10px`

### Animações
- Hover em cards: `transition: border-color 200ms ease`
- Entrada da página: fade-in suave nos cards (staggered, 50ms de delay entre cada)
- Abertura do seletor: slide-down suave

---

## Regras de implementação

1. **Zero hardcoded**: todas as constantes de configuração (limiares, pesos, URLs) em arquivos de config separados
2. **Lazy loading**: mini gráficos carregam sob demanda (IntersectionObserver)
3. **Skeleton loading**: exibir skeleton cards enquanto dados carregam
4. **Erro gracioso**: se indicador não tiver dados suficientes, exibir mensagem "Dados insuficientes" no lugar do gráfico
5. **Acessibilidade**: todos os gráficos com `aria-label` descrevendo o indicador
6. **Performance**: memoizar os dados dos gráficos com `useMemo`; não recalcular a cada render
7. **Mobile first**: todas as telas funcionam em 375px de largura; grid de mini gráficos passa de 2 para 1 coluna em telas pequenas
8. **Dark mode**: o app é sempre dark — não implementar toggle de tema
9. **Sem mock data em produção**: todo dado vem da API; usar mock apenas em testes/Storybook

---

## Referências visuais

- Arquivo `luria_demo.html` — protótipo funcional com React + Recharts via CDN
- Imagem 1 (`wireframe_home.png`) — layout da home page
- Imagem 2 (`wireframe_asset.png`) — layout da página de ativo
- Arquivo `exemplo_indicadores_wege3.csv` — estrutura real dos dados do banco
