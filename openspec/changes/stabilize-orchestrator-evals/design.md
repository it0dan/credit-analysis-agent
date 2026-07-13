# Design — Estabilizar os evals do orquestrador

## Validação de contrato
Cada `llm-rubric` da suíte principal é substituído por uma asserção JavaScript que desserializa o output e verifica os campos e invariantes correspondentes. As verificações existentes de conteúdo e JSON válido são preservadas.

## Controle de carga
`run_all_evals.sh` passa `--max-concurrency` e `--delay` ao Promptfoo. Os padrões são, respectivamente, 1 e 1000 ms, com override pelas variáveis `EVAL_MAX_CONCURRENCY` e `EVAL_DELAY_MS`.

Como a serialização aumenta a duração total além do TTL típico do JWT, o runner solicita e exporta um token novo imediatamente antes de cada configuração.
O runner aceita caminhos de configuração como argumentos para permitir a retomada seletiva; sem argumentos, executa a lista completa.

## Retentativas
O runner habilita retentativa de HTTP 5xx e backoff no Promptfoo. O cliente OpenAI criado pelo orquestrador lê `AI_GATEWAY_MAX_RETRIES`; a aplicação mantém o padrão 4 e o runner usa 8 para absorver indisponibilidades transitórias durante execuções longas.
