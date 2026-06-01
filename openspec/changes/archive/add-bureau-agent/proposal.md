# Proposal: Agente de Bureau de Crédito

**Change ID:** add-bureau-agent
**Status:** PROPOSED
**Autor:** Danilo Amaral
**Data:** 2026-05-28

---

## Motivação

O AgentBureau executa a Etapa 1 da sequência A2A do orquestrador — a primeira
chamada após receber a solicitação de crédito. Ele consulta bureaus externos
(Serasa/SPC) e retorna score, restrições ativas e status da consulta.

Sem o AgentBureau especificado, o orquestrador não tem contrato claro para a
Etapa 1, e os cenários `bureau_error` e `multi_error` do walking skeleton
simulam um comportamento sem spec formal.

O AgentBureau é o único sub-agente com **política de retry explícita**: 2
tentativas antes de escalar para HITL com flag `bureau_unavailable`. Essa
política já está refletida no prompt do orquestrador e nos evals, mas precisa
ser documentada formalmente no sub-agente.

---

## Escopo da Mudança

### Incluído
- Identidade e responsabilidades do AgentBureau
- Engenharia de contexto: o que recebe do orquestrador, o que retorna
- Ferramenta MCP: `mcp-bureau` — schema de input/output, timeout, retry
- Política de retry: 2 tentativas com backoff antes de retornar erro
- Guides: políticas de execução, restrições e anti-exemplos
- Sensores: métricas e alertas específicos do bureau
- Formato de saída contratual (consumido pelo orquestrador e pelo AgentRisk)
- Prompt derivado da spec (SPDD)
- Eval suite

### Excluído
- Implementação interna do `mcp-bureau` (MCP Server dedicado)
- Integração real com Serasa/SPC (APIs externas)
- Configuração do Sensedia AI Gateway para este agente

---

## Design de Alto Nível

```
AgentOrchestrator
        │ A2A: bureau.get_score
        │ Input: { applicant_masked_cpf, request_id }
        ▼
┌──────────────────────────────────────┐
│           AgentBureau                │
│                                      │
│  1. Receber contexto isolado         │  ← CPF mascarado + request_id
│  2. Chamar mcp-bureau.get_score      │  → Serasa/SPC
│     Timeout: 3s | Retries: 2        │
│  3. Avaliar resultado                │
│     score + restrictions: ok        │  → retornar status: "ok"
│     erro/timeout (tentativa 1)      │  → retry com backoff 1s
│     erro/timeout (tentativa 2)      │  → retry com backoff 2s
│     erro/timeout (tentativa 3)      │  → retornar status: "error"
│                                      │     flag: bureau_unavailable
└──────────────────────────────────────┘
        │ Output: { score, restrictions[], status, reason? }
        ▼
AgentOrchestrator
  → se status: "ok"    → continuar para AgentDocuments
  → se status: "error" → HITL com flag bureau_unavailable
```

---

## Diferencial em relação aos demais sub-agentes

| Característica         | AgentCompliance              | AgentBureau                      |
|------------------------|------------------------------|----------------------------------|
| Falha/timeout          | Recusa imediata              | Retry 2x → HITL                  |
| Retry                  | Zero (intencional)           | 2 tentativas com backoff         |
| Fallback               | Sem fallback                 | HITL com flag bureau_unavailable |
| Contexto recebido      | CPF mascarado + request_id   | CPF mascarado + request_id       |
| Output alimenta        | Decisão final (via orch.)    | AgentRisk (score + income)       |

---

## Impacto em Specs Existentes

| Spec                        | Tipo de impacto | Descrição                                              |
|-----------------------------|-----------------|--------------------------------------------------------|
| `credit-analysis/spec.md`   | ADDED           | Novo sub-agente: AgentBureau + ferramenta mcp-bureau   |

---

## Critérios de Aceite deste Proposal

- [ ] Spec do AgentBureau revisada e aprovada
- [ ] Política de retry (2x com backoff) documentada e justificada
- [ ] Schema completo do `mcp-bureau` com get_score
- [ ] Guides cobrindo pelo menos 3 anti-exemplos críticos
- [ ] Prompt derivado da spec com prioridades explícitas
- [ ] Eval mínimo: score ok, timeout → retry → ok, timeout → retry → error, restrições ativas