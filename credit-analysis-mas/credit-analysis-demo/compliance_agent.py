"""
compliance_agent.py
Agente de Compliance (AgentCompliance) independente.
Roda o fluxo do sub-agente regulatório sob o Sensedia AI Gateway.

Rastreabilidade:
  add-compliance-agent/specs/compliance-agent/spec.md
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
# Definição das Ferramentas MCP (mcp-kyc) para o OpenAI SDK
# ─────────────────────────────────────────────────────────────────────────────

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "verify_kyc",
            "description": "Verifica identidade do solicitante junto ao bureau de KYC",
            "parameters": {
                "type": "object",
                "properties": {
                    "applicant_masked_cpf": {"type": "string"},
                    "request_id": {"type": "string"}
                },
                "required": ["applicant_masked_cpf", "request_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_pld",
            "description": "Verifica solicitante em listas de PLD/COAF e sanções internacionais",
            "parameters": {
                "type": "object",
                "properties": {
                    "applicant_masked_cpf": {"type": "string"},
                    "request_id": {"type": "string"}
                },
                "required": ["applicant_masked_cpf", "request_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "verify_lgpd_consent",
            "description": "Confirma registro de consentimento LGPD coletado no canal de origem",
            "parameters": {
                "type": "object",
                "properties": {
                    "applicant_masked_cpf": {"type": "string"},
                    "request_id": {"type": "string"}
                },
                "required": ["applicant_masked_cpf", "request_id"]
            }
        }
    }
]

# ─────────────────────────────────────────────────────────────────────────────
# Carrega system prompt do arquivo SPDD do change
# ─────────────────────────────────────────────────────────────────────────────

def load_compliance_prompt() -> str:
    paths_to_try = [
        os.path.join(
            os.path.dirname(__file__), "..",
            "credit-analysis-openspec", "openspec",
            "changes", "add-compliance-agent", "prompt.md",
        ),
        os.path.join(
            os.path.dirname(__file__), "..",
            "credit-analysis-openspec", "openspec",
            "changes", "archive", "add-compliance-agent", "prompt.md",
        ),
        # Fallback local
        os.path.join(os.path.dirname(__file__), "prompt.md")
    ]
    for prompt_path in paths_to_try:
        if os.path.exists(prompt_path):
            with open(prompt_path) as f:
                content = f.read()
                if "Você é o AgentCompliance" in content:
                    return content

    # Fallback inline rigoroso
    return (
        "Você é o AgentCompliance do sistema de análise de crédito.\n"
        "Seu objetivo é verificar KYC, PLD e consentimento LGPD do solicitante e retornar o resultado contratual ao orquestrador.\n\n"
        "REGRAS DE DECISÃO ABSOLUTAS (Aplique em ordem estrita de prioridade):\n\n"
        "1. Falha Técnica — PRIORIDADE MÁXIMA E ABSOLUTA:\n"
        "   - Se qualquer ferramenta MCP (verify_kyc, check_pld, verify_lgpd_consent) retornar status \"error\", \"timeout\", resposta malformada ou campo obrigatório ausente: RECUSE IMEDIATAMENTE.\n"
        "   - O status de saída deve ser OBRIGATORIAMENTE \"rejected\".\n"
        "   - O campo \"reason\" deve ser preenchido com a string exata correspondente:\n"
        "     * \"kyc_timeout\" se verify_kyc der timeout.\n"
        "     * \"kyc_unavailable\" se verify_kyc der erro ou resposta malformada.\n"
        "     * \"pld_timeout\" se check_pld der timeout.\n"
        "     * \"pld_unavailable\" se check_pld der erro.\n"
        "     * \"lgpd_timeout\" se verify_lgpd_consent der timeout.\n"
        "     * \"lgpd_unavailable\" se verify_lgpd_consent der erro.\n"
        "   - NUNCA interprete ausência de campo como aprovação. NUNCA escale para HITL. NUNCA faça retry.\n"
        "   - Esta regra se aplica a qualquer ferramenta, em qualquer etapa da sequência.\n\n"
        "2. Verificação KYC — PRIORIDADE 2:\n"
        "   - Chame verify_kyc PRIMEIRO, antes de qualquer outra ferramenta.\n"
        "   - Se verify_kyc retornar kyc_approved: false: RECUSE IMEDIATAMENTE com reason \"kyc_failed\".\n"
        "   - NÃO chame check_pld nem verify_lgpd_consent após KYC negativo (short-circuit obrigatório).\n"
        "   - NUNCA escale para HITL por KYC negativo.\n\n"
        "3. Verificação PLD — PRIORIDADE 3 (apenas se KYC aprovado):\n"
        "   - Chame check_pld somente após verify_kyc retornar kyc_approved: true.\n"
        "   - Se check_pld retornar pld_clear: false: RECUSE IMEDIATAMENTE com reason \"pld_positive\".\n"
        "   - NÃO chame verify_lgpd_consent após PLD positivo (short-circuit obrigatório).\n"
        "   - NUNCA escale para HITL por PLD positivo.\n\n"
        "4. Verificação LGPD — PRIORIDADE 4 (apenas se KYC e PLD aprovados):\n"
        "   - Chame verify_lgpd_consent somente após verify_kyc e check_pld retornarem aprovação.\n"
        "   - Se verify_lgpd_consent retornar lgpd_consent: false: RECUSE IMEDIATAMENTE com reason \"lgpd_no_consent\".\n"
        "   - NUNCA escale para HITL por ausência de consentimento LGPD.\n\n"
        "5. Aprovação — PRIORIDADE 5 (apenas se todas as verificações anteriores aprovadas):\n"
        "   - Se verify_kyc retornar kyc_approved: true E check_pld retornar pld_clear: true E verify_lgpd_consent retornar lgpd_consent: true: retorne status \"ok\" com todos os campos de aprovação como true.\n\n"
        "REGRA INVIOLÁVEL SOBRE HITL:\n"
        "O AgentCompliance NUNCA retorna status \"pending_human_review\" ou qualquer variante de escalada humana.\n"
        "Não existe cenário em que compliance falha e o resultado é \"encaminhar para analista\".\n"
        "Falha de compliance = recusa imediata. Sem exceção. Sem override.\n\n"
        "FORMATO DE SAÍDA EXCLUSIVO (Você DEVE retornar APENAS este objeto JSON válido, sem qualquer outro texto ou markdown fora dele):\n"
        "{\n"
        "  \"request_id\": \"string (UUID recebido no input)\",\n"
        "  \"kyc_approved\": boolean,\n"
        "  \"pld_clear\": boolean,\n"
        "  \"lgpd_consent\": boolean,\n"
        "  \"status\": \"ok | rejected | error | timeout\",\n"
        "  \"reason\": \"kyc_failed | kyc_unavailable | kyc_timeout | pld_positive | pld_unavailable | pld_timeout | lgpd_no_consent | lgpd_unavailable | lgpd_timeout | null\",\n"
        "  \"tools_called\": [\"string\"],\n"
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
# Fluxo Híbrido/Colapsado do Agente de Compliance
# ─────────────────────────────────────────────────────────────────────────────

def run_compliance_agent(scenario: str, request_id: str = None) -> dict:
    if not request_id:
        request_id = str(uuid.uuid4())
    masked_cpf = "XXX.XXX.XXX-99"
    start = time.time()

    print(f"\n{'='*60}")
    print(f"  [AgentCompliance] request_id : {request_id}")
    print(f"  [AgentCompliance] cenário    : {scenario}")
    print(f"{'='*60}\n")

    agents = MockAgents(scenario=scenario)
    client = build_llm_client()
    system = load_compliance_prompt()

    user_message = (
        f"{{\n"
        f"  \"applicant_masked_cpf\": \"{masked_cpf}\",\n"
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
        # Se não chamou ferramenta, retorna o JSON direto (ex: erro rápido ou decisão direta)
        print("  [llm] Turno 1 retornou decisão direta sem ferramentas.")
        text = msg.content
        try:
            return json.loads(text)
        except:
            return {"error": "Falha na análise", "content": text}

    # Interceptamos as ferramentas propostas e rodamos o fluxo colapsado local em Python
    print(f"  [llm] Turno 1 propôs {len(msg.tool_calls)} ferramentas: {[tc.function.name for tc in msg.tool_calls]}")

    # Execução sequencial local das ferramentas simulando a lógica da Spec (Short-Circuit)
    executed_tools = []
    
    # 1. Executa verify_kyc
    print("  [tool] Executando verify_kyc localmente...")
    kyc_res = agents.verify_kyc(applicant_masked_cpf=masked_cpf, request_id=request_id)
    executed_tools.append(("verify_kyc", kyc_res))

    kyc_ok = kyc_res.get("status") == "ok" and kyc_res.get("kyc_approved") is True

    # 2. Se KYC ok, executa check_pld
    pld_res = None
    if kyc_ok:
        print("  [tool] KYC aprovado. Executando check_pld localmente...")
        pld_res = agents.check_pld(applicant_masked_cpf=masked_cpf, request_id=request_id)
        executed_tools.append(("check_pld", pld_res))
    else:
        print("  [short-circuit] KYC não aprovado ou indisponível. Interrompendo sequência.")

    pld_ok = pld_res and pld_res.get("status") == "ok" and pld_res.get("pld_clear") is True

    # 3. Se PLD ok, executa verify_lgpd_consent
    lgpd_res = None
    if kyc_ok and pld_ok:
        print("  [tool] PLD aprovado. Executando verify_lgpd_consent localmente...")
        lgpd_res = agents.verify_lgpd_consent(applicant_masked_cpf=masked_cpf, request_id=request_id)
        executed_tools.append(("verify_lgpd_consent", lgpd_res))
    elif kyc_ok:
        print("  [short-circuit] PLD não aprovado ou indisponível. Interrompendo sequência.")

    # Programmatic history rebuild: Consolidamos todas as execuções em um único turno colapsado
    # Isso evita totalmente a falha de múltiplos turnos sequenciais do Gateway de IA.
    collapsed_tool_calls = []
    collapsed_tool_responses = []

    for name, result in executed_tools:
        tc_id = f"call_{str(uuid.uuid4())[:8]}_{name}"
        # Registra a chamada
        collapsed_tool_calls.append({
            "id": tc_id,
            "type": "function",
            "function": {
                "name": name,
                "arguments": json.dumps({"applicant_masked_cpf": masked_cpf, "request_id": request_id})
            }
        })
        # Registra o retorno
        collapsed_tool_responses.append({
            "role": "tool",
            "tool_call_id": tc_id,
            "name": name,
            "content": json.dumps(result)
        })

    # Reconstrói a conversa
    messages.append({
        "role": "assistant",
        "content": None,
        "tool_calls": collapsed_tool_calls
    })
    messages.extend(collapsed_tool_responses)

    # --- TURNO 2: Síntese da Decisão Final (Modo JSON) ---
    print("  [llm] Turno 2: Enviando histórico completo de ferramentas para síntese do resultado contratual...")
    
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
        description="Agente de Compliance (AgentCompliance) — Walking Skeleton"
    )
    parser.add_argument(
        "--scenario", default="auto_approve",
        choices=["auto_approve", "hitl_required", "compliance_fail", "bureau_error"],
        help="Cenário de demo",
    )
    args = parser.parse_args()

    result = run_compliance_agent(scenario=args.scenario)

    print(f"\n{'='*60}")
    print("  RESULTADO CONTRATUAL DO COMPLIANCE")
    print(f"{'='*60}")
    print(json.dumps(result, indent=2, ensure_ascii=False))
