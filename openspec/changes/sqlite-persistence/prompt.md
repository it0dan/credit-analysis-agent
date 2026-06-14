# Prompt de Retomada — SQLite Persistence

Objetivo: concluir a change `openspec/changes/sqlite-persistence/`.

Implementar SQLite como store durável local no `credit-analysis-agent`:

- `src/db.py` com schema `analyses` e `hitl_states`, seed idempotente de `src/episodic_memory.json`, CRUD e helpers HITL.
- `orchestrator.py` inicializa DB e chama `save_analysis()` quando salva memória episódica, sem mudar o loop agêntico puro.
- `hitl_store.py` escreve Redis + SQLite + memória; lê Redis -> SQLite -> memória; deleta dos três.
- `resume_endpoint.py` expõe `GET /analyses`, `GET /analyses/stats` e fallback SQLite em `GET /analysis/:id/status`.
- `.gitignore` ignora `src/credit_analysis.db*`.

Observação: `openspec/adr/ADR-008.md` já existe no repo. A ADR desta change deve ser `openspec/adr/ADR-009.md`.

Validação esperada:

- `python3 src/db.py`
- `GET /analysis/e0ef1401/status`
- `GET /analyses?cpf_masked=XXX.XXX.XXX-99`
- `GET /analyses/stats`
- thread safety com 20 writes concorrentes
- `./run_all_evals.sh`
