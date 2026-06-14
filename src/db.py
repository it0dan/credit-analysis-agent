"""
db.py
Store SQLite durável para análises e estados HITL.
Compatível com Python stdlib (sqlite3) — sem deps externas.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
import time
from datetime import datetime, timezone
from typing import Any

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "credit_analysis.db")

_lock = threading.Lock()


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Cria tabelas idempotentes e importa episodic_memory.json quando necessário."""
    with _lock:
        with _get_conn() as conn:
            conn.executescript(
                """
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
                """
            )
            count = conn.execute("SELECT COUNT(*) FROM analyses").fetchone()[0]
            if count == 0:
                _seed_from_json(conn)


def _cpf_hash(cpf_masked: str) -> str:
    return hashlib.sha256(cpf_masked.encode("utf-8")).hexdigest()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _extract_cost(record: dict[str, Any]) -> float | None:
    if record.get("finops_cost_brl") is not None:
        return record.get("finops_cost_brl")
    if record.get("estimated_cost_brl") is not None:
        return record.get("estimated_cost_brl")
    meta = record.get("_meta") or {}
    finops = meta.get("finops") if isinstance(meta, dict) else {}
    if isinstance(finops, dict):
        return finops.get("estimated_cost_brl")
    return None


def _seed_from_json(conn: sqlite3.Connection) -> None:
    """Importa o histórico JSON uma única vez."""
    json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "episodic_memory.json")
    if not os.path.exists(json_path):
        print("  [db] Seed: episodic_memory.json não encontrado")
        return

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    now = _now_iso()
    inserted = 0
    for cpf_masked, records in data.items():
        cpf_hash = _cpf_hash(cpf_masked)
        for record in records:
            request_id = record.get("request_id")
            if not request_id:
                continue
            created_at = record.get("created_at") or record.get("timestamp") or now
            cur = conn.execute(
                """
                INSERT OR IGNORE INTO analyses
                    (request_id, cpf_hash, cpf_masked, requested_amount, approved_amount,
                     status, decision, justification, trace_id, finops_cost_brl, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    request_id,
                    cpf_hash,
                    cpf_masked,
                    record.get("requested_amount", 0),
                    record.get("approved_amount"),
                    record.get("status", "pending"),
                    record.get("decision"),
                    record.get("justification"),
                    record.get("trace_id"),
                    _extract_cost(record),
                    created_at,
                    record.get("updated_at") or created_at,
                ),
            )
            inserted += cur.rowcount

    print(f"  [db] Seed: {inserted} registros importados do episodic_memory.json")


def save_analysis(record: dict[str, Any]) -> None:
    """Insere ou atualiza um registro de análise."""
    request_id = record.get("request_id")
    if not request_id:
        return

    now = _now_iso()
    cpf_masked = record.get("cpf_masked") or record.get("applicant_masked_cpf") or "***.***.***-XX"
    created_at = record.get("created_at") or record.get("timestamp") or now

    with _lock:
        with _get_conn() as conn:
            conn.execute(
                """
                INSERT INTO analyses
                    (request_id, cpf_hash, cpf_masked, requested_amount, approved_amount,
                     status, decision, justification, trace_id, finops_cost_brl, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(request_id) DO UPDATE SET
                    cpf_hash=excluded.cpf_hash,
                    cpf_masked=excluded.cpf_masked,
                    requested_amount=excluded.requested_amount,
                    approved_amount=excluded.approved_amount,
                    status=excluded.status,
                    decision=excluded.decision,
                    justification=excluded.justification,
                    trace_id=excluded.trace_id,
                    finops_cost_brl=excluded.finops_cost_brl,
                    updated_at=excluded.updated_at
                """,
                (
                    request_id,
                    _cpf_hash(cpf_masked),
                    cpf_masked,
                    record.get("requested_amount", 0),
                    record.get("approved_amount"),
                    record.get("status", "pending"),
                    record.get("decision"),
                    record.get("justification"),
                    record.get("trace_id"),
                    _extract_cost(record),
                    created_at,
                    now,
                ),
            )


def get_analysis(request_id: str) -> dict[str, Any] | None:
    with _get_conn() as conn:
        row = conn.execute("SELECT * FROM analyses WHERE request_id = ?", (request_id,)).fetchone()
    return dict(row) if row else None


def list_analyses_by_cpf(cpf_masked: str, limit: int = 50) -> list[dict[str, Any]]:
    with _get_conn() as conn:
        rows = conn.execute(
            """
            SELECT * FROM analyses
            WHERE cpf_hash = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (_cpf_hash(cpf_masked), limit),
        ).fetchall()
    return [dict(row) for row in rows]


def get_stats() -> dict[str, Any]:
    with _get_conn() as conn:
        row = conn.execute(
            """
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN status = 'approved' THEN 1 ELSE 0 END) AS approved,
                SUM(CASE WHEN status = 'rejected' THEN 1 ELSE 0 END) AS rejected,
                SUM(CASE WHEN status = 'pending_human_review' THEN 1 ELSE 0 END) AS pending_human_review,
                AVG(finops_cost_brl) AS avg_cost_brl
            FROM analyses
            """
        ).fetchone()
    stats = dict(row)
    return {
        "total": stats.get("total") or 0,
        "approved": stats.get("approved") or 0,
        "rejected": stats.get("rejected") or 0,
        "pending_human_review": stats.get("pending_human_review") or 0,
        "avg_cost_brl": stats.get("avg_cost_brl") or 0.0,
    }


def save_hitl_to_db(request_id: str, payload: dict[str, Any], ttl_seconds: int) -> None:
    expires_at = time.time() + ttl_seconds
    with _lock:
        with _get_conn() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO hitl_states (request_id, payload, expires_at)
                VALUES (?, ?, ?)
                """,
                (request_id, json.dumps(payload, ensure_ascii=False), expires_at),
            )


def get_hitl_from_db(request_id: str) -> dict[str, Any] | None:
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT payload, expires_at FROM hitl_states WHERE request_id = ?",
            (request_id,),
        ).fetchone()
    if not row:
        return None
    if time.time() > row["expires_at"]:
        delete_hitl_from_db(request_id)
        return None
    return json.loads(row["payload"])


def delete_hitl_from_db(request_id: str) -> None:
    with _lock:
        with _get_conn() as conn:
            conn.execute("DELETE FROM hitl_states WHERE request_id = ?", (request_id,))


def list_hitl_from_db() -> list[dict[str, Any]]:
    states: list[dict[str, Any]] = []
    expired: list[str] = []
    with _get_conn() as conn:
        rows = conn.execute("SELECT request_id, payload, expires_at FROM hitl_states").fetchall()

    now = time.time()
    for row in rows:
        if now > row["expires_at"]:
            expired.append(row["request_id"])
            continue
        states.append(json.loads(row["payload"]))

    for request_id in expired:
        delete_hitl_from_db(request_id)

    return states


if __name__ == "__main__":
    init_db()
    print(f"DB inicializado. Stats: {get_stats()}")
