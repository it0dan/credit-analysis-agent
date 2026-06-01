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
- Falha técnica após 3 tentativas é a única causa para `status: "error"`. Divergência de nome ou comprovante ilegível resultam em `status: "ok"` com flags negativas.

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
