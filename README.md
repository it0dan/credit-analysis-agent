# Sistema de Análise de Crédito Multiagente

## Estrutura

```
credit-analysis-demo/
├── .env.example         ← variáveis de ambiente (copiar e preencher)
├── gateway_auth.py      ← OAuth2 client credentials para o Sensedia Gateway
├── mock_agents.py       ← sub-agentes simulados (substituir por A2A na v2)
├── bureau_agent.py      ← contrato do AgentBureau (runtime independente na v2)
├── compliance_agent.py  ← contrato do AgentCompliance (runtime independente na v2)
├── risk_agent.py        ← contrato do AgentRisk (runtime independente na v2)
├── decision_agent.py    ← contrato do AgentDecision (runtime independente na v2)
├── orchestrator.py      ← agente principal + loop agêntico puro (Gemini)
└── README.md
```

## Arquitetura

```
orchestrator.py
      │  (OAuth2 Bearer via gateway_auth.py)
      ├──→ [Sensedia AI Gateway] ──→ Gemini 2.5 Flash Lite  (LLM)
      │          multi-turn tool_calls por turno
      │
      └──→ mock_agents.py  (funções locais — A2A real na v2)
              ├── bureau_get_score()       → mcp-bureau (Serasa/SPC)
              ├── documents_validate()     → mcp-ocr
              ├── risk_evaluate()          → mcp-risk
              ├── compliance_check()       → mcp-kyc + mcp-pld
              ├── decision_synthesize()    → AgentDecision
              └── handoff_to_human()       → mcp-credit (HITL queue)
```

## Setup

```bash
pip install openai httpx python-dotenv

cp .env.example .env
# Preencher .env com as credenciais do Sensedia Gateway
```

## Variáveis de ambiente

| Variável                    | Descrição                                      |
|-----------------------------|------------------------------------------------|
| `AI_GATEWAY_CLIENT_ID`      | Client ID OAuth2 do Gateway                    |
| `AI_GATEWAY_CLIENT_SECRET`  | Client Secret OAuth2 do Gateway                |
| `AI_GATEWAY_OAUTH_ENDPOINT` | Endpoint de token (Keycloak)                   |
| `AI_GATEWAY_LLM_BASE_URL`   | Base URL do Gateway para chamadas ao LLM       |
| `AI_GATEWAY_MCP_BASE_URL`   | Base URL do Gateway para chamadas MCP          |
| `MCP_SERVER_CREDIT`         | Path do MCP Server de crédito no Gateway       |

## Cenários de demo

```bash
# 1. Aprovação automática — fluxo completo, todos ok, valor ≤ R$50k
python orchestrator.py --scenario auto_approve --amount 20000

# 2. HITL obrigatório — todos ok, valor > R$50k
python orchestrator.py --scenario hitl_required --amount 80000

# 3. Recusa por compliance — KYC/PLD bloqueado, recusa imediata
python orchestrator.py --scenario compliance_fail --amount 15000

# 4. Fallback por erro do bureau — retry esgotado, escala para HITL
python orchestrator.py --scenario bureau_error --amount 10000

# 5. Fallback múltiplo — bureau + documentos falham simultaneamente
python orchestrator.py --scenario multi_error --amount 10000
```

## O que cada cenário demonstra

| Cenário           | Conceito                                                           | Trajectory esperado                                              |
|-------------------|--------------------------------------------------------------------|------------------------------------------------------------------|
| `auto_approve`    | Fluxo completo, loop puro, trajectory real                         | bureau → docs → risk → compliance → decision                     |
| `hitl_required`   | HITL, threshold R$50k, handoff_to_human                            | bureau → docs → risk → compliance → decision → handoff           |
| `compliance_fail` | Guides: short-circuit, recusa sem fallback                         | bureau → docs → risk → compliance → **STOP** (sem decision)      |
| `bureau_error`    | Sensores: fallback imediato, AIOps                                 | bureau(✗) → handoff → **STOP**                                   |
| `multi_error`     | Sensores: fallback múltiplo, flags bureau_unavailable+docs_unverified | bureau(✗) + docs(✗) → handoff → **STOP**                     |

## Loop agêntico puro

O `orchestrator.py` implementa um loop agêntico puro: o LLM decide, a cada
turno, qual ferramenta chamar e quando encerrar. O harness Python apenas
executa as tools e devolve os resultados — nenhuma regra de negócio no código.

```
# Loop puro (implementado)
while finish_reason == "tool_calls":
    for tc in response.tool_calls:
        result = execute_tool(tc.name, tc.arguments)
        messages.append(tool_result(tc.id, result))
    response = llm.complete(messages, tools)
```

Todas as regras de negócio vivem no `SYSTEM_PROMPT` (Guides / feedforward):
sequência obrigatória, compliance-first, threshold HITL, fallbacks, LGPD.

O `trajectory_log` registra cada tool_call em ordem real (decisão do LLM),
habilitando trajectory evals no PromptFoo.

## Observabilidade e FinOps

Cada análise emite ao final:

```
TRAJECTORY LOG (decisões reais do LLM)
  turno 1 ✓ bureau_get_score
  turno 2 ✓ documents_validate
  ...

FINOPS
  LLM requests : 7
  Total tokens : 18710
  Custo ≈ R$   : 0.001594   ← estimado; ajuste COST_PER_*_TOKEN no topo do arquivo
  Loop turns   : 7
```

## Estado atual vs. visão-alvo

| Camada | Atual (v2) | Próximo (v3) |
|---|---|---|
| Agentic loop | **Loop puro real** — LLM dirige, Python executa | Loop puro com retry e backoff por sub-agente |
| Comunicação A2A | Mocks locais em Python | Chamadas A2A reais entre runtimes de sub-agentes |
| Ferramentas MCP | Schemas especificados, mocks nos slots | MCP Servers reais (bureau, ocr, risk, kyc, core) |
| Trajectory evals | `trajectory_log` gerado por análise | Asserts de sequência e short-circuit no PromptFoo |
| Memória semântica | Slot reservado na arquitetura | Vector store com perfil real do cliente |
| FinOps | Tokens reais, R$ estimado por constantes | Pricing real do Gateway ou header `X-Cost-BRL` |
| Evals de decisão | **12/12 passando** (PromptFoo) | + Trajectory evals |
| Gateway | Intercepta LLM, `trace_id` propagado | `trace_id` correlacionando spans A2A distribuídos |

> O loop puro foi validado com o Sensedia AI Gateway em 2026-05-29.
> A limitação documentada no ADR-003 original era uma escolha pragmática,
> não uma restrição real do Gateway. Ver `adr/adr-003-hybrid-agentic-loop.md`.

## Evals

```bash
cd credit-analysis-demo
export AI_GATEWAY_TOKEN=$(python3 -c "from gateway_auth import gateway_auth; print(gateway_auth.get_token())")
npx promptfoo eval --config evals/orchestrator.yaml
npx promptfoo view
```

## Próximos passos (v3)

1. Trajectory evals no PromptFoo validando sequência real de tool_calls
2. Pricing real no FinOps (substituir constantes ou ler header do Gateway)
3. `compliance_agent.py` como runtime HTTP independente chamado via A2A real
4. MCP Servers reais por domínio
5. `adr-003-revised.md` documentando a migração para loop puro