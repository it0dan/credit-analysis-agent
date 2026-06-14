# Spec — SQLite Persistence

## Contratos de `src/db.py`

- `init_db() -> None`: cria schema idempotente, habilita WAL e executa seed do JSON histórico quando `analyses` está vazia.
- `save_analysis(record: dict) -> None`: insere ou atualiza análise por `request_id`.
- `get_analysis(request_id: str) -> dict | None`: retorna análise persistida ou `None`.
- `list_analyses_by_cpf(cpf_masked: str, limit: int = 50) -> list[dict]`: lista por hash do CPF mascarado.
- `get_stats() -> dict`: retorna totais por status e custo médio.
- `save_hitl_to_db(request_id: str, payload: dict, ttl_seconds: int) -> None`: persiste estado HITL com expiração.
- `get_hitl_from_db(request_id: str) -> dict | None`: recupera estado HITL válido.
- `delete_hitl_from_db(request_id: str) -> None`: remove estado HITL.
- `list_hitl_from_db() -> list[dict]`: lista estados HITL válidos e remove expirados.

## Contratos REST

### `GET /analyses?cpf_masked=...`

- `400` quando `cpf_masked` ausente.
- `200` com `{ "analyses": [...], "total": N }`.
- Cada item inclui `request_id`, `status`, `decision`, `requested_amount`, `approved_amount`, `created_at`, `updated_at`, `justification`, `trace_id`, `finops_cost_brl`.

### `GET /analyses/stats`

- `200` com `total`, `approved`, `rejected`, `pending_human_review`, `avg_cost_brl`.

### `GET /analysis/:id/status`

- Preserva respostas existentes para memória episódica e HITL.
- Quando encontrado apenas no SQLite, retorna `200` com `request_id`, `status`, `decision`, `trajectory: null`, `justification`, `requested_amount`, `approved_amount`, `created_at`, `updated_at`.

## Critérios de Aceite

- `python3 src/db.py` inicializa sem erro, cria `src/credit_analysis.db` e mostra stats com `total > 0`.
- Seed idempotente: segunda execução não duplica registros.
- `GET /analysis/e0ef1401/status` retorna `200` com estado persistido.
- `GET /analyses?cpf_masked=XXX.XXX.XXX-99` retorna lista não vazia.
- `GET /analyses/stats` retorna `total > 0`.
- `hitl_store.py` grava HITL em SQLite mesmo sem Redis.
- `./run_all_evals.sh` continua passando.
- `src/credit_analysis.db`, `src/credit_analysis.db-wal` e `src/credit_analysis.db-shm` estão ignorados pelo Git.
