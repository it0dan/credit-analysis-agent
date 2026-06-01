"""
bureau_agent.py
Agente de Bureau (AgentBureau) independente.
Roda o fluxo do sub-agente de dados externos sob o Sensedia AI Gateway.

Rastreabilidade:
  add-bureau-agent/specs/bureau-agent/spec.md
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
# Definição das Ferramentas MCP (mcp-bureau) para o OpenAI SDK
# ─────────────────────────────────────────────────────────────────────────────

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_score",
            "description": "Consulta score de crédito e restrições ativas no Serasa/SPC",
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

def load_bureau_prompt() -> str:
    paths_to_try = [
        os.path.join(
            os.path.dirname(__file__), "..",
            "openspec",
            "changes", "add-bureau-agent", "prompt.md",
        ),
        os.path.join(
            os.path.dirname(__file__), "..",
            "openspec",
            "changes", "archive", "add-bureau-agent", "prompt.md",
        ),
        # Fallback local
        os.path.join(os.path.dirname(__file__), "prompt.md")
    ]
    for prompt_path in paths_to_try:
        if os.path.exists(prompt_path):
            with open(prompt_path) as f:
                content = f.read()
                if "Você é o AgentBureau" in content:
                    return content

    # Fallback inline rigoroso
    return (
        "Você é o AgentBureau do sistema de análise de crédito.\n"
        "Seu objetivo é consultar o score de crédito e restrições ativas do solicitante via mcp-bureau e retornar os dados brutos ao orquestrador.\n\n"
        "REGRAS DE DECISÃO ABSOLUTAS (Aplique em ordem estrita de prioridade):\n\n"
        "1. Falha Técnica Persistente — PRIORIDADE MÁXIMA E ABSOLUTA:\n"
        "   - Se get_score falhar (status \"error\" ou \"timeout\") nas 3 tentativas (1 original + 2 retries): retorne IMEDIATAMENTE com status \"error\" e reason \"bureau_unavailable\".\n"
        "   - Execute os retries com backoff: aguarde 1s após a tentativa 1, 2s após a tentativa 2.\n"
        "   - NUNCA invente, estime ou infira score após esgotamento de tentativas.\n"
        "   - NUNCA retorne status \"ok\" se a consulta não foi bem-sucedida.\n"
        "   - O campo \"attempts\" deve refletir quantas tentativas foram feitas (1, 2 ou 3).\n\n"
        "2. Consulta Bem-sucedida — PRIORIDADE 2:\n"
        "   - Se get_score retornar status \"ok\" em qualquer tentativa: retorne IMEDIATAMENTE os dados brutos com status \"ok\".\n"
        "   - Retorne score, restrictions, bureau_source e consulted_at exatamente como recebidos do mcp-bureau.\n"
        "   - NUNCA aplique regras de negócio sobre o score. Score baixo, restrições ativas ou qualquer combinação de dados desfavoráveis NÃO resultam em recusa — você apenas repassa os dados.\n"
        "   - NUNCA adicione campos como \"decision\", \"recommendation\" ou \"risk_assessment\" ao output.\n\n"
        "3. Isolamento de Contexto e Privacidade:\n"
        "   - NUNCA exponha CPF real em qualquer campo do output.\n"
        "   - O output não possui campo de CPF — use request_id para referenciar o solicitante.\n"
        "   - NUNCA processe dados de outros sub-agentes. Sua única fonte é o mcp-bureau.\n\n"
        "FORMATO DE SAÍDA EXCLUSIVO (Você DEVE retornar APENAS este objeto JSON válido, sem qualquer outro texto ou markdown fora dele):\n\n"
        "Em caso de sucesso:\n"
        "{\n"
        "  \"request_id\": \"string (UUID recebido no input)\",\n"
        "  \"score\": number (0–1000),\n"
        "  \"restrictions\": [\"string\"],\n"
        "  \"bureau_source\": \"serasa | spc | both\",\n"
        "  \"consulted_at\": \"string (ISO 8601)\",\n"
        "  \"status\": \"ok\",\n"
        "  \"reason\": null,\n"
        "  \"attempts\": number (1–3),\n"
        "  \"processing_time_ms\": number,\n"
        "  \"trace_id\": \"string (= request_id)\"\n"
        "}\n\n"
        "Em caso de erro (após 3 tentativas):\n"
        "{\n"
        "  \"request_id\": \"string (UUID recebido no input)\",\n"
        "  \"score\": null,\n"
        "  \"restrictions\": null,\n"
        "  \"bureau_source\": null,\n"
        "  \"consulted_at\": null,\n"
        "  \"status\": \"error\",\n"
        "  \"reason\": \"bureau_unavailable\",\n"
        "  \"attempts\": number (1–3),\n"
        "  \"processing_time_ms\": number,\n"
        "  \"trace_id\": \"string (= request_id)\"\n"
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
# Fluxo Híbrido/Colapsado do Agente de Bureau
# ─────────────────────────────────────────────────────────────────────────────

def run_bureau_agent(scenario: str, request_id: str = None, bureau_attempts: list[dict] = None) -> dict:
    if not request_id:
        request_id = str(uuid.uuid4())
    masked_cpf = "XXX.XXX.XXX-99"
    start = time.time()

    print(f"\n{'='*60}")
    print(f"  [AgentBureau] request_id : {request_id}")
    print(f"  [AgentBureau] cenário    : {scenario}")
    print(f"{'='*60}\n")

    agents = MockAgents(scenario=scenario, bureau_attempts=bureau_attempts)
    client = build_llm_client()
    system = load_bureau_prompt()

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
        print("  [llm] Turno 1 retornou decisão direta sem ferramentas.")
        text = msg.content
        try:
            return json.loads(text)
        except:
            return {"error": "Falha na análise", "content": text}

    print(f"  [llm] Turno 1 propôs {len(msg.tool_calls)} ferramentas: {[tc.function.name for tc in msg.tool_calls]}")

    # Execução sequencial local com retry (2x backoff: 1s, 2s)
    executed_tools = []
    attempts = 0
    max_attempts = 3
    backoff_times = [1, 2]
    
    bureau_res = None

    while attempts < max_attempts:
        attempts += 1
        print(f"  [tool] Tentativa {attempts} de {max_attempts}: Executando get_score localmente...")
        bureau_res = agents.bureau_get_score(applicant_masked_cpf=masked_cpf, request_id=request_id)
        
        if bureau_res.get("status") == "ok":
            print(f"  [tool] Tentativa {attempts} bem-sucedida!")
            break
        else:
            print(f"  [tool] Tentativa {attempts} falhou com erro: {bureau_res.get('error', 'desconhecido') or bureau_res.get('reason')}")
            if attempts < max_attempts:
                wait_time = backoff_times[attempts - 1]
                print(f"  [backoff] Aguardando {wait_time}s antes da tentativa {attempts + 1}...")
                time.sleep(wait_time)

    # Injeta a quantidade de tentativas na resposta final da ferramenta para orientar a síntese do LLM
    bureau_res["attempts"] = attempts
    executed_tools.append(("get_score", bureau_res))

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
                "arguments": json.dumps({"applicant_masked_cpf": masked_cpf, "request_id": request_id})
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
                # Garante os campos obrigatórios da spec
                result["attempts"] = attempts
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
        description="Agente de Bureau (AgentBureau) — Walking Skeleton"
    )
    parser.add_argument(
        "--scenario", default="auto_approve",
        choices=list(MockAgents.SCENARIOS.keys()) if hasattr(MockAgents, "SCENARIOS") else None,
        help="Cenário de demo",
    )
    args = parser.parse_args()

    result = run_bureau_agent(scenario=args.scenario)

    print(f"\n{'='*60}")
    print("  RESULTADO CONTRATUAL DO BUREAU")
    print(f"{'='*60}")
    print(json.dumps(result, indent=2, ensure_ascii=False))
