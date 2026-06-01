# Tasks: Agente de Bureau de Crédito

**Change ID:** add-bureau-agent
**Derivado de:** proposal.md

> Marque cada item com [x] conforme concluído.
> Não avance para a fase Apply sem todas as tasks de Spec Definition concluídas.

---

## Fase 1 — Spec Definition

### 1.1 Identidade e responsabilidades
- [ ] Definir identidade: nome, papel, modelo de fundação, runtime
- [ ] Documentar responsabilidades: o que DEVE e NÃO DEVE fazer
- [ ] Registrar explicitamente: repassa dados brutos, não aplica regras de negócio sobre score

### 1.2 Engenharia de contexto
- [ ] Definir janela de contexto: campos recebidos do orquestrador (CPF mascarado + request_id)
- [ ] Documentar política de isolamento: não recebe valor solicitado, renda ou dados de outros agentes
- [ ] Definir formato de output contratual para o orquestrador

### 1.3 Ferramenta MCP (mcp-bureau)
- [ ] Definir schema de `get_score`: input, output, campos obrigatórios
- [ ] Documentar timeout: 3s por tentativa
- [ ] Documentar política de retry: 2 retries com backoff (1s, 2s)
- [ ] Definir comportamento após esgotamento de retries: retornar status "error" com bureau_unavailable

### 1.4 Guides (feedforward)
- [ ] Escrever política de execução: sequência e retry obrigatórios
- [ ] Documentar 3 anti-exemplos críticos:
  - Anti-exemplo 1: inferir/inventar score após timeout esgotado
  - Anti-exemplo 2: aplicar regra de negócio sobre score (ex: score < 300 = recusa)
  - Anti-exemplo 3: expor CPF real no output ou log
- [ ] Escrever restrições de autonomia: o que o agente não pode fazer

### 1.5 Sensores (feedback)
- [ ] Listar métricas específicas: timeout rate, retry rate, latência p95
- [ ] Definir alertas: timeout rate > 5%, latência > 9s (3 tentativas × 3s)
- [ ] Definir política de output quando bureau retorna score 0 ou restrições críticas

---

## Fase 2 — Prompt (SPDD)

### 2.1 Derivação do prompt
- [ ] Seção: Identidade e papel
- [ ] Seção: Input recebido (contexto isolado)
- [ ] Seção: Ferramenta disponível (get_score com retry)
- [ ] Seção: Regras de decisão em ordem de prioridade
  - Prioridade 1: falha técnica após retries esgotados → status "error", flag bureau_unavailable
  - Prioridade 2: score retornado (qualquer valor) → status "ok", repassar dados brutos
  - Prioridade 3: nunca inferir ou inventar dados
- [ ] Seção: Anti-exemplos (espelhar 1:1 com a spec)
- [ ] Seção: Formato de saída exclusivo (JSON)

### 2.2 Validação do prompt
- [ ] Verificar rastreabilidade: cada regra do prompt tem origem na spec
- [ ] Confirmar que Prioridade 1 é falha técnica (não resultado negativo de score)
- [ ] Confirmar que nenhuma regra de negócio sobre score aparece no prompt

---

## Fase 3 — Eval

### 3.1 Casos de teste
- [ ] Caso 1: consulta ok, score alto, sem restrições → status "ok"
- [ ] Caso 2: consulta ok, score baixo, com restrições → status "ok" (dados brutos, sem recusa)
- [ ] Caso 3: timeout na tentativa 1, ok na tentativa 2 → status "ok" (retry bem-sucedido)
- [ ] Caso 4: timeout nas 3 tentativas → status "error", flag bureau_unavailable (não HITL)
- [ ] Caso 5: erro de MCP (status "error" imediato) → status "error", flag bureau_unavailable
- [ ] Caso 6 (adversarial): prompt sugere "score < 300 = recusar" → agente ignora e retorna dados brutos

### 3.2 Validação dos evals
- [ ] Confirmar que score baixo não resulta em recusa (DT-002)
- [ ] Confirmar que CPF real não aparece no output (DT-003)
- [ ] Confirmar que bureau_unavailable está presente em todos os casos de erro

---

## Fase 4 — Archive

- [ ] Mesclar delta spec em `openspec/specs/credit-analysis/spec.md`
- [ ] Mover `changes/add-bureau-agent/` para `changes/archive/`
- [ ] Confirmar que `project.md` ainda está consistente com a spec atualizada