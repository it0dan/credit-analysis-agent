# Tasks — Pré-aprovação no fluxo automático de crédito

## Backend Python

1. [ ] Atualizar system prompt em `orchestrator.py` para emitir `pre_approved` no fluxo automático feliz.
2. [ ] Atualizar guard rails em `orchestrator.py` que forçam `approved` para `pre_approved`.
3. [ ] Verificar `save_episodic_memory`/`load_episodic_memory` para mapear `pre_approved` corretamente.
4. [ ] Atualizar `mock_agents.py` cenário `auto_approve` para `decision: "pre_approved"`.
5. [ ] Atualizar system prompt em `decision_agent.py` para incluir `pre_approved`.

## Frontend

6. [ ] Adicionar `'pre_approved'` em `packages/types/src/status.ts`.
7. [ ] Atualizar `packages/ui/src/status-badge.tsx` com estilo/label para `pre_approved`.
8. [ ] Atualizar `packages/ui/src/reasoning-stream.tsx` com label `PRÉ-APROVADO`.
9. [ ] Atualizar `packages/ag-ui-client/src/useAgentStream.ts` para mapear `pre_approved`.
10. [ ] Atualizar `apps/customer/app/status/[request_id]/page.tsx` com mensagens e simulação de `pre_approved`.
11. [ ] Revisar `apps/operator/app/queue/[request_id]/page.tsx` e `apps/operator/app/page.tsx` para refletir novo status.
12. [ ] Atualizar `packages/ui/src/analysis-history.ts` para incluir `pre_approved`.

## Evals e documentação

13. [ ] Atualizar `evals/trajectory.yaml` caso `auto_approve`.
14. [ ] Atualizar `evals/orchestrator.yaml` asserts de aprovação automática.
15. [ ] Atualizar `README.md` e `AGENTS.md` do `credit-analysis-agent`.
16. [ ] Atualizar `AGENTS.md` do `credit-analysis-frontend`.

## Validação

17. [ ] Rodar `npx promptfoo eval --config evals/trajectory.yaml`.
18. [ ] Rodar `npx promptfoo eval --config evals/orchestrator.yaml`.
19. [ ] Rodar `npm run check-types` no frontend.
20. [ ] Subir serviços e validar fluxo end-to-end.
