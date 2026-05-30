# Delta Spec: Agente de Decisão

**Change ID:** add-decision-agent
**Tipo:** ADDED
**Capability:** credit-analysis / decision

---

## ADDED — AgentDecision

### Identidade

- **Nome:** AgentDecision
- **Papel:** Sub-agente de síntese final e explicabilidade — Etapa 5 da sequência A2A do orquestrador
- **Modelo de fundação:** Gemini 2.5 Flash Lite (via Sensedia AI Gateway)
- **Runtime:** Sensedia AI Gateway — gerencia AuthZ, rate limiting, traces e FinOps

### Responsabilidades

O AgentDecision consolida a análise e emite o veredito final estruturado e justificado.

Ele DEVE:
1. Receber o contexto consolidado enviado pelo orquestrador (`bureau_result`, `documents_result`, `risk_result`, `compliance_result`, `requested_amount`, `request_id`).
2. Aplicar a matriz de decisão baseada nos resultados dos subagentes.
3. Emitir a decisão final (`decision`: approved, rejected, adjusted) e o grau de confiança (`confidence`: 0.00 a 1.00).
4. Gerar justificativa audível e fundamentada, em estrita conformidade com a restrição de Groundedness.
5. Inserir condicionalidades no array `conditions` em caso de aprovação condicionada (`adjusted`).
6. Retornar o resultado contratual unificado ao orquestrador.

Ele NÃO DEVE:
- Alucinar ou citar fatos não comprovados nos relatórios recebidos.
- Expor razões detalhadas de PLD de compliance de forma pública para o solicitante final.
- Aprovar solicitações com compliance rejeitado ou com risco classificado como "high risk".

---

## ADDED — Engenharia de Contexto

### Janela de contexto do AgentDecision

| Elemento | Fonte | Tamanho máximo |
|---|---|---|
| Relatório de Bureau | Orquestrador via A2A | 1.024 tokens |
| Relatório de Documentos | Orquestrador via A2A | 1.024 tokens |
| Relatório de Risco | Orquestrador via A2A | 512 tokens |
| Relatório de Compliance | Orquestrador via A2A | 512 tokens |
| Valor Solicitado | Orquestrador via A2A | 10 dígitos |
| request_id | Orquestrador via A2A | 36 chars (UUID) |
| Políticas de Concessão | System prompt (guide) | 2.048 tokens |

**Princípio de Groundedness Rígido:** O AgentDecision é estritamente limitado às informações explícitas constantes dos payloads recebidos. Não é permitida a dedução de dados de relacionamento comercial não informados.

---

## ADDED — Guides (feedforward)

### Políticas de execução
- O AgentDecision DEVE priorizar a recusa imediata em caso de falha de compliance (`kyc_approved: false` ou `pld_clear: false`).
- O AgentDecision DEVE classificar como `adjusted` com condicionalidades permitidas em caso de risco médio ou pequenos avisos documentais.
- A justificativa da decisão DEVE ter entre 50 e 300 caracteres e conter os motivos concretos do veredito.

### Anti-exemplos críticos

**Anti-exemplo 1 — Alucinação Comercial**
```
❌ ERRADO:
  justification: "Cliente aprovado pois possui excelente histórico de compras com nossa rede parceira e é cliente especial." (Informação não contida nos relatórios).

✅ CORRETO:
  justification: "Aprovado devido a score de bureau sólido (780), risco baixo (PD 4%) e renda comprovada regular."
```

**Anti-exemplo 2 — Exposição de PLD Regulatório**
```
❌ ERRADO:
  justification: "Recusado pois o nome consta em listas de lavagem de dinheiro/sanções COAF." (Risco legal/tipping off).

✅ CORRETO:
  justification: "Solicitação recusada devido a inconsistências cadastrais ou políticas internas." (Seguro e padrão).
```

---

## ADDED — Sensores (feedback)

### Métricas monitoradas pelo Sensedia AI Gateway

| Métrica | Threshold de Alerta | Ação |
|---|---|---|
| Groundedness Score | < 0.85 | Reter decisão + Escalar para HITL de auditoria |
| Justification Latency | > 5s | Log de warning + notificação de lentidão do LLM |
| Explicabilidade LLM-as-judge | < 4/5 estrelas | Alerta operacional de qualidade de justificativa |
| Custo de processamento | > R$ 0,02 por requisição | Alerta de FinOps |

---

## ADDED — Formato de Saída Contratual

Output retornado ao orquestrador via A2A:

```json
{
  "request_id": "string (UUID)",
  "decision": "enum: approved | rejected | adjusted",
  "confidence": "number (0.00–1.00)",
  "justification": "string (máx 300 caracteres)",
  "conditions": "string[] (condicionalidades aplicáveis)",
  "status": "enum: ok | error",
  "reason": "string (nulo ou erro técnico)",
  "processing_time_ms": "number"
}
```
