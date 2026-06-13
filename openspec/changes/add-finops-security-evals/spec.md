# Spec — Evals FinOps + Security

**Data:** 2026-06-13  
**Status:** Aprovado

---

## Contratos Formais

### Schema `_meta.finops`

```typescript
interface FinOpsMeta {
  llm_requests:       number;   // contagem de chamadas LLM no ciclo
  input_tokens:       number;
  output_tokens:      number;
  total_tokens:       number;   // input + output (campo correto, NÃO tokens_used)
  estimated_cost_brl: number;   // custo estimado em reais (arredondado a 6 casas)
  trace_id:           string;   // W3C traceparent: "00-<32hex>-<16hex>-<2hex>"
  span_id:            string;   // 16 dígitos hex do span raiz OTel
}
```

### Schema `_meta.auth`

```typescript
interface AuthMeta {
  agents_tokens_used: Record<string, string>; // agent_name → token JWT string
  used_fallback_token: boolean;               // true quando AUDIENCE_MAP ausente/inválido
}
```

### Schema `_meta.trajectory[n]`

```typescript
interface TrajectoryEntry {
  turn:      number;
  tool:      string;
  trace_id:  string;   // UUID propagado do orchestrator
  result_ok: boolean;
}
```

---

## Tabela de Asserts — `evals/finops.yaml`

| # | Descrição | Cenário | Campo verificado | Condição |
|---|-----------|---------|-----------------|----------|
| F1 | custo auto_approve < threshold | auto_approve | `_meta.finops.estimated_cost_brl` | < 0.05 BRL |
| F2 | custo compliance_fail < threshold (short-circuit) | compliance_fail | `_meta.finops.estimated_cost_brl` | > 0 e < 0.02 BRL |
| F3 | custo multi_error < threshold (fallback) | multi_error | `_meta.finops.estimated_cost_brl` | > 0 e < 0.03 BRL |
| F4 | trace_id no formato W3C traceparent | auto_approve | `_meta.finops.trace_id` | regex `^00-[0-9a-f]{32}-[0-9a-f]{16}-[0-9a-f]{2}$` |
| F5 | span_id presente e não vazio | auto_approve | `_meta.finops.span_id` | typeof string && length > 0 |
| F6 | total_tokens dentro do threshold | auto_approve | `_meta.finops.total_tokens` | < 5000 |
| F7 | custo > 0 sempre registrado (fluxo feliz) | auto_approve | `_meta.finops.estimated_cost_brl` | > 0 |
| F8 | status correto por cenário | auto_approve + compliance_fail | `output.status` | "approved" / "rejected" |

---

## Tabela de Asserts — `evals/security.yaml`

| # | Descrição | Cenário | Campo verificado | Condição |
|---|-----------|---------|-----------------|----------|
| S1 | compliance-agent usa token diferente do bureau-agent | auto_approve | `_meta.auth.agents_tokens_used` | compliance ≠ bureau (strings distintas) |
| S2 | fallback gracioso sem AUDIENCE_MAP — status não é erro | auto_approve + env_override=no_audience_map | `output.status` | !== "error" |
| S3 | fallback gracioso sinaliza used_fallback_token | auto_approve + env_override=no_audience_map | `_meta.auth.used_fallback_token` | === true |
| S4 | sem fallback quando AUDIENCE_MAP configurado | auto_approve | `_meta.auth.used_fallback_token` | === false |
| S5 | trace_id propagado em todas as tool calls | auto_approve | `_meta.trajectory[*].trace_id` | every() → string.length > 0 |
| S6 | CPF não aparece em claro no output serializado | auto_approve | JSON.stringify(output) | regex `\d{3}\.\d{3}\.\d{3}-\d{2}` NÃO encontrado |

---

## Critérios de Aceite Mensuráveis

- [ ] Suite completa (`run_all_evals.sh`) roda em < 2 minutos (wall clock)
- [ ] 100% dos asserts verdes localmente antes do commit final
- [ ] Nenhum CPF em claro em `output` ou logs capturados pelos evals (S6 verde)
- [ ] `run_all_evals.sh` aborta no primeiro erro (`set -e` ou verificação explícita)
- [ ] `run_all_evals.sh` imprime tempo total no final
- [ ] Os dois novos configs estão incluídos no runner
- [ ] `evals/thresholds.yaml` tem data de validade explícita no cabeçalho

---

## Fora de Escopo (restrições explícitas)

- Decode de JWT para verificar claim `aud` diretamente (sem biblioteca de crypto em asserts JS)
- Modificações em `orchestrator.py` (loop permanece intocado)
- Testes com Gateway real (provider determinístico, mocks locais)
