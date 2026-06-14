import os
import sys
import json
import contextlib

# Add current directory to path so we can import orchestrator properly
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from orchestrator import run_orchestrator

def map_vars(vars_dict):
    scenario = vars_dict.get("scenario")
    amount = vars_dict.get("amount")
    cpf = vars_dict.get("cpf")
    env_override = vars_dict.get("env_override")
    
    # Map CPF to scenario and amount if not specified
    if cpf and not scenario:
        cpf_str = str(cpf).lower()
        if "111" in cpf_str or "compliance_fail" in cpf_str:
            scenario = "compliance_fail"
            amount = 15000.0
        elif "multi_error" in cpf_str:
            scenario = "multi_error"
            amount = 10000.0
        elif "hitl" in cpf_str:
            scenario = "hitl_required"
            amount = 80000.0
        else: # auto_approve_cpf or default
            scenario = "auto_approve"
            amount = 20000.0

    # Defaults
    if not scenario:
        scenario = "auto_approve"
    if not amount:
        amount = 20000.0
        
    try:
        amount = float(amount)
    except Exception:
        amount = 20000.0
        
    return scenario, amount, env_override

def call_api(prompt, options, context):
    test_vars = context.get("vars", {}) if context else {}
    scenario, amount, env_override = map_vars(test_vars)
    
    # Apply environment override if necessary
    original_map = os.environ.get("AI_GATEWAY_JWT_AUDIENCE_MAP")
    if env_override == "no_audience_map" and "AI_GATEWAY_JWT_AUDIENCE_MAP" in os.environ:
        del os.environ["AI_GATEWAY_JWT_AUDIENCE_MAP"]
        
    try:
        # Executa o orquestrador puro redirecionando o stdout das mensagens de log para o stderr
        with contextlib.redirect_stdout(sys.stderr):
            result = run_orchestrator(scenario=scenario, amount=amount)
        return {"output": result}
    except Exception as e:
        return {"output": {"error": str(e)}}
    finally:
        # Restore environment variables
        if env_override == "no_audience_map" and original_map is not None:
            os.environ["AI_GATEWAY_JWT_AUDIENCE_MAP"] = original_map

if __name__ == "__main__":
    scenario = "auto_approve"
    amount = 20000.0
    env_override = None
    
    # Escaneia os argumentos para encontrar o objeto de contexto JSON do PromptFoo
    for arg in sys.argv:
        arg_clean = arg.strip()
        if arg_clean.startswith("{") and arg_clean.endswith("}"):
            try:
                data = json.loads(arg_clean)
                if "vars" in data:
                    test_vars = data["vars"]
                    scenario, amount, env_override = map_vars(test_vars)
                    print(f"  [provider] Variáveis extraídas com sucesso: scenario={scenario}, amount={amount}", file=sys.stderr)
                    break
            except Exception as e:
                pass

    # Apply environment override if necessary
    original_map = os.environ.get("AI_GATEWAY_JWT_AUDIENCE_MAP")
    if env_override == "no_audience_map" and "AI_GATEWAY_JWT_AUDIENCE_MAP" in os.environ:
        del os.environ["AI_GATEWAY_JWT_AUDIENCE_MAP"]

    try:
        with contextlib.redirect_stdout(sys.stderr):
            result = run_orchestrator(scenario=scenario, amount=amount)
        # O único print no stdout será o JSON final
        print(json.dumps(result, ensure_ascii=False))
    except Exception as e:
        print(json.dumps({"error": str(e)}))
    finally:
        # Restore environment variables
        if env_override == "no_audience_map" and original_map is not None:
            os.environ["AI_GATEWAY_JWT_AUDIENCE_MAP"] = original_map
