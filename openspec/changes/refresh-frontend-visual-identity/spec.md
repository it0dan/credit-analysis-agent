# Spec — Refresh Visual Identity: credit-analysis-frontend

**Data:** 2026-06-13  
**Status:** Aprovado para tasks

---

## 1. `packages/ui/tokens/tokens.css`

Arquivo novo. Fonte canônica de todos os tokens de design.

```css
/* packages/ui/tokens/tokens.css
   Fonte canônica — não editar tokens em outro lugar */

@layer base {
  :root {
    /* Superfícies */
    --bg:        #0A0E1A;
    --surf:      #111827;
    --surf2:     #1F2937;

    /* Acentos */
    --acc:       #7C3AED;
    --acc-glow:  rgba(124, 58, 237, 0.3);

    /* Semântica */
    --ok:        #10B981;
    --ok-glow:   rgba(16, 185, 129, 0.25);
    --alert:     #EF4444;
    --alert-glow:rgba(239, 68, 68, 0.25);
    --warn:      #F59E0B;
    --warn-glow: rgba(245, 158, 11, 0.25);
    --blue:      #3B82F6;
    --blue-glow: rgba(59, 130, 246, 0.25);

    /* Texto */
    --text:      #F9FAFB;
    --muted:     #6B7280;

    /* Bordas */
    --line:      rgba(255, 255, 255, 0.08);
    --line2:     rgba(255, 255, 255, 0.15);

    /* Fontes — injetadas pelo layout.tsx via next/font */
    --font-sans: 'Inter', system-ui, sans-serif;
    --font-mono: 'JetBrains Mono', 'Fira Code', monospace;

    /* Formas */
    --radius:     12px;
    --radius-sm:  6px;
    --radius-pill:9999px;

    /* Sombras */
    --shadow:     0 4px 24px rgba(0, 0, 0, 0.4);
    --shadow-acc: 0 0 20px var(--acc-glow);
  }

  /* Tema claro — sobrescreve apenas o necessário */
  [data-theme="light"] {
    --bg:    #F9FAFB;
    --surf:  #FFFFFF;
    --surf2: #F3F4F6;
    --text:  #111827;
    --muted: #6B7280;
    --line:  rgba(0, 0, 0, 0.08);
    --line2: rgba(0, 0, 0, 0.15);
  }

  /* Acessibilidade — desativa animações */
  @media (prefers-reduced-motion: reduce) {
    *, *::before, *::after {
      animation-duration: 0.01ms !important;
      animation-iteration-count: 1 !important;
      transition-duration: 0.01ms !important;
      scroll-behavior: auto !important;
    }
  }
}
```

**Constraint:** nenhum outro arquivo declara variáveis de token de cor, tipografia ou forma.

---

## 2. `apps/*/app/globals.css` (customer e operator)

Substituir conteúdo por:

```css
@import '../../../../packages/ui/tokens/tokens.css';
/* Ajuste de path relativo conforme estrutura real do monorepo */

/* Compat shim — mantém componentes existentes funcionando */
:root {
  --bg-app:              var(--bg);
  --bg-card:             var(--surf);
  --bg-card-hover:       var(--surf2);
  --bg-sidebar:          var(--surf);
  --bg-navbar:           var(--surf);
  --bg-footer:           var(--bg);
  --border-glass:        1px solid var(--line);
  --border-glass-hover:  1px solid var(--line2);
  --color-primary:       var(--acc);
  --color-primary-glow:  var(--acc-glow);
  --color-emerald:       var(--ok);
  --color-emerald-glow:  var(--ok-glow);
  --color-rose:          var(--alert);
  --color-rose-glow:     var(--alert-glow);
  --color-amber:         var(--warn);
  --color-amber-glow:    var(--warn-glow);
  --text-primary:        var(--text);
  --text-secondary:      color-mix(in srgb, var(--text) 70%, transparent);
  --text-muted:          var(--muted);
  --shadow-main:         var(--shadow);
  --font-primary:        var(--font-sans);
  --font-heading:        var(--font-sans);
}

/* Resets */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

html, body {
  max-width: 100vw;
  overflow-x: hidden;
  font-family: var(--font-sans);
  background: var(--bg);
  color: var(--text);
  min-height: 100vh;
  -webkit-font-smoothing: antialiased;
}

/* Scrollbar */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--line2); border-radius: 4px; }
::-webkit-scrollbar-thumb:hover { background: var(--acc); }

/* Keyframes — guards para reduced-motion aplicados via tokens.css */
@keyframes spin     { to { transform: rotate(360deg); } }
@keyframes fadeIn   { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
@keyframes pulse-glow {
  0%, 100% { box-shadow: 0 0 5px var(--pulse-color, var(--acc-glow)); }
  50%       { box-shadow: 0 0 18px var(--pulse-color, var(--acc-glow)); }
}

.animate-fade-in    { animation: fadeIn 0.5s cubic-bezier(0.16, 1, 0.3, 1) forwards; }
.glow-pulse-primary { --pulse-color: var(--acc-glow); animation: pulse-glow 2s infinite ease-in-out; }
.glow-pulse-emerald { --pulse-color: var(--ok-glow);  animation: pulse-glow 2s infinite ease-in-out; }
.glow-pulse-rose    { --pulse-color: var(--alert-glow); animation: pulse-glow 2s infinite ease-in-out; }
.glow-pulse-amber   { --pulse-color: var(--warn-glow); animation: pulse-glow 2s infinite ease-in-out; }
```

---

## 3. `apps/*/app/layout.tsx` (customer e operator)

Substituir imports de fonte por:

```tsx
import { Inter, JetBrains_Mono } from 'next/font/google';

const inter = Inter({
  subsets: ['latin'],
  display: 'swap',
  variable: '--font-inter',
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ['latin'],
  display: 'swap',
  variable: '--font-mono',
});

// No <body>:
<body className={`${inter.variable} ${jetbrainsMono.variable}`}>
```

Remover `localFont` do GeistVF.woff / GeistMonoVF.woff.

---

## 4. Primitivos — `packages/ui/src/`

### 4.1 `tag.tsx`

```tsx
interface TagProps {
  variant?: 'ok' | 'warn' | 'alert' | 'blue' | 'acc' | 'muted';
  size?: 'sm' | 'md';
  children: React.ReactNode;
  pulse?: boolean;
}
```

Renderiza `<span>` com `background: var(--{variant}-glow)`, `color: var(--{variant})`, `border: 1px solid var(--{variant})`, `border-radius: var(--radius-pill)`. Texto `font-family: var(--font-mono)` em size sm, `var(--font-sans)` em md. `pulse` ativa a classe `glow-pulse-{variant}`.

### 4.2 `card.tsx` (refatorado)

```tsx
interface CardProps {
  elevated?: boolean;   // surf2 em vez de surf
  interactive?: boolean; // hover com translateY(-2px)
  glass?: boolean;       // backdrop-filter blur
  as?: keyof JSX.IntrinsicElements;
  children: React.ReactNode;
  style?: React.CSSProperties;
}
```

Substitui o `card.tsx` existente. Usa `--surf` / `--surf2`, `--line`, `--shadow`. Container com `container-type: inline-size` quando `interactive`.

### 4.3 `bullet-list.tsx`

```tsx
interface BulletListProps {
  items: string[];
  variant?: 'check' | 'dot' | 'arrow';
  color?: string; // CSS color value, default var(--acc)
}
```

Lista `<ul>` sem `list-style`. Cada item `<li>` com ícone SVG inline (`✓` / `●` / `→`) na cor `color`.

### 4.4 `code-block.tsx`

```tsx
interface CodeBlockProps {
  code: string;
  language?: string;
  copyable?: boolean;
  maxHeight?: string;
}
```

`<pre><code>` com `font-family: var(--font-mono)`, `background: var(--bg)`, `border: 1px solid var(--line)`, `border-radius: var(--radius)`. Botão "Copiar" no canto superior direito quando `copyable`. Sem dependency de syntax highlighter (out of scope para demo).

### 4.5 `pulse.tsx`

```tsx
interface PulseProps {
  color?: 'ok' | 'warn' | 'alert' | 'blue' | 'acc';
  size?: number; // px, default 8
  label?: string;
}
```

Ponto `<span>` circular com `background: var(--{color})` + `box-shadow: 0 0 8px var(--{color})`. Animação `pulse-glow`. Label opcional ao lado.

### 4.6 `hud.tsx`

```tsx
interface HudItem {
  label: string;
  value: string;
  status?: 'ok' | 'warn' | 'alert' | 'muted';
}

interface HudProps {
  items: HudItem[];
}
```

Row horizontal de itens `label: value` separados por `•`. Cada item com `Pulse` na cor do status. Usado na navbar do CockpitLayout.

### 4.7 `stat.tsx`

```tsx
interface StatProps {
  label: string;
  value: string | number;
  unit?: string;
  delta?: string;       // ex: "+12%" — verde se positivo, vermelho se negativo
  color?: 'ok' | 'warn' | 'alert' | 'blue' | 'acc' | 'text';
}
```

Card compacto: label pequeno uppercase + value grande `font-family: var(--font-mono)` + delta opcional.

### 4.8 `flow.tsx`

```tsx
interface FlowStep {
  label: string;
  sublabel?: string;
  status: 'done' | 'active' | 'pending' | 'error';
  parallel?: boolean; // agrupa com o próximo step em paralelo
}

interface FlowProps {
  steps: FlowStep[];
  orientation?: 'horizontal' | 'vertical';
}
```

Diagrama de fluxo visual T1→T2→T3. Steps conectados por linha SVG. Steps paralelos exibidos em coluna dentro de um bloco. Cores de status via tokens.

### 4.9 `terminal-shell.tsx`

```tsx
interface TerminalShellProps {
  lines: string[];
  prompt?: string;   // default "$ "
  title?: string;    // barra de título
  height?: string;   // CSS height, default "auto"
}
```

Container com header (3 dots decorativos + título), `font-family: var(--font-mono)`, `background: var(--bg)`, `border: 1px solid var(--line)`. Linhas renderizadas com `<span style={{ color: 'var(--ok)' }}>{prompt}</span>{line}`.

### 4.10 `event-stream.tsx`

```tsx
interface StreamEvent {
  type: 'AGENT_UPDATE' | 'HITL_REQUIRED' | 'ANALYSIS_COMPLETE' | 'ERROR' | string;
  label: string;
  ts?: string; // ISO timestamp
  data?: unknown;
}

interface EventStreamProps {
  events: StreamEvent[];
  maxVisible?: number; // default 20, scroll interno
  live?: boolean;      // mostra Pulse verde "ao vivo" no header
}
```

Lista scrollável de eventos SSE com timestamp, tipo (Tag colorido por tipo) e label. `live` ativa `Pulse` no header. Fundo `var(--bg)`, fonte mono. Não faz fetch — apenas renderiza eventos passados via props.

---

## 5. Contratos imutáveis (invariantes)

| Arquivo | Contrato |
|---|---|
| `packages/ag-ui-client/src/useAgentStream.ts` | Interface `UseAgentStreamResult` inalterada |
| `packages/types/` | Todos os tipos (`CreditAnalysisStatus`, `AgentTrajectory`, `HITLRequest`, `OperatorDecision`) inalterados |
| `POST /resume` | Endpoint e payload inalterados |
| `GET /analysis/:id/status` | Endpoint e payload inalterados |
| `GET /queue` | Endpoint e payload inalterados |
| `src/orchestrator.py` | Intocado |

---

## 6. WCAG 2.2 — Verificações obrigatórias

| Par de cores | Ratio mínimo | Target |
|---|---|---|
| `--text` (#F9FAFB) sobre `--bg` (#0A0E1A) | 4.5:1 (AA) | ~17:1 (AAA) |
| `--text` sobre `--surf` (#111827) | 4.5:1 (AA) | ~15:1 (AAA) |
| `--acc` (#7C3AED) sobre `--bg` | 3:1 (AA large) | verificar |
| `--ok` (#10B981) sobre `--surf` | 3:1 (AA large) | verificar |
| `--warn` (#F59E0B) sobre `--bg` | 3:1 (AA large) | verificar |
| `--alert` (#EF4444) sobre `--bg` | 3:1 (AA large) | verificar |

Texto interativo (botões, links) deve ter ratio ≥ 4.5:1.

---

## 7. Critérios de aceitação por rota

| Rota | Critério |
|---|---|
| `customer /` | Formulário CPF+valor funciona, submit chama `/analysis`, redireciona para `/status/:id` |
| `customer /status/[id]` | Polling REST funciona, TraceTimeline renderiza, CostDisplay presente |
| `operator /` | Stats cards renderizam, links para `/queue` e `/dashboard` funcionam |
| `operator /queue` | Tabela de fila renderiza, link "Analisar & Decidir" funciona |
| `operator /queue/[id]` | HITLPanel renderiza, botões Aprovar/Reprovar/Escalar funcionam, POST /resume chamado |
| `operator /dashboard` | Página renderiza sem erro de runtime |
| **Todas** | TypeScript check passa (`tsc --noEmit`) |
| **Todas** | Sem `@import url(fonts.googleapis.com)` no HTML final |
| **Todas** | `prefers-reduced-motion: reduce` desativa animações |
