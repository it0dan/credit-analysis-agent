# Design: Agente de Compliance

**Change ID:** add-compliance-agent
**Status:** ACCEPTED
**Autor:** Danilo Amaral
**Data:** 2026-05-26

---

## Contexto

O AgentCompliance executa a Etapa 4 da sequência A2A do orquestrador.
É o sub-agente de maior criticidade regulatória do sistema: verifica KYC,
PLD e consentimento LGPD antes de qualquer decisão de crédito.

Este documento registra as decisões técnicas específicas deste agente.
Decisões de escopo sistêmico já estão em ADR-001 e ADR-002.

---

## Diagrama C4 — Nível de Componente

```
┌──────────────────────────────────────────────────────────────────┐
│  Sistema de Análise de Crédito [Container: Sensedia AI Gateway]  │
│                                                                  │
│  AgentOrchestrator ──A2A: compliance.check──▶ AgentCompliance   │
│                                               │                  │
│  ┌────────────────────────────────────────────┼──────────────┐  │
│  │  AgentCompliance [Component]               │              │  │
│  │                                            ▼              │  │
│  │  ┌──────────────┐   ┌──────────────────────────────────┐  │  │
│  │  │ Context      │   │ Compliance Evaluator             │  │  │
│  │  │ Receiver     │   │                                  │  │  │
│  │  │ (valida e    │   │  verify_kyc ──▶ check_pld ──▶    │  │  │
│  │  │  isola input)│   │  verify_lgpd_consent             │  │  │
│  │  └──────┬───────┘   └──────────────┬───────────────────┘  │  │
│  │         └──────────────────────────┘                       │  │
│  │                         │                                  │  │
│  │              ┌──────────┴──────────┐                       │  │
│  │              ▼                     ▼                       │  │
│  │        [approved: true]    [rejected: true]                │  │
│  │        status: "ok"        status: "rejected"              │  │
│  │                            (sem fallback, sem HITL)        │  │
│  └────────────────────────────────────────────────────────────┘  │
│                    │ MCP                                          │
│                    ▼                                             │
│             [mcp-kyc server]                                     │
│      (KYC bureau / COAF / LGPD registry)                         │
└──────────────────────────────────────────────────────────────────┘
```

---

## Decisões Técnicas deste Change

### DT-001 — Recusa imediata vs escalada para HITL em falhas

**Problema:** Todos os outros sub-agentes escalam para HITL em caso de erro ou timeout.
O AgentCompliance deve ter comportamento diferente?

**Decisão:** Recusa imediata em qualquer falha, sem exceção.

**Razão:**
- Compliance é requisito regulatório (KYC, PLD/COAF, LGPD). Operar sem essa
  verificação expõe a instituição a risco legal, não apenas operacional.
- HITL com analista humano não substitui a verificação técnica de compliance —
  o analista não tem acesso aos sistemas KYC/PLD em tempo real.
- Um analista aprovando um crédito com compliance não verificado cria
  responsabilidade legal para a instituição.
- A política é intencional e conservadora: melhor recusar um crédito legítimo
  por falha técnica do que aprovar um crédito com risco regulatório.

**Consequência:**
- O prompt do AgentCompliance tem Prioridade 1 absoluta: qualquer status diferente
  de "ok" retorna `rejected: true` imediatamente.
- O orquestrador trata status "error" e "timeout" do compliance igual a
  `kyc_approved: false` — ambos resultam em recusa imediata.
- Disponibilidade do `mcp-kyc` é crítica: SLO de disponibilidade deve ser
  monitorado com alerta de alta prioridade.

---

### DT-002 — Sequência interna das verificações KYC → PLD → LGPD

**Problema:** As três verificações (KYC, PLD, LGPD) são independentes entre si
no `mcp-kyc`. Qual a ordem de execução interna?

**Decisão:** Sequência serial: `verify_kyc` → `check_pld` → `verify_lgpd_consent`,
com short-circuit: se qualquer verificação falhar, parar imediatamente sem
chamar as próximas.

**Razão:**
- KYC é a verificação mais básica (identidade). Se o KYC falhar, as demais
  são irrelevantes — não há sentido em verificar PLD de alguém não identificado.
- Short-circuit reduz chamadas desnecessárias ao `mcp-kyc` em casos de recusa.
- PLD antes de LGPD: verificação de lavagem de dinheiro tem precedência sobre
  consentimento de dados — PLD positivo é recusa independente de LGPD.

**Consequência:**
- O prompt do AgentCompliance instrui a chamar `verify_kyc` primeiro.
- Se `kyc_approved: false`, retornar imediatamente sem chamar `check_pld`.
- Se `pld_clear: false`, retornar imediatamente sem chamar `verify_lgpd_consent`.
- O campo `reason` no output indica qual verificação falhou primeiro.

---

### DT-003 — Isolamento de contexto: o que o AgentCompliance recebe

**Problema:** O orquestrador acumula resultados de bureau, documentos e risco
antes de chamar o compliance. O AgentCompliance deve receber esses dados?

**Decisão:** Não. O AgentCompliance recebe apenas `applicant_masked_cpf` e
`request_id` — nada dos resultados anteriores.

**Razão:**
- Compliance é uma verificação independente de score e risco.
  O resultado do KYC/PLD não deve ser influenciado pelo score de bureau ou
  pela renda confirmada — isso criaria viés regulatório.
- Princípio de isolamento de contexto: sub-agente recebe apenas
  o mínimo necessário para sua função.
- Reduz custo de tokens e elimina risco de o modelo usar dados de risco
  para "suavizar" uma decisão de compliance.

**Consequência:**
- O input contratual do AgentCompliance é estritamente
  `{ applicant_masked_cpf, request_id }`.
- O AgentCompliance não sabe o valor solicitado, o score de bureau ou
  o resultado do AgentRisk — e não precisa saber.

---

## Suposições

- O `mcp-kyc` agrupa as três ferramentas (KYC, PLD, LGPD) em um único servidor MCP.
- Os sistemas externos de KYC/PLD estão disponíveis via `mcp-kyc` — falha do
  servidor MCP é tratada como falha de compliance (recusa imediata).
- O consentimento LGPD foi coletado no canal de origem antes da solicitação chegar
  ao sistema. O `verify_lgpd_consent` confirma o registro desse consentimento.

---

## Perguntas em Aberto

- [x] Qual o comportamento quando `lgpd_consent: false` mas KYC e PLD estão ok?
      **Decisão (2026-05-26):** Recusa imediata. Sem consentimento registrado não
      há base legal para processar dados pessoais (Art. 7º, LGPD). Não escala
      para HITL nem para DPO — o canal de origem é responsável por coletar o
      consentimento antes de submeter a solicitação.

- [x] O `reason` de recusa deve ser exposto ao solicitante ou apenas ao trace interno?
      **Decisão (2026-05-26):** Apenas interno. O campo `reason` trafega no trace
      do Sensedia AI Gateway e nos logs de auditoria. O orquestrador mapeia qualquer
      recusa de compliance para mensagem genérica ao solicitante ("Solicitação não
      aprovada por critérios regulatórios"). Razões de PLD são protegidas por
      sigilo regulatório e não podem ser expostas ao solicitante.

---

## Decisões Arquiteturais Referenciadas

| ADR | Título | Aplicação neste agente |
|-----|--------|------------------------|
| ADR-001 | Sequência serial vs paralelo | Serial interno: KYC → PLD → LGPD com short-circuit |
| ADR-002 | A2A vs chamada direta MCP | AgentCompliance gerencia seu próprio `mcp-kyc` |
