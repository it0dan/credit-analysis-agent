# HANDOFF — Credit Analysis Agent

Atualizado em 2026-07-13.

## Estado do repositório

- Branch: `main`.
- HEAD e `origin/main`: `abdd2f9` (`test(eval): stabilize orchestrator contract suite`).
- Alteração local de runtime preservada: `src/episodic_memory.json`.
- Não incluir, restaurar ou apagar `src/episodic_memory.json` sem revisar seu conteúdo; ele foi alterado por execuções locais e não faz parte das entregas desta sessão.
- Serviço HTTP ativo em `http://localhost:8086`.

## Entregas concluídas

### Persistência SQLite — ADR-009

- `src/db.py` implementa store durável para análises, estados HITL e eventos.
- Seed idempotente a partir de `episodic_memory.json`.
- `hitl_store.py` usa fallback Redis → SQLite → memória.
- Banco local e arquivos auxiliares `src/credit_analysis.db*` permanecem ignorados pelo Git.
- Endpoints de consulta disponíveis:
  - `GET /analyses`
  - `GET /analyses/stats`
  - `GET /analysis/:request_id/status`

### Streaming SSE — ADR-010

- `src/sse_stream.py` mantém canais isolados por `request_id` com lock e filas não bloqueantes.
- O orquestrador emite `analysis_started`, `agent_started`, `agent_completed`, `hitl_required` e `analysis_done`.
- Eventos são persistidos em SQLite para replay.
- `GET /analysis/:request_id/events` entrega replay + eventos ao vivo, keepalive e encerramento correto.
- `POST /analysis` cria o canal antes de iniciar a execução em background.
- `ThreadingHTTPServer` evita bloqueio entre streams e outras requisições.
- Eventos não expõem CPF ou PII.

### Estabilização dos evals — ADR-011

- Rubricas instáveis foram substituídas por contratos determinísticos.
- Runner unificado ganhou serialização, intervalo configurável, retry/backoff e retomada seletiva.
- JWT do Gateway é renovado antes das configurações.
- O loop puro do orquestrador foi preservado; somente a observabilidade de trajetória necessária aos contratos foi adicionada.

## Validação registrada

- Suíte principal: 13/13.
- Trajetória: 6/6.
- FinOps: 8/8.
- Segurança: 5/5.
- Bureau: 8/8.
- Documentos: 8/8.
- Compliance: 13/13.
- Risco: 6/6.
- Decisão: 7/7.
- Testes unitários, compilação Python e validações estáticas passaram.
- Runner completo: `./run_all_evals.sh`.

## Commits relevantes

- `48b9d14 feat(db): add sqlite durable persistence`
- `97ee86e feat(api): stream agent progress over SSE`
- `abdd2f9 test(eval): stabilize orchestrator contract suite`

## Integração com o frontend

- O frontend consome `POST /analysis` em `:8086`.
- Customer e operator consomem `GET /analysis/:request_id/events`.
- O customer usa linguagem bancária; dados técnicos permanecem disponíveis ao operator e no modo debug.
- KPIs e tabela do operator ainda usam dados representativos, embora `/analyses` e `/analyses/stats` já existam para a integração futura.

## Próximos passos sugeridos

1. Conectar os KPIs do operator a `GET /analyses/stats`.
2. Conectar a tabela de decisões a `GET /analyses`.
3. Revisar política de retenção/limpeza do SQLite e da memória episódica.
4. Atualizar o README, que ainda descreve partes da arquitetura anterior ao SQLite/SSE.

## Como retomar

```bash
cd /home/daniloamaral/agentic/credit-analysis-agent
git status --short
src/.venv/bin/python src/resume_endpoint.py --port 8086
./run_all_evals.sh
```

Antes de qualquer commit, confirmar que apenas arquivos intencionais estão staged e que `src/episodic_memory.json` continua fora do commit.
