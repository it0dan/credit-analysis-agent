# Design — SSE reasoning stream (`credit-analysis-agent`)

## Detalhamento Arquitetural

### Decisão 1 — Canal SSE por `request_id` (não broadcast)
* **Abordagem**: Criar um módulo especializado `sse_stream.py` contendo um mapeamento global `_channels: dict[str, list[queue.Queue]]` protegido por um `threading.Lock()`.
* **Fluxo**:
  * Ao chamar `create_channel(request_id)`, inicializamos uma entrada vazia no mapa.
  * Quando um cliente abre `GET /analysis/:id/events`, ele é registrado via `register_client(request_id)` que cria e adiciona uma fila (`queue.Queue`) à lista correspondente.
  * Cada evento postado via `emit_event(request_id, event)` é propagado a todas as filas ativas do respectivo `request_id` via `put_nowait` (non-blocking).
  * O canal é destruído e os clientes desconectados graciosamente via sinalizadores (sentinel `None`) quando `close_channel(request_id)` é acionado ao fim do ciclo de vida da análise.

```
[Orquestrador] ───(emit_event)───► [sse_stream.py] ───(put_nowait)───► [Queue de Clientes] ───► [Browser (GET /events)]
```

### Decisão 2 — Emissão no loop puro
* **Abordagem**: Inserir ganchos de observabilidade no `orchestrator.py` em momentos estratégicos:
  1. **Início da Análise**: Logo antes do loop de chamadas do LLM, emitir o evento `analysis_started`.
  2. **Início da Execução da Ferramenta**: Imediatamente antes de chamar `execute_tool(name, ...)`, determinar a fase lógica (`T1`, `T2` ou `T3`) e disparar o evento `agent_started`.
  3. **Conclusão da Ferramenta**: Logo após o retorno de `execute_tool(...)`, capturar a latência real, formatar os dados de saída seguros (score do bureau, tier de risco, kyc de compliance) e disparar `agent_completed`.
  4. **Short-circuit / HITL**: Em `serialize_and_pause`, emitir `hitl_required` antes de fechar o canal.
  5. **Conclusão de Análise**: Em `save_episodic_memory`, antes de fechar o canal, disparar `analysis_done`.
* **Invariante**: Nenhuma condicional de fluxo ou lógica de controle do loop é alterada. O orquestrador continua a rodar linearmente e delega o envio de progresso a funções assíncronas/não-bloqueantes.

### Decisão 3 — Inicialização do Canal Sincronizada com Thread do Orquestrador
* **Abordagem**: O endpoint `POST /analysis` no servidor HTTP de retomada (`resume_endpoint.py`) cria o canal SSE via `sse_stream.create_channel(request_id)` **sincronamente** antes de disparar a thread que executa o orquestrador multiagente.
* **Benefício**: Evita race conditions onde o cliente tenta se inscrever em `GET /analysis/:id/events` antes que a thread do orquestrador tenha iniciado/declarado o canal.

### Decisão 4 — Replay do SQLite
* **Abordagem**: Criar uma tabela `analysis_events` no SQLite (`credit_analysis.db`) para registrar o log ordenado de eventos gerados em cada análise.
* **Fluxo**:
  * Ao emitir eventos como `agent_completed`, `analysis_done` ou `hitl_required`, eles são salvos no banco por meio de `db.save_event(request_id, event)`.
  * Se o cliente chamar `GET /analysis/:id/events` e o canal correspondente no `sse_stream` não estiver ativo (significando que a análise já encerrou ou expirou), o handler lê os eventos salvos via `db.list_events(request_id)`.
  * Se houver eventos salvos, o handler envia-os em sequência imediata e encerra a resposta HTTP com a sinalização `stream_end`. Caso contrário, retorna `404 Not Found`.
