# Design — SQLite Persistence

## Decisão 1 — Schema SQLite

```sql
CREATE TABLE IF NOT EXISTS analyses (
    request_id       TEXT PRIMARY KEY,
    cpf_hash         TEXT NOT NULL,
    cpf_masked       TEXT NOT NULL,
    requested_amount REAL NOT NULL,
    approved_amount  REAL,
    status           TEXT NOT NULL,
    decision         TEXT,
    justification    TEXT,
    trace_id         TEXT,
    finops_cost_brl  REAL,
    created_at       TEXT NOT NULL,
    updated_at       TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_analyses_cpf ON analyses(cpf_hash);
CREATE INDEX IF NOT EXISTS idx_analyses_status ON analyses(status);

CREATE TABLE IF NOT EXISTS hitl_states (
    request_id  TEXT PRIMARY KEY,
    payload     TEXT NOT NULL,
    expires_at  REAL NOT NULL
);
```

`reasoning_chunks` fica reservado para uma change futura de SSE.

## Decisão 2 — CPF Hash

`cpf_hash` usa SHA-256 do CPF mascarado. O sistema opera com CPF mascarado (`XXX.XXX.XXX-99`) e não deve derivar persistência a partir de CPF claro.

## Decisão 3 — Ordem de Persistência HITL

- `save_hitl_state`: escreve em Redis quando disponível, SQLite sempre que disponível, e memória do processo.
- `get_hitl_state`: lê Redis -> SQLite -> memória.
- `delete_hitl_state`: remove dos três stores.
- `list_all_hitl_states`: agrega Redis/SQLite/memória e filtra expirados.

## Decisão 4 — Seed Idempotente

`init_db()` cria tabelas e importa `episodic_memory.json` somente quando `analyses` está vazio. `request_id` é chave primária; rodadas subsequentes não duplicam registros.

## Decisão 5 — Arquivo SQLite

Banco local em `src/credit_analysis.db`, ignorado por Git junto com arquivos WAL/SHM.

## Decisão 6 — Endpoints

`GET /analyses?cpf_masked=XXX.XXX.XXX-99`

Retorna até 50 análises do CPF, ordenadas por `created_at DESC`:

```json
{ "analyses": [], "total": 0 }
```

`GET /analyses/stats`

Retorna totais para dashboards:

```json
{ "total": 0, "approved": 0, "rejected": 0, "pending_human_review": 0, "avg_cost_brl": 0.0 }
```

`GET /analysis/:id/status`

Mantém contrato existente e adiciona busca em SQLite quando o estado não está em HITL/memória episódica.

## Decisão 7 — Thread Safety

SQLite roda em WAL, `check_same_thread=False` e lock de módulo para writes. Leituras abrem conexões curtas com `row_factory=sqlite3.Row`.

## Decisão 8 — ADR

`ADR-008` já está ocupado no repositório. Esta decisão é documentada como `ADR-009: Adoção de SQLite como store durável primário`.
