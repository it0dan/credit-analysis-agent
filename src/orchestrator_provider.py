import os
import sys
import json
import contextlib

# Add current directory to path so we can import orchestrator properly
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from orchestrator import run_orchestrator

if __name__ == "__main__":
    scenario = "auto_approve"
    amount = 20000.0
    
    # Escaneia os argumentos para encontrar o objeto de contexto JSON do PromptFoo
    for arg in sys.argv:
        arg_clean = arg.strip()
        if arg_clean.startswith("{") and arg_clean.endswith("}"):
            try:
                data = json.loads(arg_clean)
                if "vars" in data:
                    test_vars = data["vars"]
                    if "scenario" in test_vars:
                        scenario = str(test_vars["scenario"])
                    if "amount" in test_vars:
                        amount = float(test_vars["amount"])
                    print(f"  [provider] Variáveis extraídas com sucesso: scenario={scenario}, amount={amount}", file=sys.stderr)
                    break
            except Exception as e:
                pass

    # Executa o orquestrador puro redirecionando o stdout das mensagens de log para o stderr,
    # deixando o stdout livre apenas para a resposta JSON final.
    try:
        with contextlib.redirect_stdout(sys.stderr):
            result = run_orchestrator(scenario=scenario, amount=amount)
        # O único print no stdout será o JSON final
        print(json.dumps(result, ensure_ascii=False))
    except Exception as e:
        print(json.dumps({"error": str(e)}))
