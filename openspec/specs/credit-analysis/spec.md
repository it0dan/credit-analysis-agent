# Delta Spec: Agente Orquestrador de Análise de Crédito

**Change ID:** add-orchestrator-agent
**Tipo:** ADDED
**Capability:** credit-analysis / orchestrator

---

## ADDED — Agente Orquestrador

### Identidade

- **Nome:** AgentOrchestrator
- **Papel:** Agente principal do sistema de análise de crédito
- **Modelo de fundação:** Claude Sonnet (via Sensedia AI Gateway)
- **Runtime:** Sensedia AI Gateway — gerencia AuthZ, rate limiting, traces e FinOps

### Responsabilidades

O AgentOrchestrator é o único ponto de entrada para solicitações de crédito.
Ele DEVE:
1. Carregar o contexto do solicitante (memória semântica + episódica)
2. Planejar a sequência de análise com base nas políticas de crédito (memória procedural)
3. Delegar para cada sub-agente via A2A na sequência definida
4. Consolidar os resultados recebidos
5. Avaliar o threshold de valor para determinar fluxo automático ou HITL
6. Emitir ou encaminhar a decisão final com justificativa auditável

O AgentOrchestrator NÃO DEVE:
- Acessar sistemas externos diretamente (apenas via sub-agentes)
- Emitir decisão de crédito sem retorno dos 4 sub-agentes de análise
- Aprovar créditos acima de R$ 50.000 sem acionar HITL
- Inferir ou inventar dados de bureau quando o AgentBureau retornar erro
- Expor CPF sem mascaramento em qualquer output ou log

---

## ADDED — Engenharia de Contexto

### Janela de contexto do orquestrador

| Elemento                        | Fonte                  | Tamanho máximo |
|---------------------------------|------------------------|----------------|
| Dados da solicitação            | Input do canal         | 512 tokens     |
| Perfil semântico do cliente     | Vector store (RAG)     | 1.024 tokens   |
| Últimas 3 interações do cliente | Base de eventos        | 512 tokens     |
| Políticas de crédito ativas     | System prompt (guide)  | 2.048 tokens   |
| Resultados dos sub-agentes      | Acumulado via A2A      | 2.048 tokens   |

**Política de compressão:** Se o contexto acumulado dos sub-agentes ultrapassar 2.048 tokens,
o orquestrador DEVE sumarizar os resultados anteriores antes de chamar o próximo sub-agente,
preservando apenas score, flags críticos e recomendação.

### Tipos de memória utilizados

| Tipo        | Conteúdo                                          | Quando acionado                            |
|-------------|---------------------------------------------------|--------------------------------------------|
| Semântica   | Perfil do cliente, histórico de crédito, renda    | Início de toda solicitação                 |
| Episódica   | Interações anteriores, decisões passadas          | Início, para detectar reincidência         |
| Procedural  | Políticas de crédito, playbooks, restrições       | Planejamento da sequência e avaliação final|

---

## ADDED — Sequência de Delegação A2A

O orquestrador DEVE seguir esta sequência serial na v1:

```
Etapa 1: bureau.get_score
  Input:  { applicant_masked_cpf, request_id }
  Output: { score, restrictions[], status }
  Timeout: 3s | Retries: 2 | Fallback: escalar para HITL com flag bureau_unavailable

Etapa 2: documents.validate
  Input:  { document_urls[], applicant_name, request_id }
  Output: { identity_valid, income_confirmed, income_value, status }
  Timeout: 5s | Retries: 2 | Fallback: escalar para HITL com flag docs_unverified

Etapa 3: risk.evaluate
  Input:  { bureau_score, income_value, requested_amount, request_id }
  Output: { internal_score, default_probability, risk_tier, status }
  Timeout: 3s | Retries: 2 | Fallback: escalar para HITL com flag risk_unavailable

Etapa 4: compliance.check
  Input:  { applicant_masked_cpf, request_id }
  Output: { kyc_approved, pld_clear, lgpd_consent, status }
  Timeout: 3s | Retries: 2 | Fallback: RECUSA IMEDIATA (compliance não tem fallback)

Etapa 5: decision.synthesize
  Input:  { todos os outputs anteriores, requested_amount, request_id }
  Output: { decision, confidence, justification, conditions[], trace_id }
  Timeout: 5s | Retries: 1 | Fallback: escalar para HITL
```

**Regra crítica:** Se `compliance.check` retornar `kyc_approved: false` ou `pld_clear: false`,
o orquestrador DEVE recusar imediatamente e NÃO chamar `decision.synthesize`.

---

## ADDED — Threshold e HITL

### Critério de threshold

| Valor solicitado   | Fluxo              | Ação do orquestrador                           |
|--------------------|--------------------|------------------------------------------------|
| ≤ R$ 50.000        | Automático         | Emitir decisão diretamente                     |
| > R$ 50.000        | HITL obrigatório   | Acionar `handoff_to_human` e aguardar          |
| Qualquer valor     | Fallback ativo     | Escalar para HITL com flags de erro            |

### Ferramenta: handoff_to_human

```json
{
  "name": "handoff_to_human",
  "description": "Encaminha análise para aprovação de analista humano",
  "input_schema": {
    "request_id": "string",
    "applicant_masked_cpf": "string (formato XXX.XXX.XXX-XX)",
    "requested_amount": "number",
    "analysis_summary": "string (máx. 500 chars)",
    "reason": "enum: threshold_exceeded | compliance_review | fallback_error",
    "error_flags": "string[] (opcional)"
  },
  "output_schema": {
    "status": "enum: pending | approved | rejected | adjusted",
    "analyst_id": "string",
    "adjusted_amount": "number (opcional, quando status=adjusted)",
    "notes": "string"
  }
}
```

**SLA do analista:** Resposta em até 4h em horário comercial (8h–18h).
**Comportamento de espera:** O orquestrador registra o `request_id` como pendente
e retorna ao solicitante com `status: pending` e prazo estimado.

---

## ADDED — Guides (feedforward)

### Políticas de execução

- O orquestrador DEVE aguardar resposta de cada sub-agente antes de chamar o próximo
- O orquestrador NUNCA deve pular a etapa de compliance, independente do valor ou score
- O orquestrador DEVE mascarar o CPF antes de qualquer delegação A2A
- O orquestrador DEVE registrar `trace_id` único para toda a sequência de análise

### Anti-exemplos críticos

**Anti-exemplo 1 — Decisão sem compliance**
```
❌ ERRADO:
  bureau retornou score 750
  documents retornou renda confirmada
  risk retornou low_risk
  → orquestrador aprova sem chamar compliance

✅ CORRETO:
  Chamar compliance.check obrigatoriamente
  Aguardar retorno antes de qualquer decisão
```

**Anti-exemplo 2 — Alucinação de bureau**
```
❌ ERRADO:
  bureau.get_score retornou erro de timeout
  → orquestrador assume score 700 e continua a análise

✅ CORRETO:
  Tentar retry (máx. 2x)
  Se persistir: acionar handoff_to_human com flag bureau_unavailable
  Nunca inferir ou inventar dados de bureau
```

**Anti-exemplo 3 — Bypass de HITL**
```
❌ ERRADO:
  Valor solicitado: R$ 80.000
  decision.synthesize retornou approved com confidence 0.95
  → orquestrador emite aprovação diretamente

✅ CORRETO:
  Valor > R$ 50.000 SEMPRE aciona handoff_to_human
  Não importa o confidence score do AgentDecision
```

---

## ADDED — Sensores (feedback)

### Métricas monitoradas pelo Sensedia AI Gateway

| Métrica                    | Threshold de alerta | Ação                            |
|----------------------------|---------------------|---------------------------------|
| Latência total             | > 8s                | Log de warning + notificação    |
| Tool success rate (A2A)    | < 95%               | Alerta operacional              |
| Groundedness da decisão    | < 0.85              | Reter decisão, escalar para HITL|
| Custo por análise          | > R$ 0,15           | Alerta FinOps                   |
| Compliance failure rate    | > 0%                | Alerta crítico imediato         |

---

## ADDED — Formato de saída do orquestrador

```json
{
  "request_id": "string",
  "status": "enum: approved | rejected | pending_human_review",
  "decision": "enum: approved | rejected | adjusted | pending",
  "requested_amount": "number",
  "approved_amount": "number (null se rejected)",
  "justification": "string (mín. 50 chars, max 300 chars)",
  "conditions": "string[] (ex: ['comprovante de renda atualizado em 90 dias'])",
  "trace_id": "string (UUID)",
  "processing_time_ms": "number",
  "agents_consulted": "string[]"
}
```


---

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



# Delta Spec: Agente de Bureau de Crédito

**Change ID:** add-bureau-agent
**Tipo:** ADDED
**Capability:** credit-analysis / bureau

---

## ADDED — AgentBureau

### Identidade

- **Nome:** AgentBureau
- **Papel:** Sub-agente de dados externos — Etapa 1 da sequência A2A do orquestrador
- **Modelo de fundação:** Claude Sonnet (via Sensedia AI Gateway)
- **Runtime:** Sensedia AI Gateway — gerencia AuthZ, rate limiting, traces e FinOps

### Responsabilidades

O AgentBureau é a primeira etapa da análise de crédito. Consulta bureaus
externos (Serasa/SPC) e retorna dados brutos de score e restrições.

Ele DEVE:
1. Receber o contexto isolado enviado pelo orquestrador (`applicant_masked_cpf`, `request_id`)
2. Chamar `mcp-bureau.get_score` com os dados recebidos
3. Executar retry com backoff em caso de falha técnica (máx. 2 retries)
4. Retornar o resultado contratual ao orquestrador

Ele NÃO DEVE:
- Aplicar regras de negócio sobre o score retornado (score baixo não é recusa)
- Inferir, estimar ou inventar dados de bureau em caso de falha persistente
- Receber ou processar dados de outros sub-agentes (contexto isolado)
- Expor CPF real em qualquer output, log ou trace
- Chamar sistemas externos diretamente — apenas via `mcp-bureau`

**Regra absoluta:** Após esgotamento de retries (3 tentativas sem sucesso),
retornar `status: "error"` com `reason: "bureau_unavailable"`. Nunca inventar
dados. O orquestrador é responsável por escalar para HITL.

---

## ADDED — Engenharia de Contexto

### Janela de contexto do AgentBureau

| Elemento               | Fonte                     | Tamanho máximo |
|------------------------|---------------------------|----------------|
| CPF mascarado          | Orquestrador via A2A      | 16 chars       |
| request_id             | Orquestrador via A2A      | 36 chars (UUID)|
| Políticas de bureau    | System prompt (guide)     | 512 tokens     |

**Princípio de isolamento:** O AgentBureau não recebe valor solicitado, renda,
histórico de crédito ou resultados de outros agentes. A consulta ao bureau deve
ser independente de qualquer contexto financeiro do solicitante — isso garante
que o score retornado é imparcial e rastreável.

---

## ADDED — Ferramenta MCP (mcp-bureau)

### get_score

```json
{
  "name": "get_score",
  "description": "Consulta score de crédito e restrições ativas no Serasa/SPC",
  "input_schema": {
    "applicant_masked_cpf": "string (formato XXX.XXX.XXX-XX)",
    "request_id": "string (UUID)"
  },
  "output_schema": {
    "score": "integer (0–1000)",
    "restrictions": "array de string (lista de restrições ativas, ex: ['atraso_30d', 'protesto'])",
    "bureau_source": "enum: serasa | spc | both",
    "consulted_at": "string (ISO 8601)",
    "status": "enum: ok | error | timeout",
    "reason": "string (presente quando status != ok, ex: 'serviço indisponível')"
  },
  "timeout_per_attempt": "3s",
  "retries": 2,
  "backoff": "1s após tentativa 1, 2s após tentativa 2"
}
```

**Política de retry:**

```
Tentativa 1 (timeout 3s)
  ├── ok        → retornar resultado imediatamente
  └── erro/timeout → aguardar 1s

Tentativa 2 (timeout 3s)
  ├── ok        → retornar resultado imediatamente
  └── erro/timeout → aguardar 2s

Tentativa 3 (timeout 3s)
  ├── ok        → retornar resultado imediatamente
  └── erro/timeout → retornar { status: "error", reason: "bureau_unavailable" }
```

**Nota sobre de-mascaramento do CPF:** O `mcp-bureau` recebe o CPF mascarado
e resolve o CPF real internamente via `request_id` + vault do Gateway.
O AgentBureau nunca tem acesso ao CPF real — isso é responsabilidade da
infraestrutura (MCP Server), não da lógica do agente.

---

## ADDED — Guides (feedforward)

### Políticas de execução

- O AgentBureau DEVE sempre chamar `get_score` antes de qualquer outra ação
- O AgentBureau DEVE executar o retry internamente antes de retornar erro
- O AgentBureau NUNCA deve inferir, estimar ou inventar score em caso de falha
- O AgentBureau NUNCA deve aplicar regras de negócio sobre o score (score baixo ≠ recusa)
- O AgentBureau DEVE retornar `status: "ok"` sempre que a consulta for bem-sucedida,
  independente do valor do score ou das restrições retornadas

### Anti-exemplos críticos

**Anti-exemplo 1 — Inventar score após timeout esgotado**
```
❌ ERRADO:
  get_score falhou nas 3 tentativas (timeout)
  → AgentBureau retorna { score: 700, status: "ok", reason: "estimado" }

✅ CORRETO:
  get_score falhou nas 3 tentativas
  → AgentBureau retorna { status: "error", reason: "bureau_unavailable" }
  (o orquestrador escalará para HITL — nunca inventar dados)
```

**Anti-exemplo 2 — Aplicar regra de negócio sobre score**
```
❌ ERRADO:
  get_score retornou score: 280, restrictions: ["protesto", "atraso_60d"]
  → AgentBureau retorna { status: "rejected", reason: "score_insuficiente" }

✅ CORRETO:
  get_score retornou score: 280, restrictions: ["protesto", "atraso_60d"]
  → AgentBureau retorna { score: 280, restrictions: [...], status: "ok" }
  (AgentRisk e AgentDecision avaliam os dados — bureau só consulta e repassa)
```

**Anti-exemplo 3 — Expor CPF real no output**
```
❌ ERRADO:
  get_score retornou dados de "123.456.789-00"
  → AgentBureau inclui "cpf": "123.456.789-00" no output

✅ CORRETO:
  Output nunca contém campo CPF
  Se necessário referenciar o solicitante, usar request_id
```

---

## ADDED — Sensores (feedback)

### Métricas monitoradas pelo Sensedia AI Gateway

| Métrica                        | Threshold de alerta | Ação                                       |
|--------------------------------|---------------------|--------------------------------------------|
| Timeout rate (get_score)       | > 5%                | Alerta operacional — verificar Serasa/SPC  |
| Retry rate                     | > 10%               | Alerta — instabilidade do bureau           |
| Latência total (incl. retries) | > 9s                | Alerta — pressiona SLO do orquestrador     |
| bureau_unavailable rate        | > 2%                | Alerta crítico — impacta todos os fluxos   |
| Score 0 rate                   | > 15% (anomalia)    | Investigar qualidade dos dados de input    |

---

## ADDED — Formato de Saída Contratual

Output retornado ao orquestrador via A2A:

```json
{
  "request_id": "string (UUID recebido no input)",
  "score": "integer (0–1000, presente quando status: ok)",
  "restrictions": "string[] (lista de restrições ativas, vazia se nenhuma)",
  "bureau_source": "enum: serasa | spc | both (presente quando status: ok)",
  "consulted_at": "string (ISO 8601, presente quando status: ok)",
  "status": "enum: ok | error | timeout",
  "reason": "string (presente quando status != ok)",
  "attempts": "integer (1–3, quantas tentativas foram feitas)",
  "processing_time_ms": "number",
  "trace_id": "string (= request_id, para correlação end-to-end)"
}
```

> **Campos obrigatórios em caso de erro:**
> `request_id`, `status: "error"`, `reason: "bureau_unavailable"`,
> `attempts`, `processing_time_ms`, `trace_id`.
> Campos de score (`score`, `restrictions`, `bureau_source`, `consulted_at`)
> NÃO estão presentes em respostas de erro.

---

# Delta Spec: Agente de Validação de Documentos

**Change ID:** add-documents-agent  
**Tipo:** ADDED  
**Capability:** credit-analysis / documents  

---

## ADDED — AgentDocuments

### Identidade

- **Nome:** AgentDocuments
- **Papel:** Sub-agente de OCR e validação de documentos — Etapa 2 da sequência A2A do orquestrador
- **Modelo de fundação:** Gemini 2.5 Flash Lite (via Sensedia AI Gateway)
- **Runtime:** Sensedia AI Gateway — gerencia AuthZ, rate limiting, traces e FinOps

### Responsabilidades

O AgentDocuments é responsável por atestar a veracidade e consistência cadastral dos documentos enviados e extrair a renda líquida mensal comprovada.

Ele DEVE:
1. Receber o contexto isolado enviado pelo orquestrador (`document_urls[]`, `applicant_name`, `request_id`).
2. Chamar a ferramenta `validate_identity` do `mcp-documents` para analisar o documento de identidade.
3. Chamar a ferramenta `verify_income` do `mcp-documents` para analisar o comprovante de renda.
4. Aplicar Fuzzy Matching inteligente para comparar o nome extraído do documento com o `applicant_name` cadastrado.
5. Aplicar o loop de retry com backoff (1s, 2s) em caso de timeouts ou erros transientes das APIs de OCR.
6. Retornar o resultado contratual unificado ao orquestrador.

Ele NÃO DEVE:
- Avaliar a suficiência ou capacidade de pagamento da renda extraída (responsabilidade do `AgentRisk`).
- Escalar para HITL por conta própria em caso de divergência cadastral ou renda não confirmada — ele deve retornar o status "ok" com as flags `identity_valid: false` ou `income_confirmed: false` e deixar a tomada de decisão para o orquestrador/analista humano.
- Expor CPF real ou dados confidenciais nos logs.

---

## ADDED — Engenharia de Contexto

### Janela de contexto do AgentDocuments

| Elemento | Fonte | Tamanho máximo |
| :--- | :--- | :--- |
| URLs dos Documentos | Orquestrador via A2A | 3x URLs de até 2048 chars |
| Nome do Solicitante | Orquestrador via A2A | 80 chars |
| request_id | Orquestrador via A2A | 36 chars (UUID) |
| Políticas de Validação | System prompt (guide) | 1.024 tokens |

**Princípio de isolamento:** O AgentDocuments não recebe scores de bureau, restrições ou dados de compliance. Ele deve avaliar os documentos puramente de forma independente, evitando qualquer viés analítico.

---

## ADDED — Ferramentas MCP (mcp-documents)

### validate_identity

```json
{
  "name": "validate_identity",
  "description": "Executa OCR no documento de identidade (RG/CNH), valida autenticidade e extrai o nome impresso",
  "input_schema": {
    "document_urls": "string[] (URLs públicas ou assinadas dos arquivos)",
    "request_id": "string (UUID)"
  },
  "output_schema": {
    "identity_found": "boolean",
    "document_name": "string (nome extraído do documento)",
    "document_type": "enum: RG | CNH | passport | unknown",
    "document_status": "enum: active | expired | unreadable | invalid",
    "status": "enum: ok | error | timeout"
  },
  "timeout": "5s",
  "retries": 2
}
```

---

### verify_income

```json
{
  "name": "verify_income",
  "description": "Analisa comprovantes de renda (holerite, extrato, pro-labore), valida legibilidade e extrai valor líquido consolidado",
  "input_schema": {
    "document_urls": "string[] (URLs públicas ou assinadas dos arquivos)",
    "request_id": "string (UUID)"
  },
  "output_schema": {
    "income_confirmed": "boolean",
    "income_value": "number (valor líquido mensal consolidado)",
    "income_source": "enum: payslip | bank_statement | tax_return | unknown",
    "status": "enum: ok | error | timeout"
  },
  "timeout": "5s",
  "retries": 2
}
```

---

## ADDED — Sequência Interna de Verificação

```
Input: { document_urls, applicant_name, request_id }
        │
        ├──────────────────────────────────────────────┐
        ▼ (Paralelo ou sequencial rápido)               ▼
validate_identity                               verify_income
  ├── status: ok                                  ├── status: ok
  │     └─ LLM aplica Fuzzy Match                   │     └─ Extrai income_value
  │        com applicant_name                       │
  └── status: error/timeout (após 3 tentativas)   └── status: error/timeout (após 3 tentativas)
        │                                               │
        ▼                                               ▼
   Se persistir falha técnica em qualquer ferramenta:
   → RECUSA TÉCNICA IMEDIATA: retorna status: "error" (reason: docs_unavailable)
   
   Se sucesso operacional:
   → Retorna status: "ok" unificado (identity_valid, income_confirmed, income_value)
```

---

## ADDED — Guides (feedforward)

### Políticas de execução
- O AgentDocuments DEVE acionar ambas as ferramentas de documentos quando fornecidas.
- O AgentDocuments DEVE usar o LLM para realizar a tolerância de nomes (Fuzzy Match).
- Pequenas variações de grafia e acentuação NÃO de-validam o documento.
- Falha técnica após 3 tentativas é a única causa para `status: "error"`. Divergência de nome ou comprovante ilegível resultam in `status: "ok"` com flags negativas.

### Anti-exemplos críticos

**Anti-exemplo 1 — Falta de tolerância no Fuzzy Match**
```
❌ ERRADO:
  applicant_name: "João da Silva"
  document_name: "Joao da Silva" (Sem acento)
  → AgentDocuments retorna { identity_valid: false }

✅ CORRETO:
  Falta de acento é aceitável.
  → AgentDocuments retorna { identity_valid: true }
```

**Anti-exemplo 2 — Presumir renda em caso de falha de leitura**
```
❌ ERRADO:
  verify_income retorna income_confirmed: false e status: ok (ilegível)
  → AgentDocuments assume renda média de R$ 3.000.00
  → retorna { income_confirmed: true, income_value: 3000 }

✅ CORRETO:
  Se o comprovante for ilegível, a renda comprovada é 0.
  → AgentDocuments retorna { income_confirmed: false, income_value: 0 }
```

---

## ADDED — Sensores (feedback)

### Métricas monitoradas pelo Sensedia AI Gateway

| Métrica | Threshold de Alerta | Ação |
| :--- | :--- | :--- |
| Latência de processamento OCR | > 12s | Log de warning + notificação de lentidão |
| OCR error rate | > 3% | Alerta técnico de instabilidade do OCR |
| Nome divergente (Fuzzy fail) | > 10% do volume | Alerta de fraude cadastral massiva |
| Custo de processamento | > R$ 0,05 por requisição | Alerta de FinOps sobre tokens de imagem |

---

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
- Em caso de falha persistente após as tentativas de retry (timeout/erro no MCP), o agente retorna `status: "error"` e `reason: "risk_calculation_failed"`. O orquestrador será responsável por conduzir para o HITL com o flag `risk_unavailable`.
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

---

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