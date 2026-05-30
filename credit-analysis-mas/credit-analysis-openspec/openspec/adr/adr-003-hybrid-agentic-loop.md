# ADR-003: Do loop híbrido ao loop agêntico puro

**Status:** REVISED — substitui ADR-003 original (2026-05-26)
**Data da revisão:** 2026-05-29
**Decididores:** Danilo Amaral

---

## Contexto

O ADR-003 original (2026-05-26) documentou a adoção de um loop híbrido —
Python conduzindo a sequência de sub-agentes, LLM sintetizando apenas a
decisão final — com a justificativa de que o Sensedia AI Gateway não
suportava múltiplos turnos de `tool_calls` nativamente.

Durante a implementação da v2 (2026-05-29), a premissa foi testada
empiricamente com o seguinte probe:

```python
# REQUEST 1 — LLM propõe tool_call
r1 = client.chat.completions.create(model=MODEL, messages=msgs, tools=TOOLS)

# adiciona tool_result ao histórico
msgs.append(assistant_msg_with_tool_calls)
msgs.append({"role": "tool", "tool_call_id": tc.id, "content": result})

# REQUEST 2 — mesmo array messages crescente, novo request HTTP
r2 = client.chat.completions.create(model=MODEL, messages=msgs, tools=TOOLS)
# → Gateway aceitou role:"tool" no histórico e respondeu coerente
```

**O Gateway aceitou o ciclo `tool_call → tool_result → nova resposta`
normalmente.** A limitação documentada no ADR-003 original não existia:
cada turno é um request HTTP independente, e o Gateway não mantém nem
precisa manter estado entre eles — o histórico crescente é responsabilidade
do cliente Python.

A restrição era uma escolha pragmática sob prazo de entrega da v1,
não uma limitação real da infraestrutura.

---

## Decisão

**Migrar para loop agêntico puro (Opção A do ADR-003 original).**

O loop puro foi implementado no `orchestrator.py` v2 e validado com
o Sensedia AI Gateway em 2026-05-29 (cenário `auto_approve --amount 100000`,
7 turnos, trajectory completo).

---

## Implementação

```python
# Loop agêntico puro (orchestrator.py v2)
while turn < MAX_TURNS:
    response = client.chat.completions.create(
        model=MODEL, messages=messages, tools=TOOLS, temperature=0
    )
    if response.choices[0].finish_reason != "tool_calls":
        final_text = response.choices[0].message.content
        break

    for tc in response.choices[0].message.tool_calls:
        result = execute_tool(tc.function.name, json.loads(tc.function.arguments))
        trajectory_log.append({"turn": turn, "tool": tc.function.name, ...})
        messages.append({"role": "tool", "tool_call_id": tc.id, "content": json.dumps(result)})
```

Todas as regras de negócio (sequência obrigatória, compliance-first,
threshold HITL, fallbacks, LGPD) foram movidas integralmente para o
`SYSTEM_PROMPT`. O harness Python não contém nenhuma lógica de fluxo.

---

## Consequências

**Positivas:**
- Trajetória real e auditável: `agents_consulted` reflete decisões do LLM,
  não sequência hard-coded em Python
- `trajectory_log` por análise habilita trajectory evals no PromptFoo
  (validação de sequência, short-circuit, compliance-never-skipped)
- LLM pode adaptar a sequência a contextos inesperados
- Alinhado com o modelo de referência da palestra e com o ADR-002
  (A2A: orquestrador coordena, sub-agentes executam)
- FinOps real: tokens acumulados por turno via `response.usage`

**Negativas / trade-offs:**
- N requests ao Gateway por análise em vez de 2 (1 por turno de tool_call)
  — confirmado 7 requests para o fluxo completo com HITL
- Custo por análise ligeiramente maior; aceitável dentro do SLO de R$0,15
- MAX_TURNS (12) como safety brake — improvável de ser atingido em operação normal

**Impacto nos evals:**
Os 12 evals de decisão final continuam válidos — o output JSON é idêntico.
Trajectory evals (validação de sequência e short-circuit) agora são
implementáveis e constam no roadmap v3.

---

## Resultado validado

```
cenário: auto_approve --amount 100000
turnos: 7  |  tokens: 18.710  |  custo≈R$0.001594

TRAJECTORY LOG (decisões reais do LLM)
  turno 1 ✓ bureau_get_score
  turno 2 ✓ documents_validate
  turno 3 ✓ risk_evaluate
  turno 4 ✓ compliance_check
  turno 5 ✓ decision_synthesize
  turno 6 ✓ handoff_to_human
  turno 7   [stop — LLM emitiu JSON de decisão final]

status: pending_human_review  |  reason: threshold_exceeded
```

---

## Referências

- ADR-003 original: `adr/adr-003-hybrid-agentic-loop.md` (arquivado, não deletado)
- ADR-002: A2A sobre tools diretas — este ADR viabiliza a implementação
  correta do padrão definido no ADR-002
- `orchestrator.py` v2 — implementação do loop puro
- `openspec/project.md` § Roadmap v2 → v3