# Proposal: Agente de Decisão

**Change ID:** add-decision-agent
**Status:** PROPOSED
**Autor:** Danilo Amaral
**Data:** 2026-05-29

---

## Motivação

O **AgentDecision (Agente de Decisão)** é a camada sintética final do sistema de análise de crédito. Ele executa a **Etapa 5** da sequência A2A do orquestrador, sendo responsável por ler todos os relatórios gerados pelos subagentes (`AgentBureau`, `AgentDocuments`, `AgentRisk`, `AgentCompliance`), correlacionar as informações contra as regras de negócio e emitir a decisão final estruturada acompanhada de uma justificativa clara, audível e explicável (explicabilidade).

Sem a especificação formal do AgentDecision:
1. O veredito final carece de regras de groundedness estruturadas, gerando riscos de alucinação do LLM ao consolidar relatórios.
2. A política de concessão de crédito sob condições (ex: solicitar documentos adicionais em caso de risco médio) não está formalizada em contratos.
3. Não há alinhamento sobre as métricas de explicabilidade e calibragem do score de confiança da decisão.

---

## Escopo da Mudança

### Incluído
- Identidade e responsabilidades do **AgentDecision**.
- Engenharia de contexto: janela de contexto consolidada com dados dos quatro subagentes de análise.
- Regras de negócio determinísticas para vereditos: aprovação, recusa estruturada e aprovação condicionada.
- Guides: políticas de explicabilidade, prevenção de alucinações e GROUNDEDNESS $\ge$ 0.85.
- Sensores de qualidade de decisão e alertas de anomalia (como LLM-as-judge para explicabilidade).
- Formato de saída contratual A2A (consumido pelo orquestrador e repassado para o canal de entrada/HITL).
- Prompt derivado da especificação (SPDD) para o AgentDecision.

### Excluído
- Ação de persistência da decisão no banco de dados central (responsabilidade do Core Bancário via MCP orquestrado).
- O fluxo de Handoff Humano em si (HITL é disparado pelo `AgentOrchestrator` baseando-se no valor ou nos fallbacks, e não pelo `AgentDecision`).

---

## Design de Alto Nível

```
AgentOrchestrator
        │ A2A: decision.synthesize
        │ Input: { bureau_result, documents_result, risk_result,
        │          compliance_result, requested_amount, request_id }
        ▼
┌─────────────────────────────────┐
│         AgentDecision           │
│                                 │
│  1. Receber relatórios A2A      │  ← Consolida os 4 subagentes
│  2. Validar conformidade        │  ← Se Compliance NOK, recusa imediata
│  3. Aplicar matriz de decisão   │  ← Risco vs. Renda vs. Bureau
│  4. Gerar justificativa         │  → Explicabilidade baseada em fatos
└─────────────────────────────────┘
        │ Output: { decision, confidence, justification, conditions[] }
        ▼
AgentOrchestrator
  → Se status: "error" ou "timeout" → Escala para HITL (flag: decision_unavailable)
  → Se status: "ok"                  → Finaliza a análise de crédito
```

---

## Matriz de Decisão Referencial (Guides)

| Risco (Risk Tier) | Bureau Score | Conformidade (Compliance) | Renda Comprovada | Veredito Esperado |
|---|---|---|---|---|
| **Low** | $\ge 700$ | Aprovado | Suficiente | **Aprovado (Approved)** |
| **Medium** | $400$ a $699$ | Aprovado | Suficiente | **Aprovado com Condições (Adjusted)** |
| **High** | Qualquer | Qualquer | Qualquer | **Recusado (Rejected)** |
| Qualquer | Qualquer | **Reprovado** | Qualquer | **Recusado (Rejected) - Compliance** |

---

## Impacto em Specs Existentes

| Spec | Tipo de impacto | Descrição |
|---|---|---|
| `credit-analysis/spec.md` | ADDED | Integração do novo sub-agente: AgentDecision e definição do payload da Etapa 5 de A2A. |

---

## Tarefas de Implementação

Ver `tasks.md` para o checklist atômico de execução.

---

## Critérios de Aceite deste Proposal

- [ ] Especificação do **AgentDecision** revisada e aprovada pelo usuário.
- [ ] Matriz de decisão estruturada cruzando risco, bureau e renda devidamente documentada.
- [ ] Regras de groundedness ($\ge 0.85$) especificadas para evitar alucinações nas justificativas.
- [ ] Payload contratual consolidado e compatível com o orquestrador atual.
- [ ] Prompt SPDD do AgentDecision gerado contendo exemplos de justificativas para aprovação e recusa.
- [ ] Evals mínimos validados: aprovação limpa, recusa por compliance, aprovação sob condição, e recusa por alto risco.
