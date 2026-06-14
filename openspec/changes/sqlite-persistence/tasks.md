# Tasks — SQLite Persistence

- [x] 1. Criar ADR de SQLite persistence preservando ADR-008 existente.
- [x] 2. Criar `src/db.py` com schema, seed idempotente, CRUD de análises e HITL.
- [x] 3. Integrar `db.init_db()` e `db.save_analysis()` em `src/orchestrator.py` sem alterar o loop puro.
- [x] 4. Enriquecer `src/hitl_store.py` com Redis -> SQLite -> memória.
- [x] 5. Adicionar endpoints/fallback SQLite em `src/resume_endpoint.py`.
- [x] 6. Ignorar `src/credit_analysis.db*` no Git.
- [x] 7. Validar init/seed, endpoints, thread safety e evals.
