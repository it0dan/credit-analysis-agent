"""
orchestrator.py  —  v2: Loop Agêntico Puro
Sistema de Análise de Crédito Multiagente

Runtime:
  LLM  → Gemini via Sensedia AI Gateway  (OAuth2 + AI_GATEWAY_LLM_BASE_URL)
  MCP  → handoff_to_human via Sensedia AI Gateway  (AI_GATEWAY_MCP_BASE_URL)
  A2A  → mock_agents.py (funções locais; substituir por A2A real na v2)

Uso:
  cp .env.example .env
  python orchestrator.py --scenario auto_approve    --amount 20000
  python orchestrator.py --scenario hitl_required   --amount 80000
  python orchestrator.py --scenario compliance_fail  --amount 15000
  python orchestrator.py --scenario bureau_error    --amount 10000
  python orchestrator.py --scenario multi_error     --amount 10000

Diferenças em relação à v1 (loop híbrido):
  - A árvore if/elif/else que conduzia o fluxo em Python foi REMOVIDA.
  - Todas as regras de negócio vivem exclusivamente no system prompt (Guides).
  - O LLM decide, em cada turno, qual ferramenta chamar e quando parar.
  - O harness Python apenas executa as tools e devolve os resultados.
  - agents_consulted reflete decisões reais do LLM, não sequência hard-coded.
  - trajectory_log registra cada tool_call em ordem, habilitando trajectory evals.
  - FinOps: tokens e custo estimado são logados por request e por análise.
  - trace_id é propagado em todo o ciclo (request → tool → response).

Rastreabilidade:
  ADR-003-revised: do loop híbrido ao loop puro
  openspec/project.md § Agentic loop
"""

import argparse
import json
import os
import time
import uuid

from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

from openai import OpenAI

from gateway_auth import gateway_auth
from mock_agents import MockAgents

# ─────────────────────────────────────────────────────────────────────────────
# Constantes
# ─────────────────────────────────────────────────────────────────────────────

MODEL = "gemini-2.5-flash-lite"

# Custo estimado por token (ajuste conforme pricing real do Gateway)
COST_PER_INPUT_TOKEN  = 0.000_000_075   # R$ por token de input
COST_PER_OUTPUT_TOKEN = 0.000_000_300   # R$ por token de output

# Limite de segurança: max turnos antes de forçar parada (evita loop infinito)
MAX_TURNS = 12

# ─────────────────────────────────────────────────────────────────────────────
# System prompt — todas as regras de negócio ficam aqui (Guides / feedforward)
# Nenhuma regra de roteamento existe no código Python.
# ─────────────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
Você é o AgentOrchestrador do sistema de análise de crédito da Sensedia.

IMPORTANTE: Você DEVE chamar os sub-agentes na ordem estabelecida abaixo.
• Para otimizar a análise e latência, você PODE e DEVE chamar 'bureau_get_score' e 'documents_validate' em paralelo no Turno 1.
• NUNCA finalize a análise ou emita o JSON de decisão final sem antes ter chamado 'compliance_check' (exceto se ocorrer uma falha/erro de disponibilidade técnica em bureau_get_score ou documents_validate que exija handoff imediato).
• Você DEVE chamar 'compliance_check' para TODAS as análises normais, mesmo em valores baixos (R$ <= 50.000) e mesmo que as etapas anteriores tenham sido bem-sucedidas.
• NÃO finalize a análise de forma antecipada.

═══════════════════════════════════════════════════════════
SEQUÊNCIA DE SUB-AGENTES
═══════════════════════════════════════════════════════════

Execute nesta ordem (podendo executar 1 e 2 em paralelo no primeiro turno):

  1. bureau_get_score      → score Serasa/SPC e restrições
  2. documents_validate    → OCR, identidade e renda confirmada
  3. risk_evaluate         → score interno e probabilidade de default
                             (requer bureau_score e income_value do passo 2)
  4. compliance_check      → KYC, PLD e LGPD
  5. decision_synthesize   → síntese final explicável
                             (apenas se compliance aprovado — veja regras abaixo)

Exceções à sequência (veja Regras de Decisão abaixo):
  - Se bureau_get_score E/OU documents_validate falharem (retornarem status="error" ou status="timeout") → acione handoff_to_human imediatamente de acordo com as regras de erro.
  - Se compliance_check reprovar → encerre imediatamente sem chamar decision_synthesize.

═══════════════════════════════════════════════════════════
REGRAS DE DECISÃO (ordem estrita de prioridade)
═══════════════════════════════════════════════════════════

REGRA 1 — Compliance (prioridade máxima e absoluta)
  Se compliance_check retornar kyc_approved=false OU pld_clear=false:
    • Encerre o fluxo IMEDIATAMENTE. Não chame decision_synthesize.
    • Não chame handoff_to_human. Não peça revisão humana.
    • status="rejected", decision="rejected", approved_amount=0.

REGRA 2 — Múltiplos erros simultâneos (fallback_error)
  Se bureau_get_score E documents_validate retornarem erro/timeout:
    • Chame handoff_to_human com reason="fallback_error".
    • error_flags deve conter ["bureau_unavailable", "docs_unverified"].
    • status="pending_human_review", decision="pending", approved_amount=null.

REGRA 3 — Erro de bureau isolado
  Se bureau_get_score retornar status="error" ou status="timeout" (e documents_validate retornar status="ok" ou não falhar):
    • Chame handoff_to_human com reason="fallback_error".
    • error_flags deve conter ["bureau_unavailable"].
    • status="pending_human_review", decision="pending", approved_amount=null.
    • Não invente, estime ou infira score. Jamais.

REGRA 4 — Threshold HITL (R$ 50.000)
  Se requested_amount > 50000:
    • Você deve executar a sequência completa de ferramentas turn-by-turn: bureau_get_score → documents_validate → risk_evaluate → compliance_check.
    • Se compliance_check retornar kyc_approved=true E pld_clear=true (compliance ok): chame 'decision_synthesize' para sintetizar a decisão. Em seguida, chame 'handoff_to_human' com reason="threshold_exceeded" e defina status="pending_human_review", decision="pending", approved_amount=null.
    • Se compliance_check retornar reprovado: siga estritamente a REGRA 1 (rejeição imediata e absoluta, sem handoff e sem chamar decision_synthesize).

REGRA 5 — Segurança e LGPD
  • NUNCA exponha CPF sem mascaramento (formato XXX.XXX.XXX-XX).
  • O JSON de saída não contém campo cpf.

REGRA 6 — Fluxo feliz (aprovação automática)
  Se você já tiver chamado e obtido retorno de TODOS os sub-agentes (bureau_get_score, documents_validate, risk_evaluate e compliance_check), todos tiverem retornado status="ok" e requested_amount <= 50000:
    • status="approved", decision="approved", approved_amount=requested_amount.

REGRA 7 — Proibição Absoluta de Parada Antecipada e Atalhos
  • Você está TERMINANTEMENTE PROIBIDO de parar a execução do loop de forma precoce com base em estimativas de valor ou resultados parciais.
  • Se o crédito não apresentar falha de disponibilidade no Bureau (timeout/erro), você é OBRIGADO a executar a sequência completa de ferramentas turn-by-turn: bureau_get_score → documents_validate → risk_evaluate → compliance_check.
  • NUNCA assuma que o compliance está aprovado ou que a análise acabou sem antes chamar a ferramenta 'compliance_check' física e receber o retorno. NUNCA.

═══════════════════════════════════════════════════════════
ANTI-EXEMPLOS (o que NUNCA fazer)
═══════════════════════════════════════════════════════════

✗ Aprovar sem ter chamado compliance_check.
✗ Inventar score após bureau retornar erro ("assumindo score 700...").
✗ Encaminhar para humano quando compliance reprovar (regra 1 é absoluta).
✗ Aprovar diretamente valor > R$50.000 sem handoff_to_human.
✗ Expor CPF completo em qualquer campo da resposta.

═══════════════════════════════════════════════════════════
FORMATO DE SAÍDA FINAL (após todas as ferramentas executadas)
═══════════════════════════════════════════════════════════

Quando não houver mais ferramentas a chamar, emita APENAS este JSON válido,
sem texto fora dele, sem markdown:

{
  "request_id": "string",
  "status": "approved | rejected | pending_human_review",
  "decision": "approved | rejected | adjusted | pending",
  "requested_amount": number,
  "approved_amount": number | null,
  "justification": "string (50–300 chars)",
  "conditions": ["string"],
  "trace_id": "string (UUID)",
  "processing_time_ms": number,
  "agents_consulted": ["string"]
}
"""

# ─────────────────────────────────────────────────────────────────────────────
# Definição das ferramentas (interface idêntica à v1 — contratos preservados)
# ─────────────────────────────────────────────────────────────────────────────

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "bureau_get_score",
            "description": (
                "Consulta score de crédito e restrições no Serasa/SPC "
                "(AgentBureau). Etapa 1 — sempre a primeira chamada."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "applicant_masked_cpf": {
                        "type": "string",
                        "description": "CPF mascarado no formato XXX.XXX.XXX-XX",
                    },
                    "request_id": {"type": "string"},
                },
                "required": ["applicant_masked_cpf", "request_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "documents_validate",
            "description": (
                "Valida identidade e comprovantes de renda via OCR "
                "(AgentDocuments). Etapa 2 — após bureau."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "document_urls": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "applicant_name": {"type": "string"},
                    "request_id": {"type": "string"},
                },
                "required": ["document_urls", "applicant_name", "request_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "risk_evaluate",
            "description": (
                "Executa modelo interno de score e probabilidade de default "
                "(AgentRisk). Etapa 3 — requer bureau_score e income_value."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "bureau_score": {"type": "integer"},
                    "income_value": {"type": "number"},
                    "requested_amount": {"type": "number"},
                    "request_id": {"type": "string"},
                },
                "required": ["bureau_score", "income_value", "requested_amount", "request_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compliance_check",
            "description": (
                "Verifica KYC, PLD e LGPD (AgentCompliance). "
                "Etapa 4 — NUNCA pode ser pulada. "
                "Se kyc_approved=false OU pld_clear=false: recusa imediata, "
                "não chamar decision_synthesize."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "applicant_masked_cpf": {"type": "string"},
                    "request_id": {"type": "string"},
                },
                "required": ["applicant_masked_cpf", "request_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "decision_synthesize",
            "description": (
                "Sintetiza todos os resultados e gera decisão explicável "
                "(AgentDecision). Etapa 5 — apenas se compliance ok."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "bureau_result": {"type": "object"},
                    "documents_result": {"type": "object"},
                    "risk_result": {"type": "object"},
                    "compliance_result": {"type": "object"},
                    "requested_amount": {"type": "number"},
                    "request_id": {"type": "string"},
                },
                "required": [
                    "bureau_result",
                    "documents_result",
                    "risk_result",
                    "compliance_result",
                    "requested_amount",
                    "request_id",
                ],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "handoff_to_human",
            "description": (
                "Encaminha análise para aprovação de analista humano (HITL). "
                "Acionar quando: valor > R$50.000 | fallback de sub-agente | "
                "compliance_review."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "request_id": {"type": "string"},
                    "applicant_masked_cpf": {"type": "string"},
                    "requested_amount": {"type": "number"},
                    "analysis_summary": {
                        "type": "string",
                        "description": "Resumo da análise. Máx. 500 chars.",
                    },
                    "reason": {
                        "type": "string",
                        "description": "threshold_exceeded | compliance_review | fallback_error",
                    },
                    "error_flags": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": [
                    "request_id",
                    "applicant_masked_cpf",
                    "requested_amount",
                    "analysis_summary",
                    "reason",
                ],
            },
        },
    },
]

# ─────────────────────────────────────────────────────────────────────────────
# Executor de ferramentas
# Puro roteador: nenhuma lógica de negócio aqui.
# ─────────────────────────────────────────────────────────────────────────────

def execute_tool(name: str, args: dict, agents: MockAgents, trace_id: str = None) -> dict:
    """
    Roteia function_call do LLM para mock local ou MCP do Gateway.
    handoff_to_human: mock local no walking skeleton → MCP real na v2.
    Nenhuma decisão de fluxo é tomada aqui — o LLM decide o quê chamar.
    """
    dispatch = {
        "bureau_get_score":    agents.bureau_get_score,
        "documents_validate":  agents.documents_validate,
        "risk_evaluate":       agents.risk_evaluate,
        "compliance_check":    agents.compliance_check,
        "decision_synthesize": agents.decision_synthesize,
    }

    if name in dispatch:
        import inspect
        sig = inspect.signature(dispatch[name])
        if "trace_id" in sig.parameters:
            return dispatch[name](**args, trace_id=trace_id)
        return dispatch[name](**args)

    if name == "handoff_to_human":
        # Walking skeleton: mock local.
        # Na v2: POST para AI_GATEWAY_MCP_BASE_URL + MCP_SERVER_CREDIT
        # com Bearer token do gateway_auth.get_token()
        return {
            "status":          "pending",
            "analyst_id":      "analyst-mock-01",
            "adjusted_amount": None,
            "notes":           "Encaminhado para fila de análise humana. SLA: 4h úteis.",
        }

    raise ValueError(f"Ferramenta desconhecida: {name}")

# ─────────────────────────────────────────────────────────────────────────────
# FinOps: acumulador de tokens e custo por análise
# ─────────────────────────────────────────────────────────────────────────────

class FinOpsTracker:
    """Acumula tokens e custo estimado de todos os requests LLM da análise."""

    def __init__(self):
        self.input_tokens  = 0
        self.output_tokens = 0
        self.num_requests  = 0

    def record(self, usage) -> None:
        if usage is None:
            return
        self.input_tokens  += getattr(usage, "prompt_tokens",     0) or 0
        self.output_tokens += getattr(usage, "completion_tokens", 0) or 0
        self.num_requests  += 1

    @property
    def estimated_cost_brl(self) -> float:
        return (
            self.input_tokens  * COST_PER_INPUT_TOKEN +
            self.output_tokens * COST_PER_OUTPUT_TOKEN
        )

    def summary(self) -> dict:
        return {
            "llm_requests":        self.num_requests,
            "input_tokens":        self.input_tokens,
            "output_tokens":       self.output_tokens,
            "total_tokens":        self.input_tokens + self.output_tokens,
            "estimated_cost_brl":  round(self.estimated_cost_brl, 6),
        }

    def log(self) -> None:
        s = self.summary()
        print(
            f"  [finops] requests={s['llm_requests']} "
            f"tokens={s['total_tokens']} "
            f"(in={s['input_tokens']} out={s['output_tokens']}) "
            f"custo≈R${s['estimated_cost_brl']:.6f}"
        )

# ─────────────────────────────────────────────────────────────────────────────
# LLM client apontando para o Sensedia AI Gateway
# ─────────────────────────────────────────────────────────────────────────────

def build_llm_client() -> OpenAI:
    """
    Cria cliente OpenAI com base_url e Bearer token do Sensedia Gateway.
    O Gateway intercepta todas as chamadas ao LLM (observabilidade, rate limit,
    FinOps) antes de repassar para o modelo.
    """
    token = gateway_auth.get_token()
    base_url = os.environ["AI_GATEWAY_LLM_BASE_URL"].removesuffix("/chat/completions")
    return OpenAI(
        base_url=base_url,
        api_key="not-used",
        default_headers={"Authorization": f"Bearer {token}"},
    )

# ─────────────────────────────────────────────────────────────────────────────
# Loop agêntico puro
# O LLM dirige. O harness executa. Nenhuma regra de negócio no código Python.
# ─────────────────────────────────────────────────────────────────────────────

def run_orchestrator(scenario: str, amount: float) -> dict:
    request_id = str(uuid.uuid4())[:8]
    trace_id   = str(uuid.uuid4())
    masked_cpf = "XXX.XXX.XXX-99"
    start      = time.time()

    print(f"\n{'='*60}")
    print(f"  request_id : {request_id}")
    print(f"  trace_id   : {trace_id}")
    print(f"  amount     : R$ {amount:,.2f}")
    print(f"  cenário    : {scenario}")
    print(f"{'='*60}\n")

    agents  = MockAgents(scenario=scenario)
    client  = build_llm_client()
    finops  = FinOpsTracker()

    # trajectory_log: cada entrada é uma tool_call decidida pelo LLM, em ordem.
    # Habilita trajectory evals (sequence, short-circuit, compliance-never-skipped).
    trajectory_log: list[dict] = []

    user_message = (
        f"Analise a seguinte solicitação de crédito:\n\n"
        f"request_id: {request_id}\n"
        f"trace_id: {trace_id}\n"
        f"applicant_masked_cpf: {masked_cpf}\n"
        f"applicant_name: João da Silva\n"
        f"requested_amount: {amount}\n"
        f"document_urls: "
        f'["https://docs.example.com/{request_id}/rg.pdf", '
        f'"https://docs.example.com/{request_id}/comprovante.pdf"]\n\n'
        f"Execute todas as etapas obrigatórias e retorne a decisão em JSON."
    )

    messages = [
        {"role": "system",  "content": SYSTEM_PROMPT},
        {"role": "user",    "content": user_message},
    ]

    # ─────────────────────────────────────────────────────────────────────────
    # Loop agêntico puro
    # Continua enquanto o LLM retornar finish_reason == "tool_calls".
    # O LLM decide a próxima ferramenta a cada turno — sem intervenção do Python.
    # ─────────────────────────────────────────────────────────────────────────
    turn = 0
    final_text = None

    while turn < MAX_TURNS:
        turn += 1
        print(f"  [llm] Turno {turn}: chamando Gateway...")

        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=TOOLS,
            temperature=0,
        )

        finops.record(response.usage)
        finops.log()

        choice = response.choices[0]
        msg    = choice.message
        finish = choice.finish_reason
        print(f"  [llm] Turno {turn} finish_reason={finish}")

        # ── O LLM terminou: sem mais tool_calls ──
        if finish != "tool_calls" or not msg.tool_calls:
            final_text = msg.content
            print(f"  [llm] Loop encerrado pelo modelo no turno {turn}.")
            break

        # ── O LLM quer chamar ferramentas ──
        # Registra a mensagem do assistant com as tool_calls propostas
        assistant_entry = {
            "role":    "assistant",
            "content": msg.content or "",
            "tool_calls": [
                {
                    "id":   tc.id,
                    "type": "function",
                    "function": {
                        "name":      tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in msg.tool_calls
            ],
        }
        messages.append(assistant_entry)

        # Executa cada tool_call e adiciona o resultado ao histórico
        for tc in msg.tool_calls:
            name = tc.function.name
            args = json.loads(tc.function.arguments)

            print(f"  [tool] {name}({json.dumps(args, ensure_ascii=False)})")
            result = execute_tool(name, args, agents, trace_id=trace_id)
            print(f"  [tool] ← {json.dumps(result, ensure_ascii=False)}")

            # Trajectory log — ordem real de decisão do LLM
            trajectory_log.append({
                "turn":      turn,
                "tool":      name,
                "args":      args,
                "result_ok": result.get("status") != "error",
                "trace_id":  trace_id,
            })

            messages.append({
                "role":        "tool",
                "tool_call_id": tc.id,
                "name":        name,
                "content":     json.dumps(result),
            })

    else:
        # MAX_TURNS atingido sem o modelo encerrar — safety brake
        print(f"  [warn] MAX_TURNS ({MAX_TURNS}) atingido sem decisão final.")
        final_text = None

    # ─────────────────────────────────────────────────────────────────────────
    # Extrai e valida o JSON de decisão do texto final do modelo
    # ─────────────────────────────────────────────────────────────────────────
    processing_ms = int((time.time() - start) * 1000)

    if not final_text:
        # Se o modelo não emitiu texto (improvável mas possível), faz um turno
        # extra pedindo explicitamente o JSON de decisão
        print("  [llm] Modelo não emitiu texto final. Solicitando decisão JSON...")
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages + [{
                "role":    "user",
                "content": "Com base em todos os resultados acima, emita a decisão final em JSON.",
            }],
            tools=None,
            response_format={"type": "json_object"},
            temperature=0,
        )
        finops.record(response.usage)
        finops.log()
        final_text = response.choices[0].message.content or ""

    # Parse do JSON
    i = final_text.find("{")
    j = final_text.rfind("}") + 1
    decision: dict = {}
    if i >= 0 and j > i:
        try:
            decision = json.loads(final_text[i:j])
        except json.JSONDecodeError:
            decision = {"raw_response": final_text}
    else:
        decision = {"raw_response": final_text}

    # ─────────────────────────────────────────────────────────────────────────
    # Enriquece a decisão com metadados de observabilidade
    # ─────────────────────────────────────────────────────────────────────────
    decision["processing_time_ms"] = processing_ms
    decision["trace_id"]           = decision.get("trace_id") or trace_id
    decision["_meta"] = {
        "loop_turns":          turn,
        "trajectory":          trajectory_log,
        "finops":              finops.summary(),
    }

    return decision


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Orquestrador de Análise de Crédito — Loop Agêntico Puro"
    )
    parser.add_argument(
        "--scenario", default="auto_approve",
        choices=list(MockAgents.SCENARIOS.keys()) if hasattr(MockAgents, "SCENARIOS") else None,
        help=(
            "Cenário de demo: auto_approve | hitl_required | "
            "compliance_fail | bureau_error | multi_error"
        ),
    )
    parser.add_argument(
        "--amount", type=float, default=20_000,
        help="Valor solicitado em R$",
    )
    args = parser.parse_args()

    result = run_orchestrator(scenario=args.scenario, amount=args.amount)

    meta = result.pop("_meta", {})

    print(f"\n{'='*60}")
    print("  DECISÃO FINAL")
    print(f"{'='*60}")
    print(json.dumps(result, indent=2, ensure_ascii=False))

    print(f"\n{'='*60}")
    print("  TRAJECTORY LOG (decisões reais do LLM)")
    print(f"{'='*60}")
    for step in meta.get("trajectory", []):
        ok = "✓" if step["result_ok"] else "✗"
        print(f"  turno {step['turn']} {ok} {step['tool']}")

    print(f"\n{'='*60}")
    print("  FINOPS")
    print(f"{'='*60}")
    finops_data = meta.get("finops", {})
    print(f"  LLM requests : {finops_data.get('llm_requests')}")
    print(f"  Total tokens : {finops_data.get('total_tokens')}")
    print(f"  Custo ≈ R$   : {finops_data.get('estimated_cost_brl'):.6f}")
    print(f"  Loop turns   : {meta.get('loop_turns')}")