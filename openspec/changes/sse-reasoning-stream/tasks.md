# Tasks — SSE reasoning stream (`credit-analysis-agent`)

## Planejamento de Implementação

- [x] **Etapa 2.1: Registrar ADR-010**
  - [x] Criar `openspec/adr/ADR-010.md` com status `ACCEPTED`.

- [x] **Etapa 2.2: Criar Módulo `src/sse_stream.py`**
  - [x] Implementar a estrutura de canais por request_id usando `threading.Lock` e filas de eventos não-bloqueantes.
  - [x] Adicionar helpers `format_sse` e `format_keepalive`.

- [x] **Etapa 2.3: Atualizar Banco SQLite (`src/db.py`)**
  - [x] Modificar `init_db()` para criar a tabela `analysis_events`.
  - [x] Criar funções `save_event(request_id, event)` e `list_events(request_id)`.

- [x] **Etapa 2.4: Integrar Emissões no Orquestrador (`src/orchestrator.py`)**
  - [x] Importar `sse_stream` e `db`.
  - [x] Emitir `analysis_started` no início de `run_orchestrator`.
  - [x] Emitir `agent_started` antes da chamada de ferramentas.
  - [x] Emitir `agent_completed` e salvar no DB após chamadas de ferramentas.
  - [x] Emitir `analysis_done` e fechar o canal no final de `save_episodic_memory`.
  - [x] Emitir `hitl_required` e fechar o canal em `serialize_and_pause`.

- [x] **Etapa 2.5: Implementar Endpoint no Servidor (`src/resume_endpoint.py`)**
  - [x] Modificar `POST /analysis` para invocar `sse_stream.create_channel(request_id)` sincrono antes da thread.
  - [x] Adicionar rota `GET /analysis/:id/events` com headers `text/event-stream` corretos, suporte a replay do SQLite, loop de keepalive a cada 15s e tratamento correto de desconexão do cliente.
  - [x] Usar `ThreadingHTTPServer` para não bloquear outras requisições durante streams longos.

- [x] **Etapa 3: Validação Técnica**
  - [x] Subir o servidor localmente na porta `8086`.
  - [x] Disparar propostas de crédito e inspecionar a saída do SSE em tempo real via `curl`.
  - [x] Validar o comportamento de replay após a conclusão da análise.
  - [x] Confirmar ausência de PII e CPFs nos eventos.
  - [x] Executar `./run_all_evals.sh` e assegurar que não haja regressão nos testes do Promptfoo.
  - [x] Adicionar testes unitários do canal não-bloqueante, formato SSE e replay SQLite.

### Resultado da revalidação em 2026-07-13

Após estabilizar contratos, concorrência, retentativas e renovação do JWT, a suíte
principal concluiu com 13/13. As demais suítes também passaram: trajetória 6/6,
FinOps 8/8, segurança 5/5, bureau 8/8, documentos 8/8, compliance 13/13,
risco 6/6 e decisão 7/7.
