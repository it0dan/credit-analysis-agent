# SQLite Persistence

## Problema

`src/episodic_memory.json` funciona como memória episódica simples para a demo, mas é um arquivo plano keyed por CPF mascarado, sem índice por `request_id` e vulnerável a reset acidental em operações de Git. O `hitl_store.py` persiste estados HITL em Redis quando configurado, mas no padrão local cai para memória do processo e perde o estado em restart.

## Solução

Introduzir SQLite como store durável primário local, sem dependências externas:

- `src/db.py` cria schema, aplica migrações idempotentes e faz seed único a partir de `episodic_memory.json`.
- `hitl_store.py` passa a gravar HITL em Redis, SQLite e memória, com leitura Redis -> SQLite -> memória.
- `resume_endpoint.py` expõe consultas REST para análises persistidas e enriquece `GET /analysis/:id/status` com fallback SQLite.

## Escopo

Dentro do escopo:

- SQLite local em `src/credit_analysis.db`.
- Seed idempotente do JSON histórico.
- Endpoints `GET /analyses`, `GET /analyses/stats` e fallback em `GET /analysis/:id/status`.
- Preservação dos contratos existentes de `POST /resume`, `POST /analysis` e `GET /queue`.

Fora do escopo:

- Alterar o loop puro do `orchestrator.py`.
- Alterar `compliance-agent`.
- Alterar `credit-analysis-frontend`.
- Implementar SSE ou persistência de `reasoning_chunks`.

## ADR

`openspec/adr/ADR-008.md` já existe e documenta a correção de observabilidade/HITL. Para preservar histórico aceito, esta change registra a nova decisão como `openspec/adr/ADR-009.md`.
