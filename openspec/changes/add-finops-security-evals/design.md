# Design — Evals FinOps + Security

**Data:** 2026-06-13  
**Status:** Definido com base no reconhecimento da Etapa 0

---

## Resultado da Etapa 0: o `_meta` já está completo

Após inspeção de `src/orchestrator.py` (linhas 566–573, 1454–1456), confirmou-se que o output do orquestrador **já expõe todos os campos necessários**. Nenhuma mudança contratual é necessária. **ADR-008 não será criado.**

### `_meta.finops` (já emitido)

```json
{
  "finops": {
    "llm_requests":       3,
    "input_tokens":       1200,
    "output_tokens":      400,
    "total_tokens":       1600,
    "estimated_cost_brl": 0.000048,
    "trace_id":           "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01",
    "span_id":            "00f067aa0ba902b7"
  }
}
```

**Campo correto:** `total_tokens` (não `tokens_used` — bug corrigido nos YAMLs).

### `_meta.auth` (já emitido)

```json
{
  "auth": {
    "agents_tokens_used": {
      "compliance-agent": "<jwt-string>",
      "bureau-agent":     "<jwt-string>"
    },
    "used_fallback_token": false
  }
}
```

**Observação importante:** `agents_tokens_used` armazena strings de token JWT, não claims `aud` diretamente. Não há biblioteca de decode de JWT disponível nos asserts JavaScript do PromptFoo. **Estratégia de assertion para `aud`:** verificar que agentes com audiences diferentes recebem tokens diferentes (strings distintas), e que `used_fallback_token: false` quando o mapa de audiences está configurado. Para o teste de fallback, verificar `used_fallback_token: true`.

### `_meta.trajectory` (já emitido)

```json
{
  "trajectory": [
    { "turn": 1, "tool": "bureau_get_score", "trace_id": "...", "result_ok": true },
    { "turn": 1, "tool": "documents_validate", "trace_id": "...", "result_ok": true },
    ...
  ]
}
```

Cada entrada de trajetória já contém `trace_id`, então o assert de propagação de `X-Trace-Id` é verificável via `_meta.trajectory`.

---

## Estratégia de Assertion

### FinOps

| Assert | Campo | Método |
|--------|-------|--------|
| Custo por cenário < threshold | `_meta.finops.estimated_cost_brl` | `javascript` com `thresholds.yaml` via env var |
| Custo > 0 (sempre registrado) | `_meta.finops.estimated_cost_brl` | `javascript` |
| Trace W3C | `_meta.finops.trace_id` | `javascript` regex `^00-[0-9a-f]{32}-[0-9a-f]{16}-[0-9a-f]{2}$` |
| Span não vazio | `_meta.finops.span_id` | `javascript` typeof + length |
| Tokens dentro do threshold | `_meta.finops.total_tokens` | `javascript` com env var |
| Custo em short-circuit | `_meta.finops.estimated_cost_brl` | `javascript` + assert de status |

### Security

| Assert | Campo | Método |
|--------|-------|--------|
| Agentes usam tokens distintos por audience | `_meta.auth.agents_tokens_used` | `javascript` comparação de strings |
| Sem fallback quando mapa presente | `_meta.auth.used_fallback_token` | `javascript` === false |
| Fallback gracioso sem mapa | `_meta.auth.used_fallback_token` | `javascript` === true + status não-error |
| trace_id propagado em todas as tool calls | `_meta.trajectory[*].trace_id` | `javascript` every() |
| CPF não aparece em claro no output | JSON.stringify(output) | `javascript` regex negativo |

---

## Variáveis por Cenário

Os evals usam o provider `python:../src/orchestrator_provider.py` (formato nativo PromptFoo). As variáveis de CPF mapeiam para cenários dentro do `orchestrator_provider.py`:

| Variável | CPF de entrada | Cenário mapeado |
|----------|----------------|-----------------|
| `auto_approve` | qualquer CPF padrão | `auto_approve` |
| `compliance_fail` | CPF com "111" ou "compliance_fail" | `compliance_fail` |
| `multi_error` | CPF com "multi_error" | `multi_error` |

Os YAMLs usarão `vars` inline em cada teste (CPF literal ou keyword), sem arquivo externo de vars.

---

## Thresholds de Custo

Vivem em `evals/thresholds.yaml` passados como env vars para os asserts. Incluem data de validade explícita porque os preços do Gemini mudam.

```yaml
# Válido até: 2026-09-01 — revisar se preço do Gemini mudar
thresholds:
  auto_approve:     0.05   # R$ — cenário mais longo (4 turnos)
  compliance_fail:  0.02   # R$ — short-circuit no T1
  multi_error:      0.03   # R$ — fallback após T1/T2 parcial
  default:          0.10   # R$ — fallback conservador
  total_tokens:     5000   # tokens por análise completa
```

---

## Trade-offs Documentados

1. **Thresholds frágeis:** preços do Gemini mudam → thresholds têm data de validade explícita em `thresholds.yaml`.
2. **Sem decode de JWT em asserts:** estratégia indireta (tokens distintos por audience) é suficiente para o objetivo da demo; decode real exigiria provider customizado.
3. **Provider `python:` vs `exec:`:** `finops.yaml` e `security.yaml` usam `python:` (PromptFoo nativo) porque chamam `call_api()` diretamente, evitando overhead de subprocess. Consistente com a forma como `orchestrator_provider.py` foi desenhado.
