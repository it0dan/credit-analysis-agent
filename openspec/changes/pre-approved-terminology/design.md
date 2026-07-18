# Design — Pré-aprovação no fluxo automático de crédito

## Decisões técnicas

### DT-001: Novo status `pre_approved`

O status final de uma análise automática bem-sucedida passa a ser `pre_approved`. Ele indica que todas as verificações automáticas (bureau, documentos, risco, compliance) foram bem-sucedidas, mas a proposta ainda depende de análise final/liberação.

### DT-002: `approved` reservado para confirmação humana

Após revisão humana no HITL, a decisão do operador gera `approved` (ou `rejected`/`pending`). Isso mantém o valor da intervenção humana como etapa de liberação.

### DT-003: `approved_amount` em `pre_approved`

O campo `approved_amount` em status `pre_approved` recebe o valor solicitado, indicando o limite pré-aprovado. Rejeições continuam com `approved_amount: 0`.

### DT-004: Comunicação A2A inalterada

O `compliance-agent` continua retornando `ok/rejected/timeout/error`. A mudança é estritamente no orquestrador e no frontend.

### DT-005: Tipagem frontend

Adicionar `'pre_approved'` ao union `CreditAnalysisStatus`. Mapear visualmente com cor `--blue` e label "Pré-aprovado".

## Matriz de decisão atualizada

| Cenário | Status | Decision | approved_amount |
|---|---|---|---|
| Automático bem-sucedido (≤ R$ 50k, tudo ok) | `pre_approved` | `pre_approved` | valor solicitado |
| Compliance reprova | `rejected` | `rejected` | 0 |
| Valor > R$ 50k (threshold) | `pending_human_review` | `pending` | null |
| Erro de bureau/docs | `pending_human_review` | `pending` | null |
| Operador aprova no HITL | `approved` | `approved` | valor solicitado |
| Operador rejeita no HITL | `rejected` | `rejected` | 0 |
| Operador escala no HITL | `pending_human_review` | `pending` | null |

## Impacto nos estados de memória

O `status_map` em `save_episodic_memory` já possui `CODE_P`. Será usado para `pre_approved`.
