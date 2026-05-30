# Delta Spec: Agente de Compliance

**Change ID:** add-compliance-agent
**Tipo:** ADDED
**Capability:** credit-analysis / compliance

---

## ADDED — AgentCompliance

### Identidade

- **Nome:** AgentCompliance
- **Papel:** Sub-agente regulatório — Etapa 4 da sequência A2A do orquestrador
- **Modelo de fundação:** Claude Sonnet (via Sensedia AI Gateway)
- **Runtime:** Sensedia AI Gateway — gerencia AuthZ, rate limiting, traces e FinOps

### Responsabilidades

O AgentCompliance é o guardião regulatório do sistema de análise de crédito.

Ele DEVE:
1. Receber o contexto isolado enviado pelo orquestrador (`applicant_masked_cpf`, `request_id`)
2. Executar as verificações de KYC, PLD e consentimento LGPD via `mcp-kyc`, nessa ordem
3. Aplicar short-circuit: parar imediatamente na primeira verificação negativa
4. Retornar resultado contratual ao orquestrador

Ele NÃO DEVE:
- Escalar para HITL em nenhuma circunstância — falha = recusa imediata
- Continuar a sequência de verificações após uma falha (short-circuit obrigatório)
- Inferir ou assumir aprovação quando `mcp-kyc` retornar erro ou timeout
- Receber ou processar dados de bureau, documentos ou risco (contexto isolado)
- Expor CPF sem mascaramento em qualquer output ou log
- Ser pulado ou ter seu resultado ignorado pelo orquestrador sob qualquer condição

**Regra absoluta:** Qualquer status diferente de "ok" — incluindo erro técnico,
timeout, resposta malformada ou indisponibilidade do `mcp-kyc` — resulta em
`rejected: true` imediatamente. Não há exceção.

---

## ADDED — Engenharia de Contexto

### Janela de contexto do AgentCompliance

| Elemento               | Fonte                     | Tamanho máximo |
|------------------------|---------------------------|----------------|
| CPF mascarado          | Orquestrador via A2A      | 16 chars       |
| request_id             | Orquestrador via A2A      | 36 chars (UUID)|
| Políticas de compliance| System prompt (guide)     | 1.024 tokens   |

**Princípio de isolamento:** O AgentCompliance deliberadamente não recebe score
de bureau, renda confirmada, resultado de risco ou valor solicitado. Compliance
é uma verificação independente — seu resultado não pode ser influenciado pelo
perfil financeiro do solicitante. Isso é um requisito regulatório, não uma
limitação técnica.

---

## ADDED — Ferramentas MCP (mcp-kyc)

### verify_kyc

```json
{
  "name": "verify_kyc",
  "description": "Verifica identidade do solicitante junto ao bureau de KYC",
  "input_schema": {
    "applicant_masked_cpf": "string (formato XXX.XXX.XXX-XX)",
    "request_id": "string (UUID)"
  },
  "output_schema": {
    "kyc_approved": "boolean",
    "identity_match": "boolean",
    "document_valid": "boolean",
    "status": "enum: ok | rejected | error | timeout",
    "reason": "string (presente quando kyc_approved: false)"
  },
  "timeout": "3s",
  "retries": 0
}
```

> **Nota sobre retries:** O AgentCompliance NÃO faz retry em nenhuma ferramenta.
> Um timeout ou erro na primeira tentativa é tratado como falha definitiva.
> Essa política é intencional: retry poderia mascarar indisponibilidade real
> do sistema de KYC/PLD.

---

### check_pld

```json
{
  "name": "check_pld",
  "description": "Verifica solicitante em listas de PLD/COAF e sanções internacionais",
  "input_schema": {
    "applicant_masked_cpf": "string (formato XXX.XXX.XXX-XX)",
    "request_id": "string (UUID)"
  },
  "output_schema": {
    "pld_clear": "boolean",
    "sanctions_match": "boolean",
    "risk_level": "enum: none | low | medium | high",
    "status": "enum: ok | rejected | error | timeout",
    "reason": "string (presente quando pld_clear: false)"
  },
  "timeout": "3s",
  "retries": 0
}
```

> **Condição de short-circuit:** `check_pld` só é chamado se `verify_kyc`
> retornar `kyc_approved: true`. KYC false encerra a sequência antes de
> qualquer consulta PLD.

---

### verify_lgpd_consent

```json
{
  "name": "verify_lgpd_consent",
  "description": "Confirma registro de consentimento LGPD coletado no canal de origem",
  "input_schema": {
    "applicant_masked_cpf": "string (formato XXX.XXX.XXX-XX)",
    "request_id": "string (UUID)"
  },
  "output_schema": {
    "lgpd_consent": "boolean",
    "consent_date": "string (ISO 8601, presente quando lgpd_consent: true)",
    "consent_scope": "string[] (escopos autorizados)",
    "status": "enum: ok | rejected | error | timeout",
    "reason": "string (presente quando lgpd_consent: false)"
  },
  "timeout": "2s",
  "retries": 0
}
```

> **Condição de short-circuit:** `verify_lgpd_consent` só é chamado se
> `verify_kyc` e `check_pld` retornarem aprovação.
>
> **Política de lgpd_consent false:** Recusa imediata. Sem consentimento
> registrado, não há base legal para processar dados pessoais do solicitante
> (Art. 7º, LGPD). Essa condição não escala para HITL — o DPO deve ser
> notificado via canal separado (fora do escopo deste agente).

---

## ADDED — Sequência Interna de Verificação

```
Input: { applicant_masked_cpf, request_id }
        │
        ▼
verify_kyc
  ├── kyc_approved: false  →  RECUSA IMEDIATA (reason: kyc_failed)
  ├── status: error        →  RECUSA IMEDIATA (reason: kyc_unavailable)
  ├── status: timeout      →  RECUSA IMEDIATA (reason: kyc_timeout)
  └── kyc_approved: true   →  continuar
        │
        ▼
check_pld
  ├── pld_clear: false     →  RECUSA IMEDIATA (reason: pld_positive)
  ├── status: error        →  RECUSA IMEDIATA (reason: pld_unavailable)
  ├── status: timeout      →  RECUSA IMEDIATA (reason: pld_timeout)
  └── pld_clear: true      →  continuar
        │
        ▼
verify_lgpd_consent
  ├── lgpd_consent: false  →  RECUSA IMEDIATA (reason: lgpd_no_consent)
  ├── status: error        →  RECUSA IMEDIATA (reason: lgpd_unavailable)
  ├── status: timeout      →  RECUSA IMEDIATA (reason: lgpd_timeout)
  └── lgpd_consent: true   →  APROVADO

Output: { kyc_approved, pld_clear, lgpd_consent, status, reason, tools_called[] }
```

---

## ADDED — Guides (feedforward)

### Políticas de execução

- O AgentCompliance DEVE sempre chamar `verify_kyc` primeiro
- O AgentCompliance DEVE aplicar short-circuit: parar na primeira falha
- O AgentCompliance NUNCA deve escalar para HITL — qualquer falha = recusa
- O AgentCompliance NUNCA deve inferir aprovação por ausência de dados negativos
- O AgentCompliance DEVE registrar `reason` em toda recusa

### Anti-exemplos críticos

**Anti-exemplo 1 — Escalar para HITL em falha de compliance**
```
❌ ERRADO:
  verify_kyc retornou status: "timeout"
  → AgentCompliance retorna { status: "pending_human_review" }
  → orquestrador aciona handoff_to_human

✅ CORRETO:
  verify_kyc retornou status: "timeout"
  → AgentCompliance retorna { rejected: true, reason: "kyc_timeout" }
  → orquestrador recusa imediatamente
  (compliance não tem fallback — timeout = recusa)
```

**Anti-exemplo 2 — Ignorar short-circuit após falha**
```
❌ ERRADO:
  verify_kyc retornou kyc_approved: false
  → AgentCompliance continua e chama check_pld
  → check_pld retorna pld_clear: true
  → AgentCompliance retorna aprovação baseado no PLD

✅ CORRETO:
  verify_kyc retornou kyc_approved: false
  → AgentCompliance retorna imediatamente: { rejected: true, reason: "kyc_failed" }
  → check_pld e verify_lgpd_consent NÃO são chamados
```

**Anti-exemplo 3 — Inferir aprovação por ausência de dados**
```
❌ ERRADO:
  mcp-kyc retornou resposta malformada (campo kyc_approved ausente)
  → AgentCompliance assume kyc_approved: true (ausência = ok)
  → continua a sequência

✅ CORRETO:
  mcp-kyc retornou resposta malformada
  → tratar como status: "error"
  → AgentCompliance retorna: { rejected: true, reason: "kyc_unavailable" }
  (campo ausente nunca é interpretado como aprovação)
```

---

## ADDED — Sensores (feedback)

### Métricas monitoradas pelo Sensedia AI Gateway

| Métrica                        | Threshold de alerta | Ação                                    |
|--------------------------------|---------------------|-----------------------------------------|
| Disponibilidade do mcp-kyc     | < 99,5%             | Alerta crítico — afeta todas as análises|
| Timeout rate (verify_kyc)      | > 1%                | Alerta operacional                      |
| Timeout rate (check_pld)       | > 1%                | Alerta operacional                      |
| Taxa de recusa por KYC         | > 20% (anomalia)    | Investigar qualidade dos dados de input |
| Taxa de recusa por PLD         | > 5% (anomalia)     | Alerta regulatório para equipe de risco |
| Latência total do agente       | > 8s                | Alerta — pressiona SLO do orquestrador  |
| Resposta malformada do mcp-kyc | > 0%                | Alerta de integridade do MCP Server     |

---

## ADDED — Formato de Saída Contratual

Output retornado ao orquestrador via A2A:

```json
{
  "request_id": "string (UUID)",
  "kyc_approved": "boolean",
  "pld_clear": "boolean",
  "lgpd_consent": "boolean",
  "status": "enum: ok | rejected | error | timeout",
  "reason": "enum: kyc_failed | kyc_unavailable | kyc_timeout | pld_positive | pld_unavailable | pld_timeout | lgpd_no_consent | lgpd_unavailable | lgpd_timeout | null",
  "tools_called": "string[] (quais ferramentas foram efetivamente chamadas)",
  "processing_time_ms": "number"
}
```

> **Nota sobre `reason` e exposição pública:** O campo `reason` é para uso
> interno (traces, auditoria) e NÃO deve ser exposto ao solicitante final.
> Em particular, razões de PLD (`pld_positive`) são protegidas por sigilo
> regulatório. O orquestrador é responsável por mapear `reason` para uma
> mensagem genérica ao solicitante.
