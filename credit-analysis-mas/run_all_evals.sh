#!/bin/bash
# run_all_evals.sh — Executa a avaliação individual de todos os agentes.
# Isso evita que o PromptFoo mescle as configurações e execute testes de um agente contra os prompts de outros.

echo "=========================================================="
echo "   Iniciando Execução de Evals Multiagente (PromptFoo)     "
echo "=========================================================="

# 1. Obter Token do Sensedia AI Gateway
echo "Obtendo token de acesso do Sensedia AI Gateway..."
cd credit-analysis-demo
TOKEN=$(.venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); from gateway_auth import gateway_auth; print(gateway_auth.get_token())")
cd ..

if [ -z "$TOKEN" ] || [ ${#TOKEN} -lt 20 ]; then
  echo "❌ Erro: Não foi possível obter o token do gateway. Verifique as credenciais em credit-analysis-demo/.env."
  exit 1
fi

echo "✅ Token do Gateway obtido com sucesso!"
export AI_GATEWAY_TOKEN=$TOKEN

# 2. Configurações individuais
CONFIGS=(
  "credit-analysis-demo/evals/orchestrator.yaml"
  "credit-analysis-openspec/openspec/changes/archive/add-bureau-agent/evals/bureau.yaml"
  "credit-analysis-openspec/openspec/changes/archive/add-documents-agent/evals/documents.yaml"
  "credit-analysis-openspec/openspec/changes/archive/add-compliance-agent/evals/compliance.yaml"
  "credit-analysis-openspec/openspec/changes/archive/add-risk-agent/evals/risk.yaml"
  "credit-analysis-openspec/openspec/changes/archive/add-decision-agent/evals/decision.yaml"
)

# 3. Execução individualizada
for CONFIG in "${CONFIGS[@]}"; do
  echo ""
  echo "----------------------------------------------------------"
  echo "🚀 Executando eval para: $CONFIG"
  echo "----------------------------------------------------------"
  
  if [ ! -f "$CONFIG" ]; then
    echo "⚠️  Arquivo não encontrado, pulando: $CONFIG"
    continue
  fi

  npx promptfoo eval --config "$CONFIG"
  
  if [ $? -eq 0 ]; then
    echo "✅ Sucesso para: $CONFIG"
  else
    echo "❌ Falhas encontradas para: $CONFIG"
  fi
done

echo ""
echo "=========================================================="
echo "🎉 Execuções concluídas!"
echo "Rode 'npx promptfoo view' para abrir o dashboard consolidado."
echo "=========================================================="
