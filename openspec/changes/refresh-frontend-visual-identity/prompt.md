# Prompt — Refresh Visual Identity: credit-analysis-frontend

**Data:** 2026-06-13  
**Uso:** Copy-paste para nova sessão Claude Code que precise retomar esta tarefa

---

## Contexto para o agente

Você está trabalhando no monorepo `credit-analysis-frontend` localizado em `/home/daniloamaral/agentic/credit-analysis-frontend`. É um Turborepo com Next.js 16.2.0 + React 19.2.0.

A tarefa é um **refresh visual** para alinhar a identidade do frontend ao deck NodeBR 2026-06-17. O backend (`credit-analysis-agent`) é completamente separado — não modifique nada lá.

## Invariantes (nunca violar)

1. `packages/ag-ui-client/src/useAgentStream.ts` — não tocar. Interface SSE imutável.
2. `packages/types/` — não tocar. Tipos TypeScript imutáveis.
3. Lógica de chamadas HTTP (fetch para `/analysis`, `/queue`, `/resume`, `/status`) — não tocar.
4. `src/orchestrator.py` no projeto agent — não tocar (projeto separado).
5. Contratos SSE: `HITL_REQUIRED`, `AGENT_UPDATE`, `ANALYSIS_COMPLETE`, `ERROR` — não tocar.

## O que fazer

### T0 — Tokens (primeiro)
Criar `/home/daniloamaral/agentic/credit-analysis-frontend/packages/ui/tokens/tokens.css` com:
```css
@layer base {
  :root {
    --bg: #0A0E1A; --surf: #111827; --surf2: #1F2937;
    --acc: #7C3AED; --acc-glow: rgba(124,58,237,0.3);
    --ok: #10B981; --ok-glow: rgba(16,185,129,0.25);
    --alert: #EF4444; --alert-glow: rgba(239,68,68,0.25);
    --warn: #F59E0B; --warn-glow: rgba(245,158,11,0.25);
    --blue: #3B82F6; --blue-glow: rgba(59,130,246,0.25);
    --text: #F9FAFB; --muted: #6B7280;
    --line: rgba(255,255,255,0.08); --line2: rgba(255,255,255,0.15);
    --font-sans: 'Inter', system-ui, sans-serif;
    --font-mono: 'JetBrains Mono', monospace;
    --radius: 12px; --radius-sm: 6px; --radius-pill: 9999px;
    --shadow: 0 4px 24px rgba(0,0,0,0.4);
    --shadow-acc: 0 0 20px var(--acc-glow);
  }
  [data-theme="light"] {
    --bg: #F9FAFB; --surf: #FFFFFF; --surf2: #F3F4F6;
    --text: #111827; --line: rgba(0,0,0,0.08); --line2: rgba(0,0,0,0.15);
  }
  @media (prefers-reduced-motion: reduce) {
    *, *::before, *::after {
      animation-duration: 0.01ms !important;
      animation-iteration-count: 1 !important;
      transition-duration: 0.01ms !important;
    }
  }
}
```

### T1-T2 — globals.css (ambos os apps)
Substituir conteúdo por `@import` do tokens.css + compat shim que mapeia nomes antigos para novos:
- `--color-primary` → `var(--acc)`, `--bg-card` → `var(--surf)`, `--text-primary` → `var(--text)`, etc.

### T3-T4 — layout.tsx (ambos os apps)
Trocar `localFont` (Geist) por:
```tsx
import { Inter, JetBrains_Mono } from 'next/font/google';
const inter = Inter({ subsets: ['latin'], display: 'swap', variable: '--font-inter' });
const mono = JetBrains_Mono({ subsets: ['latin'], display: 'swap', variable: '--font-mono' });
```

### T6-T15 — Primitivos (packages/ui/src/)
Criar 10 componentes: `Tag`, `Card` (refatorar), `BulletList`, `CodeBlock`, `Pulse`, `Hud`, `Stat`, `Flow`, `TerminalShell`, `EventStream`. Ver spec.md para interfaces detalhadas.

### T17-T22 — Re-skin das 6 rotas
Atualizar JSX visual das rotas para usar tokens canônicos e novos primitivos. Não alterar nenhuma lógica de negócio ou fetch.

### T23-T26 — Validação
- `tsc --noEmit` nos dois apps
- grep zero por `googleapis.com`
- confirmar `prefers-reduced-motion` no CSS gerado
- smoke test visual nos dois dev servers

## Referência de arquivos

```
credit-analysis-frontend/
  packages/
    ui/
      tokens/tokens.css        ← CRIAR (T0)
      src/
        tag.tsx                ← CRIAR (T6)
        card.tsx               ← REFATORAR (T7)
        bullet-list.tsx        ← CRIAR (T8)
        code-block.tsx         ← CRIAR (T9)
        pulse.tsx              ← CRIAR (T10)
        hud.tsx                ← CRIAR (T11)
        stat.tsx               ← CRIAR (T12)
        flow.tsx               ← CRIAR (T13)
        terminal-shell.tsx     ← CRIAR (T14)
        event-stream.tsx       ← CRIAR (T15)
    ag-ui-client/              ← NÃO TOCAR
    types/                     ← NÃO TOCAR
  apps/
    customer/app/
      globals.css              ← ATUALIZAR (T1)
      layout.tsx               ← ATUALIZAR (T3)
      page.tsx                 ← RE-SKIN (T17)
      status/[request_id]/page.tsx ← RE-SKIN (T18)
    operator/app/
      globals.css              ← ATUALIZAR (T2)
      layout.tsx               ← ATUALIZAR (T4)
      page.tsx                 ← RE-SKIN (T19)
      queue/page.tsx           ← RE-SKIN (T20)
      queue/[request_id]/page.tsx ← RE-SKIN (T21)
      dashboard/page.tsx       ← VERIFICAR (T22)
```

## Estado atual dos artefatos OpenSpec

Todos criados em:
`/home/daniloamaral/agentic/credit-analysis-agent/openspec/changes/refresh-frontend-visual-identity/`
- `proposal.md` ✓
- `design.md` ✓
- `spec.md` ✓
- `tasks.md` ✓
- `prompt.md` ✓ (este arquivo)
