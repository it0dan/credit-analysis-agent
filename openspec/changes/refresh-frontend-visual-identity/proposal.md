# Proposal — Refresh Visual Identity: credit-analysis-frontend

**Data:** 2026-06-13  
**Autor:** Danilo Amaral (danilo.amaral@sensedia.com)  
**Contexto:** Apresentação NodeBR 2026-06-17  
**Status:** Aprovado para design

---

## Problema

O `credit-analysis-frontend` (Turborepo + Next.js 16.2.0 + React 19.2.0) possui uma identidade visual funcional, mas desconectada da linguagem de design do deck NodeBR. Especificamente:

1. **Fonte externa:** Montserrat carregada via `@import url(fonts.googleapis.com)` — latência de rede, sem auto-hospedagem, viola CSP strict.
2. **Tokens duplicados:** `globals.css` copiada identicamente nos dois apps (`customer/` e `operator/`). Qualquer mudança de cor exige edição em dois arquivos.
3. **Sem `prefers-reduced-motion`:** Animações `pulseGlow`, `fadeIn`, `spin` disparam incondicionalmente — falha WCAG 2.2 critério 2.3.3 (AAA).
4. **Sem container queries:** Responsividade feita por `min-width` inline e `minmax()` no grid — não segue mobile-first com `@container`.
5. **Primitivos ausentes:** Não existem `Tag`, `BulletList`, `CodeBlock`, `Pulse`, `Hud`, `Stat`, `Flow`, `TerminalShell`, `EventStream` — os componentes que o deck usa extensamente.
6. **Identidade visual diferente do deck:** Deck usa `#0A0E1A` (bg), `#7C3AED` (acc), JetBrains Mono + Inter. App usa `hsl(240, 25%, 7%)` + `hsl(262, 80%, 60%)` + Montserrat.

## Proposta

Implantar um sistema de design tokens como fonte canônica em `packages/ui/tokens/tokens.css`. Migrar as duas apps para consumir esse arquivo. Criar os primitivos faltantes em `packages/ui/src/`. Re-skinnar as 6 rotas existentes sem alterar nenhum contrato funcional (SSE, AG-UI, HITL, orchestrator).

## Escopo

**Dentro do escopo:**
- `packages/ui/tokens/tokens.css` — tokens canônicos
- `packages/ui/src/` — 10 novos primitivos
- `apps/customer/app/globals.css` + `apps/operator/app/globals.css` — substituídos por import do tokens.css
- `apps/customer/app/layout.tsx` + `apps/operator/app/layout.tsx` — fontes via `next/font/google`
- Re-skin de 6 rotas (CSS + JSX visual; sem lógica de negócio)

**Fora do escopo (invariantes):**
- `src/orchestrator.py` — intocado
- `packages/ag-ui-client/src/useAgentStream.ts` — intocado
- `packages/types/` — intocado
- Contratos SSE: `HITL_REQUIRED`, `AGENT_UPDATE`, `ANALYSIS_COMPLETE`, `ERROR` — intocados
- Endpoint `POST /resume` — intocado
- Lógica de polling REST nas páginas — intocada

## Stakeholders

| Papel | Nome |
|---|---|
| Autor / implementador | Danilo Amaral |
| Audiência | NodeBR 2026-06-17 (~500 devs) |
| Sistema upstream | credit-analysis-agent (orchestrator) |

## Critérios de Aceitação (alto nível)

- [ ] Todos os tokens definidos em `packages/ui/tokens/tokens.css` e apenas lá
- [ ] Fontes JetBrains Mono + Inter auto-hospedadas (sem chamada ao Google Fonts)
- [ ] `prefers-reduced-motion` desativa todas as animações
- [ ] WCAG 2.2 AA em todas as rotas (AAA onde possível)
- [ ] Nenhuma regressão nas rotas existentes — compilação TypeScript limpa
- [ ] Suite de evals 100% verde após o refresh (`./run_all_evals.sh` no agent)
