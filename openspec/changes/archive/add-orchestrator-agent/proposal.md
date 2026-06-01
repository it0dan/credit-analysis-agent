# Proposal: Agente Orquestrador de Análise de Crédito

**Change ID:** add-orchestrator-agent
**Status:** PROPOSED
**Autor:** Danilo Amaral
**Data:** 2026-05-25

---

## Motivação

O sistema de análise de crédito requer um agente central capaz de receber solicitações,
planejar a sequência de análise, delegar tarefas aos sub-agentes via A2A, consolidar
resultados e aplicar o threshold de HITL antes de emitir a decisão final.

Sem o Agente Orquestrador, não há coordenação entre os domínios de bureau, documentos,
risco, compliance e decisão — cada sub-agente operaria de forma isolada sem contexto
compartilhado ou sequência garantida.

---

## Escopo da Mudança

### Incluído
- Definição completa do Agente Orquestrador: identidade, responsabilidades e limites
- Engenharia de contexto: quais informações chegam, como são selecionadas e comprimidas
- Memória: tipos utilizados (semântica, episódica, procedural) e quando cada uma é acionada
- Plano de delegação A2A: sequência de chamadas aos sub-agentes e política de retentativas
- Lógica de threshold HITL: critério de R$ 50.000 e handoff para analista humano
- Guides do orquestrador: políticas de execução, restrições e anti-exemplos
- Sensores do orquestrador: o que é monitorado na trajetória deste agente
- Spec da ferramenta `handoff_to_human` (MCP) acionada no fluxo HITL

### Excluído (escopo de outros proposals)
- Implementação interna de cada sub-agente (cada um terá seu próprio proposal)
- Configuração dos MCP Servers individuais
- Configuração do Sensedia AI Gateway
- Eval suite (será um proposal separado após todos os agentes estarem especificados)

---

## Design de Alto Nível

```
Solicitação de crédito
        │
        ▼
┌─────────────────────────────┐
│     AgentOrchestrator       │
│                             │
│  1. Carregar contexto       │  ← memória semântica + episódica do cliente
│  2. Planejar sequência      │  ← memória procedural (políticas)
│  3. Delegar via A2A         │  → AgentBureau → AgentDocuments →
│                             │    AgentRisk → AgentCompliance
│  4. Consolidar resultados   │  ← AgentDecision
│  5. Avaliar threshold       │
│     ≤ R$50k → auto          │  → resposta direta
│     > R$50k → HITL          │  → handoff_to_human (MCP)
└─────────────────────────────┘
```

### Sequência de Delegação A2A

O orquestrador segue esta sequência fixa, sem paralelismo na v1:

1. `bureau.get_score` — score e restrições no Serasa/SPC
2. `documents.validate` — validação de identidade e comprovantes
3. `risk.evaluate` — score interno e probabilidade de default
4. `compliance.check` — KYC, PLD e LGPD
5. `decision.synthesize` — decisão final com explicabilidade

> **Decisão arquitetural (ADR-001):** Sequência serial na v1 para garantir
> rastreabilidade completa. Paralelismo de bureau + documentos será avaliado
> na v2 após validação dos SLOs.

---

## Impacto em Specs Existentes

| Spec                        | Tipo de impacto | Descrição                                    |
|-----------------------------|-----------------|----------------------------------------------|
| `credit-analysis/spec.md`   | ADDED           | Primeira spec do sistema — criada do zero    |

---

## Tarefas de Implementação

Ver `tasks.md` para checklist atômico.

---

## Critérios de Aceite deste Proposal

- [ ] Spec do Agente Orquestrador revisada e aprovada pelo time
- [ ] ADR-001 (serial vs paralelo) documentado e aceito
- [ ] Ferramenta `handoff_to_human` com schema completo e validado
- [ ] Guides do orquestrador cobrindo pelo menos 3 anti-exemplos críticos
- [ ] Prompt derivado da spec (SPDD) com todos os campos obrigatórios preenchidos
- [ ] Eval mínimo: 1 caso aprovação automática, 1 caso HITL, 1 caso recusa por compliance
