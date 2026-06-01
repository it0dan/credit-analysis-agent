# Tasks: Agente Orquestrador de Análise de Crédito

**Change ID:** add-orchestrator-agent
**Derivado de:** proposal.md

> Marque cada item com [x] conforme concluído.
> Não avance para a fase Apply sem todas as tasks de Spec Definition concluídas.

---

## Fase 1 — Spec Definition

### 1.1 Source of Truth: spec do sistema
- [ ] Criar `openspec/specs/credit-analysis/spec.md` com identidade e objetivo do sistema
- [ ] Documentar os 6 atores (orquestrador + 5 sub-agentes) e o ator humano (HITL)
- [ ] Documentar os fluxos principais: aprovação automática, HITL, recusa por compliance

### 1.2 Spec do Agente Orquestrador
- [ ] Definir identidade: nome, papel, modelo de fundação, runtime
- [ ] Definir janela de contexto: o que entra, tamanho máximo, política de compressão
- [ ] Especificar os 3 tipos de memória e quando cada um é acionado
- [ ] Documentar a sequência A2A (5 etapas) com inputs e outputs esperados de cada sub-agente
- [ ] Definir política de retentativa: max 2 tentativas por sub-agente, fallback para HITL
- [ ] Definir lógica de threshold: critério R$ 50.000 e condições de exceção

### 1.3 Spec da ferramenta HITL
- [ ] Definir schema da ferramenta `handoff_to_human`
  - Input: `request_id`, `applicant_masked_cpf`, `amount`, `analysis_summary`, `reason`
  - Output: `status` (pending | approved | rejected | adjusted), `analyst_id`, `notes`
- [ ] Documentar SLA de resposta do analista: 4h em horário comercial
- [ ] Definir comportamento do orquestrador enquanto aguarda resposta HITL

### 1.4 Guides do orquestrador (feedforward)
- [ ] Escrever política de execução: nunca emitir decisão sem os 4 sub-agentes anteriores
- [ ] Escrever critério de aceite de cada sub-agente (o que constitui resposta válida)
- [ ] Documentar 3 anti-exemplos críticos:
  - Anti-exemplo 1: orquestrador decidindo sem aguardar AgentCompliance
  - Anti-exemplo 2: orquestrador inventando score quando bureau retorna erro
  - Anti-exemplo 3: orquestrador aprovando acima do threshold sem acionar HITL
- [ ] Escrever restrições de autonomia: o que o orquestrador pode e não pode fazer sozinho

### 1.5 Sensores do orquestrador (feedback)
- [ ] Listar métricas monitoradas: latência total, tool success rate, groundedness
- [ ] Definir alertas: latência > 8s, tool failure no compliance, groundedness < 0.85
- [ ] Definir comportamento em caso de falha de sub-agente: retry, fallback, escala humana

---

## Fase 2 — ADR

### 2.1 ADR-001: Sequência serial vs paralelo
- [ ] Registrar contexto da decisão: por que serial na v1
- [ ] Documentar alternativa avaliada: paralelismo bureau + documentos
- [ ] Registrar consequências: rastreabilidade garantida, latência ~3s acima do ideal
- [ ] Registrar critério de revisão: após 30 dias de dados de SLO em produção

---

## Fase 3 — SPDD (derivação do prompt)

### 3.1 Prompt do Agente Orquestrador
- [ ] Seção: Identidade e papel
- [ ] Seção: Contexto que o agente recebe ao iniciar
- [ ] Seção: Ferramentas disponíveis (lista de chamadas A2A + handoff_to_human)
- [ ] Seção: Guides — políticas de execução e restrições
- [ ] Seção: Exemplos positivos (1 aprovação automática, 1 HITL)
- [ ] Seção: Anti-exemplos (os 3 documentados na spec)
- [ ] Seção: Formato de saída esperado (JSON com decisão + justificativa + trace_id)

### 3.2 Validação do prompt
- [ ] Verificar que cada campo do prompt tem origem rastreável na spec
- [ ] Confirmar que os anti-exemplos do prompt espelham os da spec (1:1)
- [ ] Revisar restrições: nenhuma restrição no prompt que não esteja na spec

---

## Fase 4 — Eval mínimo

- [ ] Caso 1: Solicitação R$ 20.000, todos sub-agentes retornam OK → aprovação automática
- [ ] Caso 2: Solicitação R$ 80.000, todos sub-agentes retornam OK → HITL acionado
- [ ] Caso 3: Solicitação R$ 10.000, AgentCompliance retorna restrição PLD → recusa imediata
- [ ] Caso 4: AgentBureau retorna erro → retry, segunda falha → fallback HITL com flag de erro
- [ ] Verificar groundedness >= 0.85 em todos os casos de aprovação e recusa

---

## Fase 5 — Archive

- [ ] Mesclar delta spec em `openspec/specs/credit-analysis/spec.md`
- [ ] Mover `changes/add-orchestrator-agent/` para `changes/archive/`
- [ ] Confirmar que `project.md` ainda está consistente com a spec atualizada
