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