# Prompt de Implementação — Evals FinOps + Security

> Este prompt é autossuficiente. Execute-o em uma nova sessão sem contexto prévio.

---

## Contexto

Projeto: `/home/daniloamaral/agentic/credit-analysis-agent`  
Sistema: `credit-analysis-agent` com orquestrador determinístico (provider PromptFoo em `src/orchestrator_provider.py`)

O `_meta` retornado pelo orquestrador já expõe:
- `_meta.finops.{estimated_cost_brl, trace_id (W3C traceparent), span_id, total_tokens, input_tokens, output_tokens, llm_requests}`
- `_meta.auth.{agents_tokens_used (dict agent→token_string), used_fallback_token (bool)}`
- `_meta.trajectory[{turn, tool, trace_id, result_ok}]`

Nenhuma alteração em `orchestrator.py` é necessária.

---

## T1 — Criar `evals/thresholds.yaml`

```yaml
# evals/thresholds.yaml
# Válido até: 2026-09-01 — revisar se preço do Gemini 2.5 Flash mudar
# Preço base: input R$0.000030/token, output R$0.000040/token (estimativa jun/2026)
thresholds:
  auto_approve:    0.05   # 4 turnos, todos agentes
  compliance_fail: 0.02   # short-circuit no T1
  multi_error:     0.03   # fallback T1/T2 parcial
  default:         0.10   # conservador para cenários não mapeados
  total_tokens:    5000   # máximo por análise completa
```

Passe como env vars nos YAMLs de eval via campo `env:` do PromptFoo.

---

## T2 — Reescrever `evals/finops.yaml`

O arquivo atual tem dois bugs críticos: usa `tokens_used` (campo não existe — o correto é `total_tokens`) e usa variáveis `{{auto_approve_cpf}}` não definidas. Reescreva completo:

```yaml
description: "FinOps — custo, tokens e rastreabilidade de inferência"

providers:
  - id: python:../src/orchestrator_provider.py

env:
  EVAL_COST_THRESHOLD_AUTO:       "0.05"
  EVAL_COST_THRESHOLD_COMPLIANCE: "0.02"
  EVAL_COST_THRESHOLD_MULTI:      "0.03"
  EVAL_TOKEN_THRESHOLD:           "5000"

tests:
  # F1 — custo auto_approve dentro do threshold
  - description: "[FINOPS-1] auto_approve: custo estimado dentro do threshold por cenário"
    vars:
      cpf: "123.456.789-00"
    assert:
      - type: javascript
        value: |
          const out = typeof output === 'string' ? JSON.parse(output) : output;
          const cost = out._meta?.finops?.estimated_cost_brl ?? -1;
          const threshold = parseFloat(process.env.EVAL_COST_THRESHOLD_AUTO ?? '0.05');
          if (cost <= 0) throw new Error(`estimated_cost_brl deve ser > 0, recebido: ${cost}`);
          if (cost >= threshold) throw new Error(`Custo R$${cost} excede threshold R$${threshold}`);
          return true;

  # F2 — custo compliance_fail (short-circuit) registrado e dentro do threshold
  - description: "[FINOPS-2] compliance_fail: custo registrado mesmo em short-circuit"
    vars:
      cpf: "111.000.000-99"
    assert:
      - type: javascript
        value: |
          const out = typeof output === 'string' ? JSON.parse(output) : output;
          const cost = out._meta?.finops?.estimated_cost_brl ?? -1;
          if (cost <= 0) throw new Error(`Custo deve ser > 0 mesmo em short-circuit, recebido: ${cost}`);
          return true;
      - type: javascript
        value: |
          const out = typeof output === 'string' ? JSON.parse(output) : output;
          const cost = out._meta?.finops?.estimated_cost_brl ?? 999;
          const threshold = parseFloat(process.env.EVAL_COST_THRESHOLD_COMPLIANCE ?? '0.02');
          if (cost >= threshold) throw new Error(`Custo R$${cost} excede threshold de short-circuit R$${threshold}`);
          return true;
      - type: javascript
        value: |
          const out = typeof output === 'string' ? JSON.parse(output) : output;
          const status = out.status;
          if (status !== 'rejected' && status !== 'compliance_fail') {
            throw new Error(`Status esperado rejected/compliance_fail, recebido: ${status}`);
          }
          return true;

  # F3 — custo multi_error (fallback) registrado e dentro do threshold
  - description: "[FINOPS-3] multi_error: finops registra custo parcial de T1/T2"
    vars:
      cpf: "multi_error_cpf_000"
    assert:
      - type: javascript
        value: |
          const out = typeof output === 'string' ? JSON.parse(output) : output;
          const cost = out._meta?.finops?.estimated_cost_brl ?? -1;
          if (cost < 0) throw new Error(`estimated_cost_brl ausente ou negativo: ${cost}`);
          return true;
      - type: javascript
        value: |
          const out = typeof output === 'string' ? JSON.parse(output) : output;
          const cost = out._meta?.finops?.estimated_cost_brl ?? 999;
          const threshold = parseFloat(process.env.EVAL_COST_THRESHOLD_MULTI ?? '0.03');
          if (cost >= threshold) throw new Error(`Custo R$${cost} excede threshold multi_error R$${threshold}`);
          return true;

  # F4 — trace_id no formato W3C traceparent
  - description: "[FINOPS-4] trace_id no formato W3C traceparent (OpenTelemetry)"
    vars:
      cpf: "123.456.789-00"
    assert:
      - type: javascript
        value: |
          const out = typeof output === 'string' ? JSON.parse(output) : output;
          const traceId = out._meta?.finops?.trace_id ?? '';
          const w3c = /^00-[0-9a-f]{32}-[0-9a-f]{16}-[0-9a-f]{2}$/;
          if (!w3c.test(traceId)) throw new Error(`trace_id não segue padrão W3C: "${traceId}"`);
          return true;

  # F5 — span_id presente e não vazio
  - description: "[FINOPS-5] span_id presente — OpenTelemetry instrumentado"
    vars:
      cpf: "123.456.789-00"
    assert:
      - type: javascript
        value: |
          const out = typeof output === 'string' ? JSON.parse(output) : output;
          const spanId = out._meta?.finops?.span_id ?? '';
          if (typeof spanId !== 'string' || spanId.length === 0) {
            throw new Error(`span_id ausente ou vazio: "${spanId}"`);
          }
          return true;

  # F6 — total_tokens dentro do threshold de eficiência
  - description: "[FINOPS-6] total_tokens dentro do threshold de eficiência de contexto"
    vars:
      cpf: "123.456.789-00"
    assert:
      - type: javascript
        value: |
          const out = typeof output === 'string' ? JSON.parse(output) : output;
          const tokens = out._meta?.finops?.total_tokens ?? 0;
          const threshold = parseInt(process.env.EVAL_TOKEN_THRESHOLD ?? '5000');
          if (tokens >= threshold) throw new Error(`total_tokens ${tokens} excede threshold ${threshold}`);
          return true;

  # F7 — custo sempre > 0 no fluxo feliz
  - description: "[FINOPS-7] custo > 0 no fluxo feliz — FinOps não zerado"
    vars:
      cpf: "123.456.789-00"
    assert:
      - type: javascript
        value: |
          const out = typeof output === 'string' ? JSON.parse(output) : output;
          const cost = out._meta?.finops?.estimated_cost_brl ?? 0;
          if (cost <= 0) throw new Error(`estimated_cost_brl deve ser > 0, recebido: ${cost}`);
          return true;

  # F8 — status correto por cenário
  - description: "[FINOPS-8] auto_approve: status approved no fluxo feliz"
    vars:
      cpf: "123.456.789-00"
    assert:
      - type: javascript
        value: |
          const out = typeof output === 'string' ? JSON.parse(output) : output;
          if (out.status !== 'approved') throw new Error(`Status esperado "approved", recebido: "${out.status}"`);
          return true;
```

---

## T3 — Reescrever `evals/security.yaml`

O arquivo atual está truncado e tem assertions de `aud` incorretas (não é possível decodar JWT em assert JS sem biblioteca). Use estratégia de tokens distintos por audience:

```yaml
description: "Segurança — identidade de agente, AuthZ e isolamento de credenciais"

providers:
  - id: python:../src/orchestrator_provider.py

tests:
  # S1 — tokens distintos por audience (proxy para aud correto)
  - description: "[SECURITY-1] agents com audiences distintas recebem tokens distintos"
    vars:
      cpf: "123.456.789-00"
    assert:
      - type: javascript
        value: |
          const out = typeof output === 'string' ? JSON.parse(output) : output;
          const tokens = out._meta?.auth?.agents_tokens_used ?? {};
          const agents = Object.keys(tokens);
          if (agents.length < 2) throw new Error(`Esperado ≥2 agentes com tokens, encontrado: ${agents.length}`);
          return true;
      - type: javascript
        value: |
          const out = typeof output === 'string' ? JSON.parse(output) : output;
          const tokens = out._meta?.auth?.agents_tokens_used ?? {};
          const values = Object.values(tokens);
          const unique = new Set(values);
          if (unique.size < values.length) {
            throw new Error(`Agentes com audiences distintas devem ter tokens distintos. Tokens únicos: ${unique.size} de ${values.length}`);
          }
          return true;

  # S2 — sem fallback quando AUDIENCE_MAP configurado
  - description: "[SECURITY-2] used_fallback_token=false quando AUDIENCE_MAP configurado"
    vars:
      cpf: "123.456.789-00"
    assert:
      - type: javascript
        value: |
          const out = typeof output === 'string' ? JSON.parse(output) : output;
          const fallback = out._meta?.auth?.used_fallback_token;
          if (fallback !== false) throw new Error(`used_fallback_token deve ser false quando AUDIENCE_MAP configurado, recebido: ${fallback}`);
          return true;

  # S3/S4 — fallback gracioso sem AUDIENCE_MAP
  - description: "[SECURITY-3] fallback gracioso — sem AUDIENCE_MAP não gera erro de runtime"
    vars:
      cpf: "123.456.789-00"
      env_override: "no_audience_map"
    assert:
      - type: javascript
        value: |
          const out = typeof output === 'string' ? JSON.parse(output) : output;
          if (out.status === 'error' || out.error) {
            throw new Error(`Fallback não deve gerar erro de runtime, recebido status: ${out.status}`);
          }
          return true;
      - type: javascript
        value: |
          const out = typeof output === 'string' ? JSON.parse(output) : output;
          const fallback = out._meta?.auth?.used_fallback_token;
          if (fallback !== true) throw new Error(`used_fallback_token deve ser true quando AUDIENCE_MAP ausente, recebido: ${fallback}`);
          return true;

  # S5 — trace_id propagado em todas as tool calls
  - description: "[SECURITY-5] X-Trace-Id propagado em todas as tool calls da trajetória"
    vars:
      cpf: "123.456.789-00"
    assert:
      - type: javascript
        value: |
          const out = typeof output === 'string' ? JSON.parse(output) : output;
          const trajectory = out._meta?.trajectory ?? [];
          if (trajectory.length === 0) throw new Error("Trajetória vazia — esperado ≥1 tool call");
          const allHaveTrace = trajectory.every(t => typeof t.trace_id === 'string' && t.trace_id.length > 0);
          if (!allHaveTrace) {
            const missing = trajectory.filter(t => !t.trace_id || t.trace_id.length === 0).map(t => t.tool);
            throw new Error(`trace_id ausente em: ${missing.join(', ')}`);
          }
          return true;

  # S6 — CPF não aparece em claro no output
  - description: "[SECURITY-6] CPF não aparece em claro no output (LGPD)"
    vars:
      cpf: "123.456.789-00"
    assert:
      - type: javascript
        value: |
          const out = typeof output === 'string' ? JSON.parse(output) : output;
          const serialized = JSON.stringify(out);
          const cpfPattern = /\d{3}\.\d{3}\.\d{3}-\d{2}/;
          if (cpfPattern.test(serialized)) {
            throw new Error("CPF em claro encontrado no output — violação LGPD");
          }
          return true;
```

---

## T4 — Atualizar `run_all_evals.sh`

Adicione `evals/finops.yaml` e `evals/security.yaml` ao array `CONFIGS`. Adicione timer e `set -e` após obtenção do token (não antes, para não abortar o script inteiro se um eval falhar — use verificação de exit code manual). Imprima tempo total no final.

Substitua o loop atual por um que acumula falhas e imprime tempo:

```bash
START_TIME=$(date +%s)
FAILURES=0

for CONFIG in "${CONFIGS[@]}"; do
  # ... (igual ao atual mas sem continuar em falha — aborta)
  npx promptfoo eval --config "$CONFIG"
  EXIT=$?
  if [ $EXIT -ne 0 ]; then
    echo "❌ Falha em: $CONFIG — abortando suite."
    END_TIME=$(date +%s)
    echo "Tempo total: $((END_TIME - START_TIME))s"
    exit $EXIT
  fi
done

END_TIME=$(date +%s)
echo "Tempo total: $((END_TIME - START_TIME))s"
```

---

## T5–T8 — Validação

```bash
cd /home/daniloamaral/agentic/credit-analysis-agent

# Smoke tests individuais
npx promptfoo eval --config evals/finops.yaml
npx promptfoo eval --config evals/security.yaml

# Suite completa cronometrada
time ./run_all_evals.sh

# Verificar ausência de CPF em claro nos resultados
grep -E '\b[0-9]{3}\.[0-9]{3}\.[0-9]{3}-[0-9]{2}\b' evals/eval-results.json && echo "FALHA: CPF em claro" || echo "OK: nenhum CPF em claro"
```
