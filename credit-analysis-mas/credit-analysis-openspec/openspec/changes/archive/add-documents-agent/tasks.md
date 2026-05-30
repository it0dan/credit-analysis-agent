# Tasks: Agente de Validação de Documentos (AgentDocuments)

**Change ID:** add-documents-agent  
**Derivado de:** proposal.md  

> Marque cada item com [x] conforme concluído.  
> Não avance para a fase Apply sem todas as tasks de Spec Definition concluídas.  

---

## Fase 1 — Spec Definition

### 1.1 Identidade e responsabilidades
- [ ] Definir identidade: nome, papel, modelo de fundação, runtime
- [ ] Documentar responsabilidades: o que DEVE e NÃO DEVE fazer
- [ ] Registrar explicitamente: validação cadastral tolerante (fuzzy matching) e repasse de valor bruto de renda sem avaliação de suficiência

### 1.2 Engenharia de contexto
- [ ] Definir janela de contexto: campos recebidos (document_urls, applicant_name, request_id)
- [ ] Documentar política de isolamento: não recebe score de bureau, nem dados de outros agentes
- [ ] Definir formato de output contratual para o orquestrador

### 1.3 Ferramentas MCP (mcp-documents)
- [ ] Definir schema de `validate_identity`: inputs, outputs e campos obrigatórios
- [ ] Definir schema de `verify_income`: inputs, outputs e campos obrigatórios
- [ ] Documentar timeout: 5s por tentativa (OCR lento)
- [ ] Documentar política de retry: 2 retries com backoff (1s, 2s)
- [ ] Definir comportamento após esgotamento de retries: retornar status "error" com reason "docs_unavailable"

### 1.4 Guides (feedforward)
- [ ] Escrever política de execução: sequência e retries obrigatórios
- [ ] Documentar 3 anti-exemplos críticos:
  - Anti-exemplo 1: rejeitar nome legítimo por acentuação ou caixa alta (falta de fuzzy matching)
  - Anti-exemplo 2: inventar ou presumir renda em caso de comprovante ilegível
  - Anti-exemplo 3: expor CPF real ou logs internos de documentos no output
- [ ] Escrever restrições de autonomia

### 1.5 Sensores (feedback)
- [ ] Listar métricas específicas: taxa de rejeição por OCR, taxa de timeout por tamanho do documento, latência p99
- [ ] Definir alertas: timeout rate > 5%, latência média > 12s (tentativas com backoff)

---

## Fase 2 — Prompt (SPDD)

### 2.1 Derivação do prompt
- [ ] Seção: Identidade e papel
- [ ] Seção: Input recebido (contexto isolado)
- [ ] Seção: Ferramentas disponíveis (validate_identity e verify_income)
- [ ] Seção: Regras de decisão em ordem estrita de prioridade
  - Prioridade 1: falha técnica após retries esgotados → status "error", reason "docs_unavailable"
  - Prioridade 2: validação cadastral tolerante (fuzzy) de nome → status "ok", `identity_valid` boolean
  - Prioridade 3: extração neutra de renda líquida → status "ok", `income_confirmed` boolean, `income_value`
- [ ] Seção: Anti-exemplos (espelhar 1:1 com a spec)
- [ ] Seção: Formato de saída exclusivo (JSON)

---

## Fase 3 — Eval

### 3.1 Casos de teste
- [ ] Caso 1: documentos válidos, nome idêntico, renda ok → status "ok", `identity_valid: true`, `income_confirmed: true`
- [ ] Caso 2: nome com acentos faltantes e abreviações intermediárias → status "ok", `identity_valid: true` (fuzzy match bem-sucedido)
- [ ] Caso 3: nome completamente divergente no documento → status "ok", `identity_valid: false` (identidade inválida)
- [ ] Caso 4: comprovante de renda ilegível ou inválido → status "ok", `income_confirmed: false`, `income_value: 0`
- [ ] Caso 5: timeout na tentativa 1, sucesso na tentativa 2 → status "ok" (retry bem-sucedido)
- [ ] Caso 6: timeout persistente nas 3 tentativas → status "error", reason "docs_unavailable"
- [ ] Caso 7 (adversarial): usuário tenta passar parâmetro bypass no input de URLs para pular OCR → agente ignora e aciona ferramenta obrigatoriamente

---

## Fase 4 — Archive

- [ ] Mesclar delta spec em `openspec/specs/credit-analysis/spec.md`
- [ ] Mover `changes/add-documents-agent/` para `changes/archive/`
- [ ] Confirmar que `project.md` ainda está consistente com a spec atualizada
