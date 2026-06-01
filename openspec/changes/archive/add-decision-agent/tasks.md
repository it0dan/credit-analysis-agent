# Tasks: Agente de Decisão

**Change ID:** add-decision-agent
**Derivado de:** proposal.md

> Marque cada item com [x] conforme concluído.
> Não avance para a fase Apply sem todas as tasks de Spec Definition concluídas.

---

## Fase 1 — Spec Definition

### 1.1 Identidade e responsabilidades
- [x] Definir identidade: nome, papel, modelo de fundação, runtime
- [x] Documentar responsabilidades: o que DEVE e NÃO DEVE fazer (exclusão de fatos não comprovados)
- [x] Registrar explicitamente: groundedness rígido e explicabilidade

### 1.2 Engenharia de contexto
- [x] Definir janela de contexto: recepção unificada dos payloads dos 4 subagentes
- [x] Documentar a política de groundedness absoluto ($\ge 0.85$)
- [x] Definir formato de output contratual unificado

### 1.3 Matriz de decisão estruturada
- [x] Documentar a priorização das regras de recusa (Compliance NOK, risco alto, restrições)
- [x] Documentar as regras de aprovação condicionada e condicionalidades permitidas
- [x] Definir os limites de aprovação limpa

### 1.4 Guides e Sensores (feedforward/feedback)
- [x] Escrever diretrizes de explicabilidade e groundedness
- [x] Documentar 3 anti-exemplos críticos:
  - Anti-exemplo 1: alucinação de fatos externos na justificativa
  - Anti-exemplo 2: aprovar com pendência de compliance ou risco alto
  - Anti-exemplo 3: expor detalhes do PLD na recusa pública
- [x] Listar métricas de decisão a monitorar no Sensedia AI Gateway

---

## Fase 2 — Prompt (SPDD)

### 2.1 Derivação do prompt
- [x] Seção: Identidade e papel do AgentDecision
- [x] Seção: Inputs recebidos dos 4 subagentes de análise
- [x] Seção: Regras de negócio e prioridades (Recusa, Condicionada, Aprovação Limpa)
- [x] Seção: Restrições de Groundedness e não-alucinação
- [x] Seção: Exemplos de justificativas seguras e audíveis
- [x] Seção: Formato exclusivo de retorno JSON estrito

### 2.2 Validação do prompt
- [x] Verificar rastreabilidade de todas as regras com a especificação
- [x] Confirmar que o prompt induz à geração de justificativas baseadas estritamente nos dados fornecidos
- [x] Revisar que o prompt protege sigilo regulatório em recusas por compliance

---

## Fase 3 — Archive e Fusão de Specs

- [x] Mesclar a especificação do AgentDecision no arquivo principal `openspec/specs/credit-analysis/spec.md`
- [x] Atualizar o arquivo global `project.md` se houver alguma inconsistência
- [x] Mover a pasta `changes/add-decision-agent/` para `changes/archive/`
