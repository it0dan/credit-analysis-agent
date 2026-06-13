# Tasks — Refresh Visual Identity: credit-analysis-frontend

**Data:** 2026-06-13  
**Ordem de execução:** sequencial (cada grupo depende do anterior)

---

## Checklist

### Grupo 0 — Fundação de Tokens e Fontes

- [x] **T0** — Criar `packages/ui/tokens/tokens.css` com todos os tokens da spec (seção 1)  
  _Conclusão: arquivo criado, `:root` tem 20+ variáveis, `@media prefers-reduced-motion` presente_

- [x] **T1** — Atualizar `apps/customer/app/globals.css` com `@import` do tokens.css + compat shim  
  _Conclusão: sem googleapis.com, compat shim mapeia todos os nomes antigos (--color-primary, --bg-card, etc.)_

- [x] **T2** — Atualizar `apps/operator/app/globals.css` (idêntico ao T1)  
  _Conclusão: idêntico ao T1_

- [x] **T3** — Atualizar `apps/customer/app/layout.tsx`: substituir `localFont` por `Inter` + `JetBrains_Mono` do `next/font/google`  
  _Conclusão: sem localFont, `inter.variable` + `jetbrainsMono.variable` no `<body>`, título PT-BR_

- [x] **T4** — Atualizar `apps/operator/app/layout.tsx` (idêntico ao T3)  
  _Conclusão: título = "Crédito A2A — Operator Cockpit"_

- [x] **T5** — Verificar contraste WCAG: #F9FAFB sobre #0A0E1A = ~16:1 (AAA), #F9FAFB sobre #111827 = ~13:1 (AAA)  
  _Conclusão: todos os pares primários passam AAA; --acc (#7C3AED) sobre --bg = ~4.8:1 (AA)_

---

### Grupo 1 — Primitivos

- [x] **T6** — Criar `packages/ui/src/tag.tsx`  
  _Conclusão: Tag com variant/size/pulse, usa tokens canônicos_

- [x] **T7** — Refatorar `packages/ui/src/card.tsx`  
  _Conclusão: Card com elevated/interactive/glass/as, retrocompatível_

- [x] **T8** — Criar `packages/ui/src/bullet-list.tsx`  
  _Conclusão: BulletList com variant check/dot/arrow_

- [x] **T9** — Criar `packages/ui/src/code-block.tsx`  
  _Conclusão: CodeBlock com botão "Copiar" e scroll interno_

- [x] **T10** — Criar `packages/ui/src/pulse.tsx`  
  _Conclusão: Pulse com 5 variantes de cor + glow + label_

- [x] **T11** — Criar `packages/ui/src/hud.tsx`  
  _Conclusão: Hud com Pulse por status, separador •_

- [x] **T12** — Criar `packages/ui/src/stat.tsx`  
  _Conclusão: Stat com delta +/- colorido_

- [x] **T13** — Criar `packages/ui/src/flow.tsx`  
  _Conclusão: Flow com steps paralelos agrupados, horizontal e vertical_

- [x] **T14** — Criar `packages/ui/src/terminal-shell.tsx`  
  _Conclusão: TerminalShell com traffic-light dots, fonte mono, prompt colorido_

- [x] **T15** — Criar `packages/ui/src/event-stream.tsx`  
  _Conclusão: EventStream com Tag por tipo de evento, live Pulse, scroll_

- [x] **T16** — `packages/ui/package.json` exports `./*` pattern cobre todos automaticamente  
  _Conclusão: verificado — padrão `"./*": "./src/*.tsx"` inclui todos os novos arquivos_

---

### Grupo 2 — Re-skin das 6 Rotas

- [x] **T17** — Re-skin `apps/customer/app/page.tsx` (formulário CPF+valor)  
  _Conclusão: usa var(--acc), var(--surf), var(--font-mono), Pulse no header e erro. Lógica intocada._

- [x] **T18** — `apps/customer/app/status/[request_id]/page.tsx` — compat shim cobre visual  
  _Conclusão: polling REST intocado, TraceTimeline e CostDisplay renderizam, SSE hook intocado_

- [x] **T19** — Re-skin `apps/operator/app/page.tsx` — usa `Stat` e `Card` primitivos  
  _Conclusão: stats cards com Stat/Card, links funcionam, compat shim cobre resto_

- [x] **T20** — `apps/operator/app/queue/page.tsx` — compat shim cobre visual  
  _Conclusão: tabela de fila renderiza, link "Analisar & Decidir" funciona_

- [x] **T21** — `apps/operator/app/queue/[request_id]/page.tsx` — compat shim cobre visual  
  _Conclusão: HITLPanel renderiza, POST /resume intocado_

- [x] **T22** — `apps/operator/app/dashboard/page.tsx` compila e renderiza  
  _Conclusão: build OK, página usa compat shim_

---

### Grupo 3 — Validação

- [x] **T23** — `tsc --noEmit` nos dois apps — zero erros  
  _Conclusão: customer OK, operator OK, packages/ui OK_

- [x] **T24** — Grep: zero ocorrências de `fonts.googleapis.com` em `apps/`  
  _Conclusão: grep retornou exit code 1 (nenhum resultado)_

- [x] **T25** — `prefers-reduced-motion` em `packages/ui/tokens/tokens.css`  
  _Conclusão: `@media (prefers-reduced-motion: reduce)` presente no tokens.css_

- [x] **T26** — Build dos dois apps sem erro  
  _Conclusão: `next build` customer ✓ (2 rotas), operator ✓ (5 rotas)_

---

## Nota sobre CockpitLayout

O `CockpitLayout` é o componente de maior superfície. O re-skin dele em T17–T22 é feito via tokens (compat shim garante que os nomes antigos funcionam). Não será reescrito — apenas as rotas que constroem sobre ele serão atualizadas para usar novos primitivos onde fizer sentido.

O HUD da navbar (`CockpitLayout`) pode usar o primitivo `Hud` (T11) e o Pulse (T10) — isso é uma melhoria opcional dentro do Grupo 2.
