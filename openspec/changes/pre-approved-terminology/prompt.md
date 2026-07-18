# Prompt — Implementação de pré-aprovação

Você está no repositório `credit-analysis-agent`. Implemente a mudança descrita em `spec.md` e `design.md`.

## Invariantes

- Não altere o contrato do `compliance-agent`.
- Não introduza novas dependências.
- Mantenha retrocompatibilidade de tracing (`X-Trace-Id`, `traceparent`).
- Preserve a arquitetura de turnos T1/T2/T3 e HITL assíncrono.

## Backend

Em `orchestrator.py`:
- No system prompt, substitua a regra que emite `status="approved"`/`decision="approved"` no fluxo automático feliz por `status="pre_approved"`/`decision="pre_approved"`.
- Mantenha `approved` apenas para aprovação humana via `resume_analysis`.
- Atualize quaisquer guard rails que forcem `approved` no cenário `auto_approve`.
- Atualize justificativas padrão para mencionar "pré-aprovado".

Em `mock_agents.py`:
- No cenário `auto_approve`, altere `decision` para `"pre_approved"`.
- No cenário `hitl_required`, mantenha `decision: "approved"` (o orquestrador converte para `pending_human_review`).

Em `decision_agent.py`:
- Inclua `pre_approved` na matriz de decisão e no formato de saída.

## Frontend

Adicione `'pre_approved'` em todos os lugares onde `CreditAnalysisStatus` é pattern-matched:
- `packages/types/src/status.ts`
- `packages/ui/src/status-badge.tsx`
- `packages/ui/src/reasoning-stream.tsx`
- `packages/ag-ui-client/src/useAgentStream.ts`
- `apps/customer/app/status/[request_id]/page.tsx`
- `packages/ui/src/analysis-history.ts`

Mensagens de UI:
- `pre_approved`: "Pré-aprovada · proposta em análise final"
- `approved`: "Aprovada · crédito liberado"

## Evals

- `evals/trajectory.yaml`: caso `auto_approve` deve esperar `r.status === "pre_approved"`.
- `evals/orchestrator.yaml`: ajustar asserts que esperam `"approved"` no fluxo automático.

## Testes

- `npx promptfoo eval --config evals/trajectory.yaml`
- `npx promptfoo eval --config evals/orchestrator.yaml`
- `npm run check-types` no frontend
- Subir serviços e validar fluxo end-to-end
