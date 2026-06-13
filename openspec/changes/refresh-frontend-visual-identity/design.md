# Design — Refresh Visual Identity: credit-analysis-frontend

**Data:** 2026-06-13  
**Status:** Aprovado para spec

---

## Reconhecimento (Etapa 0)

### Estado atual confirmado

| Arquivo | Situação |
|---|---|
| `apps/customer/app/globals.css` | 9 variáveis de token, Montserrat Google Fonts, sem `prefers-reduced-motion` |
| `apps/operator/app/globals.css` | Cópia idêntica do customer globals.css |
| `packages/ui/tokens/` | **Não existe** |
| `packages/ui/src/` | 9 componentes: CockpitLayout, StatusBadge, TraceTimeline, AgentCard, HITLPanel, CostDisplay, card, button, code |
| `packages/ag-ui-client/src/useAgentStream.ts` | EventSource SSE — não tocar |
| `apps/*/app/layout.tsx` | `localFont` com GeistVF.woff + GeistMonoVF.woff — mas globals.css sobrescreve com Montserrat |

### Fontes locais existentes

Ambos os apps já têm `/app/fonts/GeistVF.woff` e `/app/fonts/GeistMonoVF.woff`. O `localFont` está configurado mas as variáveis `--font-geist-*` nunca são consumidas no corpo (globals.css declara `font-family: Montserrat`). Podemos reutilizar o padrão `localFont` para Inter e JetBrains Mono.

---

## Decisões de Arquitetura

### DA-1: Tokens em pacote compartilhado (não em cada app)

**Decisão:** Criar `packages/ui/tokens/tokens.css` como fonte canônica. Os dois apps importam este arquivo via `globals.css` simplificado.

**Alternativa rejeitada:** Manter tokens em cada `globals.css` e sincronizar manualmente — gerou duplicação e drift no estado atual.

**Consequência:** Qualquer mudança de cor/espaçamento feita em `tokens.css` propaga automaticamente para customer e operator.

### DA-2: Fontes auto-hospedadas via `next/font/google` com `display: swap`

**Decisão:** Usar `next/font/google` com `{ subsets: ['latin'], display: 'swap' }` para Inter e JetBrains Mono. O Next.js faz download automático e serve os arquivos localmente (zero dependência de rede em runtime).

**Alternativa rejeitada:** `@import url(fonts.googleapis.com)` — latência de rede, dependência externa, violação de CSP strict.

**Consequência:** Layout.tsx de cada app declara as fontes e injeta as variáveis CSS `--font-inter` e `--font-mono`.

### DA-3: Primitivos como componentes React puros (sem CSS Modules)

**Decisão:** Novos primitivos em `packages/ui/src/` usam `style={}` inline + variáveis CSS dos tokens. Sem CSS Modules separados — o sistema de tokens já provê a consistência.

**Razão:** Os componentes existentes (StatusBadge, AgentCard, etc.) todos usam inline styles. Mudar para CSS Modules introduziria dois padrões num mesmo pacote. Manter consistência.

**Exceção:** `tokens.css` usa `@layer base` para evitar conflito de especificidade com estilos inline.

### DA-4: `prefers-reduced-motion` via CSS media query global

**Decisão:** Adicionar bloco único em `tokens.css`:
```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}
```
Isso cobre todos os componentes sem modificar cada um individualmente.

### DA-5: Container queries opt-in por componente

**Decisão:** Novos primitivos que precisam de responsividade usam `container-type: inline-size` no wrapper e `@container` internamente. Não converter os componentes existentes (TraceTimeline, HITLPanel) — apenas novos primitivos.

**Razão:** Converter os existentes aumenta risco de regressão visual sem benefício direto para a demo.

### DA-6: Nomes de tokens alinhados ao deck NodeBR

O deck usa estas variáveis semânticas. O `tokens.css` as adota como nomes canônicos:

| Token | Valor dark | Semântica |
|---|---|---|
| `--bg` | `#0A0E1A` | Background principal |
| `--surf` | `#111827` | Superfície de card/panel |
| `--surf2` | `#1F2937` | Superfície elevada (hover) |
| `--acc` | `#7C3AED` | Acento principal (purple) |
| `--acc-glow` | `rgba(124,58,237,0.3)` | Glow do acento |
| `--alert` | `#EF4444` | Alerta / erro / rejeição |
| `--warn` | `#F59E0B` | Aviso / HITL pendente |
| `--ok` | `#10B981` | Sucesso / aprovado |
| `--blue` | `#3B82F6` | Informação / análise |
| `--text` | `#F9FAFB` | Texto primário |
| `--muted` | `#6B7280` | Texto secundário |
| `--line` | `rgba(255,255,255,0.08)` | Borda sutil |
| `--line2` | `rgba(255,255,255,0.15)` | Borda mais visível |
| `--font-sans` | Inter | Fonte padrão |
| `--font-mono` | JetBrains Mono | Código / IDs / trace |
| `--radius` | `12px` | Border-radius padrão |
| `--radius-sm` | `6px` | Border-radius pequeno |
| `--radius-pill` | `9999px` | Pills / badges |

**Compatibilidade retroativa:** `globals.css` de cada app mapeia os nomes antigos para os novos:
```css
/* Compat shim — será removido na v2 */
:root {
  --color-primary: var(--acc);
  --bg-card: var(--surf);
  --text-primary: var(--text);
  /* … */
}
```
Isso permite que os componentes existentes (StatusBadge, etc.) continuem funcionando sem serem reescritos imediatamente.

---

## Mapa de Primitivos

| Primitivo | Uso principal | Props-chave |
|---|---|---|
| `Tag` | Badges de status, labels | `variant` (ok/warn/alert/blue/muted), `size` |
| `Card` | Container glassmorphism | `elevated`, `interactive`, `as` |
| `BulletList` | Listas de features/itens | `items`, `variant` (check/dot/arrow) |
| `CodeBlock` | Snippets JSON/Python | `language`, `copyable` |
| `Pulse` | Indicador de status ao vivo | `color` (ok/warn/alert/blue) |
| `Hud` | Painel de telemetria (navbar) | `items: {label, value, status}[]` |
| `Stat` | Métrica numérica grande | `label`, `value`, `delta`, `color` |
| `Flow` | Diagrama de fluxo T1→T2→T3 | `steps: {label, status, parallel}[]` |
| `TerminalShell` | Janela de terminal estilizada | `lines`, `prompt` |
| `EventStream` | Stream de eventos SSE ao vivo | `events: {type, label, ts}[]` |

---

## Fluxo de Importação

```
packages/ui/tokens/tokens.css
        ↓ @import
apps/customer/app/globals.css   (adiciona compat shim + resets)
apps/operator/app/globals.css   (idêntico)
        ↓ importado por
apps/*/app/layout.tsx           (também declara next/font → injeta --font-inter, --font-mono)
```

---

## Impacto em SSE / AG-UI

Zero. O `useAgentStream.ts` não tem nenhuma dependência de CSS ou tokens. O refactor é puramente na camada de apresentação.

---

## Riscos

| Risco | Mitigação |
|---|---|
| Compat shim quebrar componente existente | Shim mapeia 1:1 — verificar no TypeScript check |
| JetBrains Mono não disponível no `next/font/google` | Verificar disponibilidade antes de implementar |
| Container queries não suportadas em browsers antigos | Usar `@supports (container-type: inline-size)` como guard |
| Contraste WCAG falhar com novos tokens | Verificar ratio de `--text` sobre `--bg` e `--surf` antes de confirmar valores |
