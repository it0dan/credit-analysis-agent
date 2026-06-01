# credit-analysis-agent — Agent Guide

Sistema multiagente (MAS) de análise de crédito. Orquestrador do loop agêntico
híbrido paralelo-serial (T1/T2/T3) que coordena agentes especializados via
Sensedia AI Gateway. Materialização da palestra "Arquitetura Agêntica:
Construindo Sistemas Multiagentes Eficientes" — APIX 2026.

## Stack

- Python 3.12
- Gemini 2.5 Flash Lite via Sensedia AI Gateway (OpenAI SDK compat layer)
- PromptFoo para evals
- asyncio para paralelismo interno por turno

## Comandos essenciais

```bash
# Executar orquestrador
cd credit-analysis-mas/credit-analysis-demo
python orchestrator.py

# Executar evals
cd credit-analysis-mas/credit-analysis-demo/evals
promptfoo eval -c orchestrator.yaml
promptfoo eval -c trajectory.yaml
promptfoo eval -c bureau.yaml
promptfoo eval -c compliance.yaml

# Variáveis de ambiente obrigatórias (nunca commitar valores)
AI_GATEWAY_CLIENT_ID=
AI_GATEWAY_CLIENT_SECRET=
AI_GATEWAY_OAUTH_ENDPOINT=
AI_GATEWAY_LLM_BASE_URL=
AI_GATEWAY_MCP_BASE_URL=
MCP_SERVER_CREDIT=
A2A_COMPLIANCE_PORT=8085
```

## Arquitetura — loop agêntico híbrido (ADR-004 ACCEPTED)

Três turnos com paralelismo interno. Turno N só inicia após N-1 estar completo.

| Turno | Modo | Agentes |
|---|---|---|
| T1 | paralelo | `bureau_get_score` + `documents_validate` |
| T2 | paralelo | `risk_evaluate` + `compliance_check` |
| T3 | serial | `decision_synthesize` |

Short-circuit em qualquer turno → handoff imediato para HITL.

## Cenários validados

| Cenário | Trajectory | Status |
|---|---|---|
| `auto_approve` | T1 → T2 → T3 | ✓ |
| `hitl_required` | T1 → T2 → T3 + handoff | ✓ |
| `compliance_fail` | T1 → T2 → STOP | ✓ |
| `bureau_error` | T1(✗) → handoff → STOP | ✓ |
| `multi_error` | T1(✗✗) → handoff → STOP | ✓ |

## Estrutura de arquivos relevante

```
credit-analysis-mas/
├── credit-analysis-demo/
│   ├── orchestrator.py           ← loop agêntico puro (não modificar sem ADR)
│   ├── orchestrator_provider.py  ← provider determinístico para PromptFoo
│   ├── mock_agents.py            ← envelope normalizado p/ Gateway (v2)
│   ├── gateway_auth.py           ← OAuth2 client credentials
│   ├── compliance_agent.py       ← servidor HTTP A2A local porta 8085 (FALLBACK)
│   ├── episodic_memory.json      ← event store por CPF mascarado
│   └── evals/
│       ├── orchestrator.yaml     ← 12/12 ✓
│       └── trajectory.yaml       ← cenários T1/T2/T3 ✓
└── credit-analysis-openspec/openspec/
    ├── project.md                ← MODELO CANÔNICO — ler antes de trabalho arquitetural
    ├── specs/credit-analysis/spec.md
    ├── adr/                      ← ADR-002, ADR-004, ADR-005 vigentes
    └── changes/archive/          ← histórico imutável (não injetar no agente)
```

## Modelo canônico — ler antes de qualquer trabalho arquitetural

Antes de propor qualquer mudança arquitetural, leia:

1. `credit-analysis-mas/credit-analysis-openspec/openspec/project.md`
2. `credit-analysis-mas/credit-analysis-openspec/openspec/specs/credit-analysis/spec.md`
3. ADRs vigentes: `adr/adr-002-a2a-vs-direct-tools.md`, `adr/adr-004-hybrid-parallel-serial.md`, `adr/adr-005-compliance-versioning.md`

NÃO leia ADR-001 (SUPERSEDED) nem ADR-003 (REVISED) como referência de decisão.

## Invariantes arquiteturais — MUST / NEVER

**MUST:**
- Todo acesso ao `compliance-agent` DEVE passar pelo Sensedia AI Gateway — nunca chamada direta
- Toda mudança DEVE seguir o processo OpenSpec: `proposal.md → design.md → spec.md → tasks.md → prompt.md`
- FinOpsTracker DEVE registrar `prompt_tokens + completion_tokens` por request com `estimated_cost_brl`
- Memória episódica DEVE usar CPF mascarado e ofuscação semântica (CODE_A / CODE_R / CODE_P)

**NEVER:**
- NEVER remover `compliance_agent.py` (fallback local) sem URL definitiva configurada no Gateway
- NEVER referenciar ADR-001 ou ADR-003 como decisões vigentes
- NEVER serializar agentes dentro de um mesmo turno sem novo ADR aprovado
- NEVER commitar variáveis de ambiente com valores reais

## Processo obrigatório para mudanças (OpenSpec)

Qualquer mudança — por menor que seja — DEVE gerar os seguintes artefatos em ordem:

```
openspec/changes/<nome-da-mudança>/
├── proposal.md    ← o quê e por quê
├── design.md      ← decisões técnicas DT-001..N
├── spec.md        ← contrato atualizado
├── tasks.md       ← tarefas atômicas
└── prompt.md      ← SPDD derivation guide para o agente executor
```

Após conclusão e validação → mover para `openspec/changes/archive/<nome-da-mudança>/`.

## Contexto de sessão

**Ao iniciar:** leia `.agent/handoff.md`. Se não estiver vazio, o conteúdo
representa o estado exato de onde a última sessão parou — siga a partir daí.

**Ao encerrar:** atualize `.agent/handoff.md` com:
- O que foi implementado ou decidido nesta sessão
- Estado atual dos arquivos modificados
- Próximo passo concreto (ação específica, não direção genérica)
- Qualquer invariante nova que emergiu durante o trabalho
