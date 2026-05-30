# Design: Agente Orquestrador de Análise de Crédito

**Change ID:** add-orchestrator-agent
**Status:** IN REVIEW
**Autor:** Danilo Amaral
**Data:** 2026-05-25

---

## Contexto

O AgentOrchestrator é o ponto de entrada único do sistema de análise de crédito.
Este documento registra as decisões técnicas tomadas durante o design deste change,
antes da implementação. Decisões com impacto arquitetural duradouro foram extraídas
para ADRs próprios (ver `openspec/adr/`).

---

## Diagrama C4 — Nível de Componente

```
┌─────────────────────────────────────────────────────────────────────┐
│  Sistema de Análise de Crédito [Container: Sensedia AI Gateway]     │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  AgentOrchestrator [Component]                               │  │
│  │                                                              │  │
│  │  ┌─────────────┐   ┌──────────────┐   ┌─────────────────┐  │  │
│  │  │ Context     │   │ Planner      │   │ HITL Evaluator  │  │  │
│  │  │ Loader      │   │              │   │                 │  │  │
│  │  │ (RAG +      │   │ (sequência   │   │ (threshold      │  │  │
│  │  │  episódica) │   │  A2A serial) │   │  R$ 50k)        │  │  │
│  │  └──────┬──────┘   └──────┬───────┘   └────────┬────────┘  │  │
│  │         └─────────────────┴────────────────────┘           │  │
│  │                           │                                 │  │
│  └───────────────────────────┼─────────────────────────────────┘  │
│                              │ A2A                                  │
│         ┌────────────────────┼─────────────────────┐               │
│         ▼          ▼         ▼         ▼            ▼               │
│   [AgentBureau] [AgentDocs] [AgentRisk] [AgentCompliance] [AgentDecision] │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
         │ MCP                 │ MCP         │ MCP
         ▼                     ▼             ▼
   [Serasa/SPC]           [KYC/PLD]    [Core bancário]
```

---

## Decisões Técnicas deste Change

### DT-001 — Separação entre Context Loader e Planner

**Problema:** O orquestrador precisa carregar contexto do cliente E planejar a sequência
de análise. Fazer isso em uma única etapa mistura memória com lógica de controle.

**Decisão:** Tratar como duas responsabilidades distintas no prompt:
- **Context Loader** executa primeiro, carrega memória semântica + episódica
- **Planner** recebe o contexto já carregado e decide a sequência A2A

**Razão:** Permite compressão de contexto entre as duas etapas se necessário,
e facilita evals independentes de cada responsabilidade.

**Consequência:** O prompt do orquestrador terá duas seções distintas de instrução,
com handoff explícito de contexto entre elas.

---

### DT-002 — Formato de handoff entre orquestrador e sub-agentes

**Problema:** O que o orquestrador passa para cada sub-agente via A2A?
Passar o contexto completo é caro e vaza informação entre domínios.

**Decisão:** Cada chamada A2A recebe apenas os campos necessários para aquele domínio
(princípio do isolamento de contexto da palestra). O orquestrador mantém o estado
consolidado internamente e nunca expõe o payload completo a um único sub-agente.

**Razão:** Reduz custo de tokens, respeita LGPD (sub-agente de documentos não
precisa ver o score do bureau) e limita blast radius de falha.

**Consequência:** O orquestrador precisa de lógica explícita de "o que passar para quem",
documentada na spec de cada sub-agente.

---

### DT-003 — Comportamento durante espera de HITL

**Problema:** Créditos acima de R$ 50k exigem aprovação humana com SLA de 4h.
O orquestrador não pode ficar bloqueado esperando.

**Decisão:** Padrão fire-and-forget com callback:
1. Orquestrador chama `handoff_to_human` e recebe `request_id` + `status: pending`
2. Retorna imediatamente ao solicitante com status pending e prazo estimado
3. Quando o analista decide, o sistema notifica via webhook (fora do escopo deste change)

**Razão:** Evita timeout do agente, libera recursos e melhora experiência do solicitante.

**Consequência:** O estado `pending` precisa ser persistido externamente (fora do agente).
Tratamento do callback será especificado em change separado.

---

## Suposições

- O Sensedia AI Gateway já está configurado com AuthZ e rate limiting ativos.
- O vector store para memória semântica está populado com dados do cliente antes
  da primeira chamada ao orquestrador.
- O canal de notificação HITL (e-mail / sistema interno) está disponível independente
  deste agente.

---

## Perguntas em Aberto

- [ ] Qual o comportamento se o analista não responder dentro do SLA de 4h?
      → Auto-recusa ou escala para supervisor? (definir antes do Apply)
- [ ] O orquestrador deve registrar o estado `pending` no mesmo vector store
      ou em uma base de eventos separada?
      → Impacta design da memória episódica (definir antes do Apply)

---

## Decisões Arquiteturais Extraídas para ADR

| ADR | Título | Arquivo |
|-----|--------|---------|
| ADR-001 | Sequência serial vs paralelo entre sub-agentes | `openspec/adr/ADR-001-serial-vs-parallel.md` |
| ADR-002 | Protocolo A2A vs chamada direta de ferramentas | `openspec/adr/ADR-002-a2a-vs-direct-tools.md` |
