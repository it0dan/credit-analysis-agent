#!/bin/bash
# run_evals.sh — Executa a suíte de avaliação com injeção automática do token do gateway.

echo "Obtendo token de acesso do Sensedia AI Gateway..."
TOKEN=$(python3 -c "from dotenv import load_dotenv; load_dotenv(); from gateway_auth import gateway_auth; print(gateway_auth.get_token())" 2>/dev/null)

if [ -z "$TOKEN" ] || [ ${#TOKEN} -lt 20 ]; then
  echo "❌ Erro: Não foi possível obter o token do gateway. Verifique as credenciais no arquivo .env."
  exit 1
fi

echo "✅ Token obtido com sucesso!"
export AI_GATEWAY_TOKEN=$TOKEN

# Executa o PromptFoo (permite passar um arquivo de configuração alternativo como argumento)
CONFIG_FILE=${1:-"evals/promptfoo.yaml"}
npx promptfoo eval --config "$CONFIG_FILE"
