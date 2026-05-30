# Project: Sistema de Análise de Crédito Multiagente

## Visão Geral

Sistema multiagente para processamento de solicitações de crédito de ponta a ponta,
combinando dados externos (bureaus, documentos), modelos internos (risco, compliance)
e decisão com explicabilidade — com aprovação humana (HITL) para créditos acima de
R$ 50.000.

Desenvolvido como demonstração de Arquitetura Agêntica no Sensedia AI Gateway,
cobrindo os quatro conceitos-chave: Engenharia de Contexto & Memória,
Harness Engineering & Evals, Protocolos & Integrações (MCP + A2A), AIOps & FinOps.

---

## Atores do Sistema

| Ator                  | Tipo           | Responsabilidade                                                              |
|-----------------------|----------------|-------------------------------------------------------------------------------|
| Agente Orquestrador   | Agente principal | Recebe solicitação, planeja, delega via A2A, consolida contexto e memória   |
| Agente Bureau         | Sub-agente     | Consulta Serasa/SPC, retorna score e restrições                               |
| Agente Documentos     | Sub-agente     | Aciona OCR, valida identidade e comprovantes de renda                        |
| Agente Risco          | Sub-agente     | Executa modelo interno de score e probabilidade de default                   |
| Agente Compliance     | Sub-agente     | Verifica KYC, PLD e conformidade LGPD                                        |
| Agente Decisão        | Sub-agente     | Sintetiza todos os resultados e gera decisão explicável                      |
| Analista Humano       | HITL           | Aprova, recusa ou ajusta créditos acima de R$ 50.000                         |

---

## Stack Tecnológica

- **AI Gateway:** Sensedia AI Gateway (roteamento, observabilidade, AuthZ, rate limiting)
- **Protocolo vertical (ferramentas):** MCP (Model Context Protocol)
- **Protocolo horizontal (agentes):** A2A (Agent-to-Agent Protocol)
- **Modelo de fundação:** modelo configurável via AI Gateway, demo usando Gemini 2.5 Flash Lite
- **Memória semântica:** Vector store (RAG) para perfil e histórico do cliente
- **Memória episódica:** Base de eventos para interações e decisões passadas
- **Memória procedural:** System prompts + guides para políticas de crédito
- **Observabilidade:** Traces, logs e trajetória de agentes via Sensedia
- **Evals:** PromptFoo para testes declarativos por agente

---

## Padrões Arquiteturais

- Todo sub-agente acessa seus sistemas exclusivamente via MCP Server dedicado.
  Chamadas diretas a APIs externas sem passar pelo MCP são proibidas.
- A comunicação entre agentes se dá exclusivamente via protocolo A2A.
  O Agente Orquestrador não chama sub-agentes por função direta.
- O Agente Decisão NÃO pode emitir aprovação sem retorno dos 4 sub-agentes anteriores.
- HITL é obrigatório para valores acima de R$ 50.000. Não há override por agente.
- Nenhum dado de CPF trafega entre agentes sem mascaramento (CPF → XXX.XXX.XXX-XX).
- Toda decisão deve ser acompanhada de justificativa auditável (groundedness >= 0.85).

---

## Memória e Contexto

### Tipos de Memória
- **Semântica:** Fatos sobre o cliente (perfil, histórico de crédito, renda declarada)
- **Episódica:** Ações passadas do agente e interações anteriores do cliente
- **Procedural:** Políticas de crédito, playbooks de compliance, system prompts

### Pilares de Engenharia de Contexto
- **Write:** Salvar contexto relevante após cada etapa de análise
- **Select:** Recuperar apenas contexto pertinente ao sub-agente em execução
- **Compress:** Sumarizar histórico longo antes de passar ao modelo
- **Isolate:** Cada sub-agente recebe apenas o contexto do seu domínio

---

## Harness: Guides e Sensores

### Guides (feedforward — reduzem erro antes da ação)
- Políticas de crédito por faixa de valor e perfil de cliente
- Critérios de aceite e DoD por agente (Definition of Done)
- Exemplos e anti-exemplos de saídas esperadas
- Spec de ferramentas, schemas e contratos MCP
- Playbooks de compliance (KYC, PLD, LGPD)
- Restrições de segurança, custo máximo por inferência e limites de autonomia

### Sensores (feedback — reduzem dano após a ação)
- Traces, logs e trajetória de agente
- Tool success rate e fallback rate por sub-agente
- Groundedness e policy compliance da decisão gerada
- LLM-as-judge para avaliação de explicabilidade
- HITL para revisão de casos de alta complexidade

---

## Critérios de Aceite Globais (DoD)

- Decisão gerada em < 8s para créditos até R$ 50.000
- Decisão gerada em < 30s para créditos acima de R$ 50.000 (inclui HITL assíncrono)
- Tool success rate > 95% por sub-agente
- Groundedness score >= 0.85 em toda decisão emitida
- Zero decisões sem consulta ao Agente Compliance
- Zero CPFs trafegando sem mascaramento entre agentes
- Toda decisão registrada com trace completo no Sensedia AI Gateway

---

## AIOps & FinOps

- Custo máximo por análise de crédito: R$ 0,15 (tokens + inferência)
- Budget diário monitorado via Sensedia; alertas em 80% e hard stop em 100%
- Latência P95 < 10s para fluxo automatizado
- SLO de disponibilidade: 99,5%
- Otimização: cache semântico para consultas repetidas ao mesmo CPF no mesmo dia

---

## Convenções de Nomenclatura

- Agentes: PascalCase prefixado com `Agent` → `AgentOrchestrator`, `AgentBureau`
- MCP Servers: kebab-case prefixado com `mcp-` → `mcp-bureau`, `mcp-ocr`
- Ferramentas MCP: snake_case → `get_credit_score`, `validate_document`
- Tarefas A2A: snake_case prefixado com domínio → `bureau.get_score`, `risk.evaluate`
- Arquivos de spec: `spec.md` dentro de pasta nomeada pela capability

---

## Estado Atual vs. Visão-Alvo

Esta seção registra a distância entre o que está implementado hoje e a
arquitetura de referência descrita neste documento. A v1 valida contratos,
políticas, prompts e evals. As versões seguintes implementam a infraestrutura
real de forma incremental.

| Camada | v1 — Walking Skeleton (atual) | v2 — Agent Runtime | v3 — Enterprise-Ready |
|---|---|---|---|
| Agentic loop | Híbrido: Python conduz sequência, LLM sintetiza (ADR-003) | Loop puro conduzido pelo LLM com multi-turn tool_calls | Loop puro com adaptação dinâmica de sequência |
| Comunicação A2A | Mocks locais em Python | Chamadas A2A reais entre runtimes de sub-agentes | A2A com AuthZ por agente e escopo mínimo |
| Ferramentas MCP | Schemas especificados, mocks simulam os slots | MCP Servers reais (bureau, ocr, risk, kyc, core) | MCP com registry, allowlist e circuit breaker |
| Memória semântica | Slot reservado na arquitetura | Vector store populado com perfil real do cliente | RAG com TTL, classificação de sensibilidade e auditoria |
| Memória episódica | Resultados A2A passados no contexto do turno | Event store persistente por CPF mascarado | Retenção controlada com consentimento e finalidade |
| Evals | Decisão final + adversariais (PromptFoo) | + Trajectory evals (tool sequence, short-circuit) | + Evals contínuos em produção com drift detection |
| Observabilidade | Gateway intercepta LLM e MCP handoff | trace_id único correlacionando todos os spans A2A | Dashboard AIOps/FinOps com SLOs, alertas e custo por análise |
| Contratos entre agentes | Schemas JSON documentados na spec | Validação Pydantic em runtime | Policy engine determinístico para regras críticas |
| AuthZ | OAuth2 client credentials no Gateway | Identidade por agente com scopes por ferramenta | Princípio do menor privilégio por agente e por tool |
| FinOps | Custo máximo definido, alertas planejados | Logging de tokens e custo estimado por etapa | Model routing dinâmico por complexidade da tarefa |

---

## Roadmap de Maturidade

| Versão | Foco | Estado |
|---|---|---|
| v1 — Walking Skeleton | Narrativa, contratos, prompts, evals de decisão, demo funcional | ✅ Atual |
| v2 — Agent Runtime | Loop puro, A2A real, MCP Servers reais, tracing distribuído, trajectory evals | ⬜ Próximo |
| v3 — Enterprise-Ready | Policy engine, AuthZ por agente, evals contínuos, validação Pydantic, FinOps visível | ⬜ Alvo |
| v4 — Scale | Multi-tenant, model routing, dashboards executivos, melhoria contínua | ⬜ Futuro |

**Princípio de evolução:** cada versão entrega valor demonstrável e mantém
os evals da versão anterior passando. Nenhuma versão quebra o contrato
estabelecido pela anterior.