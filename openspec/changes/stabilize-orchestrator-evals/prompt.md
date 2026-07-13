# Prompt de Retomada — Estabilizar os evals do orquestrador

O objetivo é tornar a execução do Promptfoo resistente a indisponibilidades transitórias do AI Gateway sem enfraquecer os contratos funcionais. A suíte principal usa asserções determinísticas sobre JSON; o runner controla concorrência, intervalo, backoff e retentativas por variáveis de ambiente. Antes de concluir, execute `./run_all_evals.sh` e as validações locais do backend.
