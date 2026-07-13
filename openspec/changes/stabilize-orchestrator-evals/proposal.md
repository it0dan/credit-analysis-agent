# Proposal — Estabilizar os evals do orquestrador

## Problema
A suíte principal encerrava com 5/13 devido a respostas 503 transitórias e ao uso do mesmo LLM para gerar e julgar respostas que já seguem um contrato JSON explícito.

## Solução
Validar os treze cenários com asserções determinísticas de contrato, reduzir a pressão concorrente no Gateway e tornar as retentativas do cliente configuráveis por ambiente.

## Resultado Esperado
O runner unificado deve concluir a suíte principal com 13/13 de forma reproduzível, sem reduzir a cobertura das regras de compliance, fallback, segurança, fluxo feliz e HITL.
