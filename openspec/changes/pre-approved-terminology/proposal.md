# Proposal — Pré-aprovação no fluxo automático de crédito

## Problema

O sistema atual classifica o cenário `auto_approve` como `approved` e o frontend exibe:

> "Proposta aprovada · seu crédito está disponível"

Essa mensagem é enganosa. Uma decisão tomada em segundos por agentes autônomos não representa uma liberação real de crédito, que depende de validações documentais, assinatura e liberação operacional posteriores.

## Motivação

- Evitar promessas falsas ao cliente final.
- Alinhar a linguagem do sistema com o processo real de concessão de crédito.
- Preservar a arquitetura atual (turnos T1/T2/T3 + HITL assíncrono).

## Proposta de valor

Introduzir o status `pre_approved` para decisões automáticas bem-sucedidas, reservando `approved` para confirmações humanas (HITL) ou workflows futuros de liberação.

## Escopo

- Backend Python (`orchestrator.py`, `mock_agents.py`, `decision_agent.py`).
- Frontend (`packages/types`, `packages/ui`, `packages/ag-ui-client`, `apps/customer`, `apps/operator`).
- Evals (`trajectory.yaml`, `orchestrator.yaml`).
- Documentação (`README.md`, `AGENTS.md`).

## Fora de escopo

- Workflow completo de liberação/documentação/assinatura.
- Mudanças no `compliance-agent` (seu contrato não muda).
