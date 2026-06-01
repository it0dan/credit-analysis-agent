# Design: Agente de Decisão

**Change ID:** add-decision-agent
**Status:** ACCEPTED
**Autor:** Danilo Amaral
**Data:** 2026-05-29

---

## Contexto

O **AgentDecision** executa a **Etapa 5** do fluxo do orquestrador. Ele atua como o juiz final do sistema. Sua função é consolidar todas as perspectivas levantadas pelos subagentes especializados e formular um veredito de crédito estruturado e fundamentado.

Este documento estabelece as diretrizes de design técnico aplicáveis à modelagem do AgentDecision.

---

## Diagrama C4 — Nível de Componente

```
┌──────────────────────────────────────────────────────────────────┐
│  Sistema de Análise de Crédito [Container: Sensedia AI Gateway]  │
│                                                                  │
│  AgentOrchestrator ──A2A: decision.synthesize──▶ AgentDecision  │
│                                                     │            │
│  ┌──────────────────────────────────────────────────┼───────┐    │
│  │  AgentDecision [Component]                       │       │    │
│  │                                                  ▼       │    │
│  │  ┌──────────────┐   ┌─────────────────────────────────┐  │    │
│  │  │ Context      │   │ Synthesizer Engine (LLM)        │  │    │
│  │  │ Receiver     │   │                                 │  │    │
│  │  │ (valida e    │   │  Aplica regras de negócio,      │  │    │
│  │  │  consolida)  │   │  garante groundedness >= 0.85   │  │    │
│  │  └──────┬───────┘   └─────────────┬───────────────────┘  │    │
│  │         └─────────────────────────┘                      │    │
│  │                        │                                 │    │
│  │             ┌──────────┴──────────┐                      │    │
│  │             ▼                     ▼                      │    │
│  │       [status: "ok"]       [status: "error"]             │    │
│  │       emite veredito       escalabilidade HITL           │    │
│  │       (justificativa)      (decision_unavailable)        │    │
│  │                                                          │    │
│  └──────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────┘
```

---

## Decisões Técnicas deste Change

### DT-001 — Groundedness Absoluto ($\ge 0.85$)

**Problema:** LLMs de uso geral tendem a inventar motivos ou alucinar critérios de recusa ou aprovação que não constam nas políticas ou nos relatórios de entrada (ex: "solicitante tem histórico de bom relacionamento com o banco" — informação que o agente sequer recebeu).

**Decisão:** Restrição rígida de Groundedness no prompt e na validação da trajetória. O AgentDecision é proibido de usar qualquer fato ou informação que não esteja explicitamente presente nos payloads dos subagentes (`bureau_result`, `documents_result`, `risk_result`, `compliance_result`).

**Razão:**
- Evita alucinações comerciais ou legais.
- Assegura auditoria precisa de auditorias regulatórias: se um crédito foi recusado, o motivo da recusa deve ser 100% rastreável a um dado bruto verificado nas etapas anteriores.

**Consequência:**
- O sensor de Groundedness do Gateway é calibrado para disparar alerta vermelho se o score cair abaixo de 0.85.
- O prompt do agente contém uma seção explícita detalhando que fatos não citados nos relatórios são classificados como violação grave de diretriz.

---

### DT-002 — Tratamento de Condicionalidades (Aprovado com Condições)

**Problema:** Em cenários de risco médio (ex: score de bureau razoável mas renda comprometida perto do limite), recusar sumariamente gera perda de negócios, enquanto aprovar gera risco de crédito elevado.

**Decisão:** O AgentDecision poderá emitir o status `adjusted` (ou `approved` com condições estruturadas no array `conditions`). As condicionalidades permitidas são limitadas a:
1.  `docs_unverified`: "Apresentar comprovante de residência atualizado em até 30 dias".
2.  `medium_risk`: "Redução de limite em 20% ou inclusão de co-titular com renda comprovada".
3.  `identity_warning`: "Apresentação física do documento de identidade na agência".

**Razão:**
- Dá flexibilidade comercial ao sistema mantendo o controle de risco.
- Estrutura as condições em formato legível por sistemas automatizados (Core Bancário).

**Consequência:**
- O schema contratual inclui obrigatoriamente o campo `conditions` como um array de strings.

---

## Formato de Saída Contratual A2A

```json
{
  "request_id": "string (UUID)",
  "decision": "enum: approved | rejected | adjusted",
  "confidence": "number (0.00–1.00)",
  "justification": "string (máx 300 caracteres, justificativa explicável baseada estritamente nos relatórios)",
  "conditions": "string[] (condições atreladas à aprovação, ex: ['comprovante de endereço atualizado'])",
  "status": "enum: ok | error",
  "reason": "string (nulo ou erro técnico em caso de falha de processamento)",
  "processing_time_ms": "number"
}
```
