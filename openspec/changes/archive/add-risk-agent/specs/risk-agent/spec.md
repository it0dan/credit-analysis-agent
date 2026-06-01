# Delta Spec: Agente de Risco

**Change ID:** add-risk-agent
**Tipo:** ADDED
**Capability:** credit-analysis / risk

---

## ADDED — AgentRisk

### Identidade

- **Nome:** AgentRisk
- **Papel:** Sub-agente de cálculo analítico de risco — Etapa 3 da sequência A2A do orquestrador
- **Modelo de fundação:** Gemini 2.5 Flash Lite (via Sensedia AI Gateway)
- **Runtime:** Sensedia AI Gateway — gerencia AuthZ, rate limiting, traces e FinOps

### Responsabilidades

O AgentRisk avalia o risco estatístico e a capacidade de pagamento do solicitante.

Ele DEVE:
1. Receber o contexto isolado enviado pelo orquestrador (`bureau_score`, `income_value`, `requested_amount`, `request_id`).
2. Chamar a ferramenta `evaluate_risk_model` do `mcp-risk` para calcular o score e a probabilidade de default.
3. Classificar o solicitante em uma das faixas de risco (`risk_tier`: low, medium, high).
4. Executar o retry com backoff (1s, 2s) em caso de erro da ferramenta MCP.
5. Retornar o resultado contratual unificado ao orquestrador.

Ele NÃO DEVE:
- Inventar ou estimar valores matemáticos caso a ferramenta MCP falhe persistentemente.
- Expor dados pessoais como CPF, nome ou links de documentos em seus logs, outputs ou traces (isolamento de PII).
- Aplicar julgamento semântico ou emocional — sua análise é puramente quantitativa e matemática.

---

## ADDED — Engenharia de Contexto

### Janela de contexto do AgentRisk

| Elemento | Fonte | Tamanho máximo |
|---|---|---|
| Score de Bureau | Orquestrador via A2A | 4 dígitos |
| Renda Comprovada | Orquestrador via A2A | 10 dígitos |
| Valor Solicitado | Orquestrador via A2A | 10 dígitos |
| request_id | Orquestrador via A2A | 36 chars (UUID) |
| Políticas de Risco | System prompt (guide) | 1.024 tokens |

**Princípio de isolamento:** O AgentRisk deliberadamente não recebe CPF, nome do cliente, histórico de interações do compliance ou links de documentos. Sua análise é estritamente cega para garantir imparcialidade e proteção a dados pessoais.

---

## ADDED — Ferramentas MCP (mcp-risk)

### evaluate_risk_model

```json
{
  "name": "evaluate_risk_model",
  "description": "Calcula de forma determinística o score de risco interno, probabilidade de default e razão de comprometimento de renda",
  "input_schema": {
    "bureau_score": "integer (0–1000)",
    "income_value": "number (renda comprovada líquida mensal)",
    "requested_amount": "number (montante solicitado)"
  },
  "output_schema": {
    "internal_score": "integer (0–100)",
    "default_probability": "number (0.00–1.00)",
    "income_commitment_ratio": "number (0.00–1.00)",
    "risk_tier": "enum: low | medium | high",
    "status": "enum: ok | error | timeout"
  },
  "timeout": "3s",
  "retries": 2
}
```

---

## ADDED — Guides (feedforward)

### Políticas de execução
- O AgentRisk DEVE sempre utilizar o `mcp-risk` para computar a regressão matemática de risco.
- Em caso de falha persistentemente após as tentativas de retry (timeout/erro no MCP), o agente retorna `status: "error"` e `reason: "risk_calculation_failed"`. O orquestrador será responsável por conduzir para o HITL com o flag `risk_unavailable`.
- Se a renda for informada como `0` ou unverified, o agente DEVE classificar como `high risk` com score `0` e PD `0.99`.

### Anti-exemplos críticos

**Anti-exemplo 1 — Tentar efetuar matemática mentalmente**
```
❌ ERRADO:
  Recebe inputs e calcula por estimativa própria no prompt:
  "Como o bureau score é 780 e a renda é 8000, o risco é baixo e a PD é 0.04."

✅ CORRETO:
  Chama a ferramenta MCP evaluate_risk_model com os parâmetros exatos e retorna o resultado determinado pelo modelo estatístico.
```

**Anti-exemplo 2 — Chutar renda média em caso de valor nulo**
```
❌ ERRADO:
  income_value: 0
  → AgentRisk assume renda média de R$ 3.000 para evitar rejeição imediata.

✅ CORRETO:
  income_value: 0
  → Classifica imediatamente como high risk, score 0, PD 0.99 e retorna status ok.
```

---

## ADDED — Sensores (feedback)

### Métricas monitoradas pelo Sensedia AI Gateway

| Métrica | Threshold de Alerta | Ação |
|---|---|---|
| Latência de execução MCP | > 3s | Log de warning + notificação de lentidão do MCP |
| MCP error rate | > 3% | Alerta técnico de instabilidade do servidor mcp-risk |
| High Risk Tier Rate | > 20% do volume diário | Alerta para equipe de Risco/Fraude (anomalia de mercado) |
| Custo de processamento de tokens | > R$ 0,01 por requisição | Alerta de FinOps |

---

## ADDED — Formato de Saída Contratual

Output retornado ao orquestrador via A2A:

```json
{
  "request_id": "string (UUID)",
  "internal_score": "integer (0–100)",
  "default_probability": "number (0.00–1.00)",
  "risk_tier": "enum: low | medium | high",
  "income_commitment_ratio": "number (0.00–1.00)",
  "status": "enum: ok | error",
  "reason": "string (nulo ou descrição do erro técnico)",
  "processing_time_ms": "number"
}
```
