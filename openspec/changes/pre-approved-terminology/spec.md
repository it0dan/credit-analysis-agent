:# Spec — Pré-aprovação no fluxo automático de crédito

## Contrato de saída do orquestrador

```json
{
  "request_id": "uuid",
  "status": "pre_approved | approved | rejected | pending_human_review",
  "decision": "pre_approved | approved | rejected | adjusted | pending",
  "approved_amount": 20000,
  "justification": "string (50-300 caracteres)",
  "trace_id": "uuid",
  "_meta": { ... }
}
```

## Regras de emissão de status

1. **Automático bem-sucedido**: quando `bureau_get_score`, `documents_validate`, `risk_evaluate`, `compliance_check` e `decision_synthesize` retornam sucesso, e `requested_amount <= 50000`:
   - `status` = `"pre_approved"`
   - `decision` = `"pre_approved"`
   - `approved_amount` = `requested_amount`

2. **Rejeição por compliance**: quando `compliance_check` retorna `kyc_approved=false` ou `pld_clear=false`:
   - `status` = `"rejected"`
   - `decision` = `"rejected"`
   - `approved_amount` = `0`

3. **HITL por threshold**: quando `requested_amount > 50000` e todas as verificações automáticas passam:
   - `status` = `"pending_human_review"`
   - `decision` = `"pending"`
   - `approved_amount` = `null`

4. **HITL por erro técnico**: quando `bureau_get_score` ou `documents_validate` falham:
   - `status` = `"pending_human_review"`
   - `decision` = `"pending"`
   - `approved_amount` = `null`

5. **Aprovação humana**: quando operador aprova via `POST /resume`:
   - `status` = `"approved"`
   - `decision` = `"approved"`
   - `approved_amount` = `requested_amount`

## Contrato frontend

```ts
export type CreditAnalysisStatus =
  | 'pending'
  | 'analyzing'
  | 'hitl_required'
  | 'pre_approved'
  | 'approved'
  | 'rejected'
  | 'expired'
  | 'error';
```

## Mensagens de UI

- `pre_approved`: "Pré-aprovada · proposta em análise final"
- `approved`: "Aprovada · crédito liberado"
- `rejected`: "Não foi possível aprovar sua proposta no momento"
- `hitl_required`: "Proposta em análise especializada · retornamos em breve"

## Evals

- `evals/trajectory.yaml`: caso `auto_approve` deve validar `status === "pre_approved"`.
- `evals/orchestrator.yaml`: ajustar asserts de aprovação automática.
