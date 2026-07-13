# Specification — Estabilizar os evals do orquestrador

## Requisitos

### Suíte principal
* Deve executar os 13 cenários descritos em `evals/orchestrator.yaml`.
* Deve validar deterministicamente o contrato JSON e as regras de compliance, fallback, segurança, fluxo feliz e HITL.
* Não deve depender de um segundo julgamento por LLM.

### Runner
* Deve habilitar retentativas para respostas HTTP 5xx.
* Deve permitir configurar backoff, concorrência, intervalo entre chamadas e máximo de retentativas.
* Deve usar padrões conservadores para reduzir a pressão sobre o AI Gateway.
* Deve renovar o token do Gateway antes de executar cada arquivo de configuração.
* Deve aceitar uma lista opcional de configurações por argumento e manter a suíte completa como padrão.

### Cliente do orquestrador
* Deve ler `AI_GATEWAY_MAX_RETRIES` como inteiro.
* Deve usar 4 retentativas quando a variável não estiver definida.
