# Design: Agente de Bureau de Crédito

**Change ID:** add-bureau-agent
**Status:** ACCEPTED
**Autor:** Danilo Amaral
**Data:** 2026-05-28

---

## Contexto

O AgentBureau executa a Etapa 1 da sequência A2A do orquestrador.
É o ponto de entrada dos dados externos de crédito — sem ele, AgentRisk
não tem score de bureau e o fluxo não pode avançar.

Este documento registra as decisões técnicas específicas deste agente.
Decisões de escopo sistêmico já estão em ADR-001 e ADR-002.

---

## Diagrama C4 — Nível de Componente

```
┌──────────────────────────────────────────────────────────────────┐
│  Sistema de Análise de Crédito [Container: Sensedia AI Gateway]  │
│                                                                  │
│  AgentOrchestrator ──A2A: bureau.get_score──▶ AgentBureau       │
│                                               │                  │
│  ┌────────────────────────────────────────────┼──────────────┐  │
│  │  AgentBureau [Component]                   │              │  │
│  │                                            ▼              │  │
│  │  ┌──────────────┐   ┌────────────────────────────────┐   │  │
│  │  │ Context      │   │ Bureau Evaluator               │   │  │
│  │  │ Receiver     │   │                                │   │  │
│  │  │ (valida e    │   │  get_score ──▶ parse result    │   │  │
│  │  │  isola input)│   │  retry logic (max 2x backoff)  │   │  │
│  │  └──────┬───────┘   └──────────────┬─────────────────┘   │  │
│  │         └──────────────────────────┘                      │  │
│  │                         │                                  │  │
│  │         ┌───────────────┴──────────────┐                  │  │
│  │         ▼                              ▼                   │  │
│  │   [status: "ok"]              [status: "error"]            │  │
│  │   score + restrictions        bureau_unavailable           │  │
│  └────────────────────────────────────────────────────────────┘  │
│                    │ MCP                                          │
│                    ▼                                             │
│             [mcp-bureau server]                                  │
│             (Serasa / SPC / Open Finance)                        │
└──────────────────────────────────────────────────────────────────┘
```

---

## Decisões Técnicas deste Change

### DT-001 — Retry com backoff vs retry imediato

**Problema:** Timeouts de bureau são frequentemente transientes (sobrecarga
momentânea do Serasa/SPC). Escalar para HITL na primeira falha geraria ruído
excessivo para os analistas humanos.

**Decisão:** 2 retries com exponential backoff (1s, 2s) antes de retornar erro.
Total de até 3 tentativas (1 original + 2 retries) com timeout de 3s cada.

**Razão:**
- P99 de timeouts transientes de bureaus brasileiros é tipicamente < 5s
- 2 retries com backoff cobrem a maioria dos casos transientes sem impactar
  o SLO de 8s do orquestrador (3s × 3 tentativas + 3s de backoff = 12s worst case)
- Zero retries (política do compliance) seria conservador demais para bureau —
  bureau não é risco regulatório, é disponibilidade operacional

**Consequência:**
- No pior caso (3 timeouts de 3s + 3s backoff), o AgentBureau consome ~12s,
  pressionando o SLO de 8s. Esse tradeoff é aceitável: bureau indisponível
  por 12s vai para HITL de qualquer forma.
- O prompt do AgentBureau instrui a executar o retry internamente antes de
  retornar `status: "error"` ao orquestrador.

---

### DT-002 — Score mínimo: AgentBureau decide ou apenas repassa?

**Problema:** O AgentBureau deve aplicar regras de negócio (ex: score < 300
= recusa imediata) ou apenas repassar os dados brutos do bureau?

**Decisão:** AgentBureau apenas repassa dados brutos. Nenhuma regra de
negócio sobre score é aplicada aqui.

**Razão:**
- Regras de score são responsabilidade do AgentRisk (modelo interno) e do
  AgentDecision (síntese final)
- AgentBureau não tem contexto de valor solicitado, renda ou histórico —
  sem esse contexto, qualquer decisão baseada só no score seria incompleta
- Separação de responsabilidades: bureau = dados, risco = avaliação

**Consequência:**
- AgentBureau retorna sempre `status: "ok"` se a consulta funcionou,
  independente do score retornado (mesmo score 0 ou restrições ativas)
- O orquestrador e AgentRisk são responsáveis por interpretar os dados

---

### DT-003 — Mascaramento de CPF na chamada ao mcp-bureau

**Problema:** O `mcp-bureau` (Serasa/SPC) requer CPF real para consulta.
O AgentBureau recebe CPF mascarado do orquestrador. Como resolver?

**Decisão:** O `mcp-bureau` é responsável por fazer o de-mascaramento.
O AgentBureau passa o CPF mascarado ao MCP Server, que internamente
tem acesso ao CPF real via vault/key management — fora do escopo do agente.

**Razão:**
- O AgentBureau nunca deve ter acesso ao CPF real — princípio do menor privilégio
- O de-mascaramento é responsabilidade da infraestrutura (MCP Server),
  não da lógica do agente
- Isso mantém o contrato de isolamento de contexto da palestra

**Consequência:**
- O schema do `mcp-bureau` recebe `applicant_masked_cpf` como input
- O MCP Server resolve o CPF real internamente via `request_id` + vault
- Logs e traces do agente nunca expõem CPF real

---

## Perguntas em Aberto

Todas as perguntas foram resolvidas durante o design. Nenhuma pendência.

---

## Decisões Arquiteturais Referenciadas

| ADR | Título | Aplicação neste agente |
|-----|--------|------------------------|
| ADR-001 | Sequência serial vs paralelo | AgentBureau é Etapa 1 — sem dependência de outros agentes |
| ADR-002 | A2A vs chamada direta MCP | AgentBureau gerencia seu próprio `mcp-bureau` |