"""
risk_agent.py
Agente de Risco (AgentRisk) independente.
Roda o fluxo do sub-agente de análise de risco sob o Sensedia AI Gateway.

Rastreabilidade:
  add-risk-agent/specs/risk-agent/spec.md
"""

import os
import sys
import json
import time
import uuid
import argparse
from typing import Any
from openai import OpenAI

from dotenv import load_dotenv
load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

from gateway_auth import gateway_auth
from mock_agents import MockAgents

MODEL = "gemini-2.5-flash-lite"

# ─────────────────────────────────────────────────────────────────────────────
# Definição das Ferramentas MCP (mcp-risk) para o OpenAI SDK
# ─────────────────────────────────────────────────────────────────────────────

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "evaluate_risk_model",
            "description": "Calcula de forma determinística o score de risco interno, probabilidade de default e razão de comprometimento de renda",
            "parameters": {
                "type": "object",
                "properties": {
                    "bureau_score": {"type": "integer"},
                    "income_value": {"type": "number"},
                    "requested_amount": {"type": "number"}
                },
                "required": ["bureau_score", "income_value", "requested_amount"]
            }
        }
    }
]

# ─────────────────────────────────────────────────────────────────────────────
# Carrega system prompt do arquivo SPDD do change
# ─────────────────────────────────────────────────────────────────────────────

def load_risk_prompt() -> str:
    paths_to_try = [
        os.path.join(
            os.path.dirname(__file__), "..",
            "openspec",
            "changes", "archive", "add-risk-agent", "prompt.md",
        ),
        os.path.join(
            os.path.dirname(__file__), "..",
            "openspec",
            "changes", "add-risk-agent", "prompt.md",
        ),
        # Fallback local
        os.path.join(os.path.dirname(__file__), "prompt.md")
    ]
    for prompt_path in paths_to_try:
        if os.path.exists(prompt_path):
            with open(prompt_path) as f:
                content = f.read()
                if "Você é o AgentRisk" in content:
                    return content

    # Fallback inline rigoroso
    return (
        "Você é o AgentRisk do sistema de análise de crédito multiagente.\n"
        "Seu objetivo é analisar o risco financeiro e a probabilidade de default com base em dados numéricos puros de bureau de crédito, renda comprovada e montante de empréstimo solicitado.\n\n"
        "REGRAS DE EXECUÇÃO E PROCESSAMENTO (Prioridade Estrita):\n\n"
        "1. Isolamento de Contexto e Confidencialidade (LGPD):\n"
        "   - Sua janela de contexto NÃO CONTEM nomes reais, CPFs, URLs ou imagens de documentos.\n"
        "   - NUNCA tente inventar, prever ou solicitar dados pessoais identificáveis (PII) do solicitante.\n\n"
        "2. Tratamento de Renda Zero ou Não Comprovada:\n"
        "   - Se income_value for igual a 0, null, menor que zero, ou se o income_confirmed for falso na etapa anterior:\n"
        "     - Defina income_commitment_ratio como 1.0 (100% de comprometimento).\n"
        "     - Defina internal_score como 0.\n"
        "     - Defina risk_tier como \"high\".\n"
        "     - Defina default_probability como 0.99.\n"
        "     - Retorne com status: \"ok\".\n\n"
        "3. Avaliação da Capacidade de Pagamento (Aritmética Determinística):\n"
        "   - Você DEVE acionar a ferramenta do seu servidor MCP dedicada a rodar o motor analítico de risco: evaluate_risk_model.\n"
        "   - Se a chamada à ferramenta MCP falhar persistentemente (error ou timeout) após as tentativas regulamentares:\n"
        "     - Retorne IMEDIATAMENTE um JSON com status: \"error\" e reason: \"risk_calculation_failed\".\n"
        "     - Não infira ou estime o risco de forma autônoma em caso de falha sistêmica.\n\n"
        "FORMATO DE SAÍDA EXCLUSIVO (Você DEVE retornar APENAS este objeto JSON válido, sem qualquer outro texto ou markdown fora dele):\n\n"
        "{\n"
        "  \"request_id\": \"string (UUID correspondente ao input)\",\n"
        "  \"internal_score\": number,\n"
        "  \"default_probability\": number,\n"
        "  \"risk_tier\": \"low | medium | high\",\n"
        "  \"income_commitment_ratio\": number,\n"
        "  \"status\": \"ok | error\",\n"
        "  \"reason\": \"string | null\",\n"
        "  \"processing_time_ms\": number\n"
        "}"
    )

# ─────────────────────────────────────────────────────────────────────────────
# Gemini client apontando para o Sensedia AI Gateway
# ─────────────────────────────────────────────────────────────────────────────

def build_llm_client() -> OpenAI:
    token = gateway_auth.get_token()
    llm_base_url = os.environ["AI_GATEWAY_LLM_BASE_URL"]
    if llm_base_url.endswith("/chat/completions"):
        llm_base_url = llm_base_url[:-len("/chat/completions")]

    return OpenAI(
        base_url=llm_base_url,
        api_key="not-used",
        default_headers={"Authorization": f"Bearer {token}"},
    )

# ─────────────────────────────────────────────────────────────────────────────
# Fluxo Híbrido/Colapsado do Agente de Risco
# ─────────────────────────────────────────────────────────────────────────────

def run_risk_agent(scenario: str, requested_amount: float, request_id: str = None) -> dict:
    if not request_id:
        request_id = str(uuid.uuid4())[:8]
    start = time.time()

    print(f"\n{'='*60}")
    print(f"  [AgentRisk] request_id : {request_id}")
    print(f"  [AgentRisk] cenário    : {scenario}")
    print(f"  [AgentRisk] solicitado : R$ {requested_amount:.2f}")
    print(f"{'='*60}\n")

    agents = MockAgents(scenario=scenario)
    client = build_llm_client()
    system = load_risk_prompt()

    # Recupera informações mockadas das etapas anteriores
    bureau_res = agents.bureau_get_score(applicant_masked_cpf="XXX.XXX.XXX-99", request_id=request_id)
    bureau_score = bureau_res.get("score", 0) or 0
    
    docs_res = agents.documents_validate(document_urls=[], applicant_name="João da Silva", request_id=request_id)
    income_value = docs_res.get("income_value", 0.0) or 0.0

    user_message = (
        f"{{\n"
        f"  \"bureau_score\": {bureau_score},\n"
        f"  \"income_value\": {income_value},\n"
        f"  \"requested_amount\": {requested_amount},\n"
        f"  \"request_id\": \"{request_id}\"\n"
        f"}}"
    )

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user_message}
    ]

    # --- TURNO 1: LLM propõe a primeira ferramenta ---
    print("  [llm] Turno 1: Solicitando decisão inicial (espera-se proposta de ferramenta)...")
    response = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        tools=TOOLS,
        temperature=0,
    )

    choice = response.choices[0]
    msg = choice.message

    if not msg.tool_calls:
        print("  [llm] Turno 1 retornou decisão direta sem ferramentas.")
        text = msg.content
        try:
            return json.loads(text)
        except:
            return {"error": "Falha na análise", "content": text}

    print(f"  [llm] Turno 1 propôs {len(msg.tool_calls)} ferramentas: {[tc.function.name for tc in msg.tool_calls]}")

    executed_tools = []
    # Chama o mock de cálculo de risco
    risk_res = agents.risk_evaluate(
        bureau_score=bureau_score,
        income_value=income_value,
        requested_amount=requested_amount,
        request_id=request_id
    )
    
    executed_tools.append(("evaluate_risk_model", risk_res))

    # Reconstrói a conversa
    collapsed_tool_calls = []
    collapsed_tool_responses = []

    for name, result in executed_tools:
        tc_id = f"call_{str(uuid.uuid4())[:8]}_{name}"
        collapsed_tool_calls.append({
            "id": tc_id,
            "type": "function",
            "function": {
                "name": name,
                "arguments": json.dumps({"bureau_score": bureau_score, "income_value": income_value, "requested_amount": requested_amount})
            }
        })
        collapsed_tool_responses.append({
            "role": "tool",
            "tool_call_id": tc_id,
            "name": name,
            "content": json.dumps(result)
        })

    messages.append({
        "role": "assistant",
        "content": None,
        "tool_calls": collapsed_tool_calls
    })
    messages.extend(collapsed_tool_responses)

    # --- TURNO 2: Síntese da Decisão Final (Modo JSON) ---
    print("  [llm] Turno 2: Enviando histórico completo de ferramenta para síntese...")
    
    response = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        tools=None,
        response_format={"type": "json_object"},
        temperature=0,
    )

    choice = response.choices[0]
    msg = choice.message
    print(f"  [llm] Turno 2 finish_reason={choice.finish_reason}")

    text = msg.content
    if text:
        i = text.find("{")
        j = text.rfind("}") + 1
        if i >= 0 and j > i:
            try:
                result = json.loads(text[i:j])
                result["processing_time_ms"] = int((time.time() - start) * 1000)
                result["trace_id"] = request_id
                return result
            except json.JSONDecodeError:
                pass
        return {
            "raw_response": text,
            "processing_time_ms": int((time.time() - start) * 1000),
        }

    return {
        "error": "Turno 2 encerrado sem decisão",
        "processing_time_ms": int((time.time() - start) * 1000),
    }

# ─────────────────────────────────────────────────────────────────────────────
# CLI Entry Point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Agente de Risco (AgentRisk) — Walking Skeleton"
    )
    parser.add_argument(
        "--scenario", default="auto_approve",
        choices=list(MockAgents.SCENARIOS.keys()) if hasattr(MockAgents, "SCENARIOS") else None,
        help="Cenário de demo",
    )
    parser.add_argument(
        "--amount", type=float, default=20000.0,
        help="Valor do crédito solicitado"
    )
    args = parser.parse_args()

    try:
        decision = run_risk_agent(scenario=args.scenario, requested_amount=args.amount)
        print("\n============================================================")
        print("  DECISÃO FINAL DO AGENTE DE RISCO")
        print("============================================================")
        print(json.dumps(decision, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"❌ Erro na execução do agente: {e}", file=sys.stderr)
