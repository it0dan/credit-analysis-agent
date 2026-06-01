"""
decision_agent.py
Agente de Decisão (AgentDecision) independente.
Roda o fluxo do sub-agente de síntese final sob o Sensedia AI Gateway.

Rastreabilidade:
  add-decision-agent/specs/decision-agent/spec.md
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
# Carrega system prompt do arquivo SPDD do change
# ─────────────────────────────────────────────────────────────────────────────

def load_decision_prompt() -> str:
    paths_to_try = [
        os.path.join(
            os.path.dirname(__file__), "..",
            "openspec",
            "changes", "archive", "add-decision-agent", "prompt.md",
        ),
        os.path.join(
            os.path.dirname(__file__), "..",
            "openspec",
            "changes", "add-decision-agent", "prompt.md",
        ),
        # Fallback local
        os.path.join(os.path.dirname(__file__), "prompt.md")
    ]
    for prompt_path in paths_to_try:
        if os.path.exists(prompt_path):
            with open(prompt_path) as f:
                content = f.read()
                if "Você é o AgentDecision" in content:
                    return content

    # Fallback inline rigoroso
    return (
        "Você é o AgentDecision do sistema de análise de crédito multiagente.\n"
        "Seu objetivo é sintetizar os relatórios analíticos gerados pelas etapas anteriores (bureau_result, documents_result, risk_result, compliance_result) e emitir um veredito de crédito estruturado, auditável e explicável.\n\n"
        "Você DEVE atuar sob estrita conformidade com as regras operacionais abaixo:\n\n"
        "1. Groundedness Rígido (Fatos Reais apenas):\n"
        "   - Toda frase escrita em seu campo justification DEVE ser diretamente derivada de um dado presente nos relatórios de entrada.\n"
        "   - NUNCA alucine, presuma ou insira fatos que não constem nos payloads recebidos.\n\n"
        "2. Transparência nas Justificativas:\n"
        "   - Sua justificativa deve ser clara e legível, indicando explicitamente quais fatores determinaram a decisão.\n"
        "   - Em caso de recusa baseada em Compliance (KYC/PLD), utilize a mensagem genérica: \"Solicitação recusada devido a inconsistências cadastrais ou políticas regulatórias.\"\n\n"
        "3. Regras de Negócio e Veredito (Matriz de Decisão):\n"
        "   - Recusa Mandatória (Rejected): Se compliance_result contiver kyc_approved: false ou pld_clear: false, ou se risk_result contiver risk_tier: \"high\", ou se bureau_result contiver restrições ativas (restrictions não vazio).\n"
        "   - Aprovação Condicionada (Adjusted): Se o risco for médio (risk_tier: \"medium\"), insira condicionalidades no array conditions.\n"
        "   - Aprovação Limpa (Approved): Se tudo estiver regularizado: compliance ok, risk_tier \"low\", sem restrições de bureau e renda confirmada compatível.\n\n"
        "FORMATO DE SAÍDA EXCLUSIVO (Você DEVE retornar APENAS este objeto JSON válido, sem qualquer outro texto ou markdown fora dele):\n\n"
        "{\n"
        "  \"request_id\": \"string (UUID correspondente ao input)\",\n"
        "  \"decision\": \"approved | rejected | adjusted\",\n"
        "  \"confidence\": number,\n"
        "  \"justification\": \"string (máximo 300 caracteres)\",\n"
        "  \"conditions\": [\"string\"],\n"
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
# Fluxo do Agente de Decisão (Modo JSON de Turno Único)
# ─────────────────────────────────────────────────────────────────────────────

def run_decision_agent(scenario: str, requested_amount: float, request_id: str = None) -> dict:
    if not request_id:
        request_id = str(uuid.uuid4())[:8]
    start = time.time()

    print(f"\n{'='*60}")
    print(f"  [AgentDecision] request_id : {request_id}")
    print(f"  [AgentDecision] cenário    : {scenario}")
    print(f"  [AgentDecision] solicitado : R$ {requested_amount:.2f}")
    print(f"{'='*60}\n")

    agents = MockAgents(scenario=scenario)
    client = build_llm_client()
    system = load_decision_prompt()

    # Coleta todos os relatórios mockados simulados das etapas anteriores
    bureau_res = agents.bureau_get_score(applicant_masked_cpf="XXX.XXX.XXX-99", request_id=request_id)
    docs_res = agents.documents_validate(document_urls=[], applicant_name="João da Silva", request_id=request_id)
    risk_res = agents.risk_evaluate(bureau_score=bureau_res.get("score", 0), income_value=docs_res.get("income_value", 0.0), requested_amount=requested_amount, request_id=request_id)
    compliance_res = agents.compliance_check(applicant_masked_cpf="XXX.XXX.XXX-99", request_id=request_id)

    user_message = (
        f"{{\n"
        f"  \"bureau_result\": {json.dumps(bureau_res)},\n"
        f"  \"documents_result\": {json.dumps(docs_res)},\n"
        f"  \"risk_result\": {json.dumps(risk_res)},\n"
        f"  \"compliance_result\": {json.dumps(compliance_res)},\n"
        f"  \"requested_amount\": {requested_amount},\n"
        f"  \"request_id\": \"{request_id}\"\n"
        f"}}"
    )

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user_message}
    ]

    print("  [llm] Turno 1: Enviando todos os relatórios dos sub-agentes para decisão final...")
    response = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        response_format={"type": "json_object"},
        temperature=0,
    )

    choice = response.choices[0]
    msg = choice.message
    print(f"  [llm] Turno 1 finish_reason={choice.finish_reason}")

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
        "error": "Encerramento sem decisão",
        "processing_time_ms": int((time.time() - start) * 1000),
    }

# ─────────────────────────────────────────────────────────────────────────────
# CLI Entry Point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Agente de Decisão (AgentDecision) — Walking Skeleton"
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
        decision = run_decision_agent(scenario=args.scenario, requested_amount=args.amount)
        print("\n============================================================")
        print("  DECISÃO FINAL DO AGENTE DE DECISÃO")
        print("============================================================")
        print(json.dumps(decision, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"❌ Erro na execução do agente: {e}", file=sys.stderr)
