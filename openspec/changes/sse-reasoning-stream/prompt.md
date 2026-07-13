# Prompt de Retomada — SSE reasoning stream (`credit-analysis-agent`)

Este arquivo serve como contexto para retomar o desenvolvimento da funcionalidade de Server-Sent Events (SSE) do orquestrador multiagente.

## Escopo
Substituir a simulação baseada em temporizadores do frontend por eventos reais e em tempo real emitidos pelo orquestrador no backend por meio do endpoint `/analysis/:id/events`.

## Tarefas Pendentes
1. Criar o arquivo `src/sse_stream.py`.
2. Adicionar a tabela `analysis_events` e os métodos de persistência em `src/db.py`.
3. Injetar as chamadas de emissão de eventos SSE e salvamento no banco de dados nas etapas correspondentes do orquestrador (`src/orchestrator.py`).
4. Implementar o endpoint HTTP `GET /analysis/:id/events` e garantir a criação prévia do canal no `POST /analysis` no servidor `src/resume_endpoint.py`.
5. Validar o fluxo com curls de teste e a suíte `./run_all_evals.sh`.
