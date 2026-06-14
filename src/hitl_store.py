"""
hitl_store.py
Persistência de estado HITL assíncrono.
Ordem de leitura: Redis -> SQLite -> memória do processo.
"""

import json
import os
import time

try:
    import db as _db
    _db.init_db()
    _DB_AVAILABLE = True
except Exception as e:
    print(f"  [hitl_store] SQLite indisponível ({e}). Usando Redis/memória.")
    _db = None
    _DB_AVAILABLE = False

# Store in-memory fallback
_in_memory_store = {}


def _get_redis_client():
    redis_url = os.environ.get("REDIS_URL")
    if not redis_url:
        return None
    try:
        import redis
        return redis.from_url(redis_url, decode_responses=True)
    except (ImportError, Exception) as e:
        print(f"  [hitl_store] Falha ao inicializar Redis client ({e}). Usando fallback durável/local.")
        return None


def save_hitl_state(request_id: str, state_dict: dict, ttl_seconds: int) -> None:
    """Salva estado HITL em Redis, SQLite e memória de processo."""
    payload_str = json.dumps(state_dict, ensure_ascii=False)
    saved_anywhere = False

    r = _get_redis_client()
    if r:
        try:
            key = f"hitl:analysis:{request_id}"
            r.setex(key, ttl_seconds, payload_str)
            print(f"  [hitl_store] Estado salvo no Redis para {request_id} com TTL de {ttl_seconds}s.")
            saved_anywhere = True
        except Exception as e:
            print(f"  [hitl_store] Erro ao salvar no Redis: {e}.")

    if _DB_AVAILABLE:
        try:
            _db.save_hitl_to_db(request_id, state_dict, ttl_seconds)
            print(f"  [hitl_store] Estado salvo no SQLite para {request_id} com TTL de {ttl_seconds}s.")
            saved_anywhere = True
        except Exception as e:
            print(f"  [hitl_store] Erro ao salvar no SQLite: {e}.")

    expires_at = time.time() + ttl_seconds
    _in_memory_store[request_id] = {
        "payload": payload_str,
        "expires_at": expires_at,
    }
    if not saved_anywhere:
        print(f"  [hitl_store] Estado salvo apenas em memória para {request_id} (expira em {ttl_seconds}s).")


def get_hitl_state(request_id: str) -> dict | None:
    """Recupera estado HITL de Redis, SQLite ou memória, respeitando TTL."""
    r = _get_redis_client()
    if r:
        try:
            key = f"hitl:analysis:{request_id}"
            payload_str = r.get(key)
            if payload_str:
                return json.loads(payload_str)
            print(f"  [hitl_store] Estado não encontrado no Redis para {request_id}.")
        except Exception as e:
            print(f"  [hitl_store] Erro ao ler do Redis: {e}.")

    if _DB_AVAILABLE:
        try:
            state = _db.get_hitl_from_db(request_id)
            if state:
                return state
        except Exception as e:
            print(f"  [hitl_store] Erro ao ler do SQLite: {e}.")

    item = _in_memory_store.get(request_id)
    if item:
        if time.time() > item["expires_at"]:
            print(f"  [hitl_store] Estado em memória expirado para {request_id}.")
            delete_hitl_state(request_id)
            return None
        return json.loads(item["payload"])

    return None


def delete_hitl_state(request_id: str) -> None:
    """Remove estado HITL de Redis, SQLite e memória."""
    r = _get_redis_client()
    if r:
        try:
            key = f"hitl:analysis:{request_id}"
            r.delete(key)
            print(f"  [hitl_store] Estado deletado do Redis para {request_id}.")
        except Exception as e:
            print(f"  [hitl_store] Erro ao deletar do Redis: {e}.")

    if _DB_AVAILABLE:
        try:
            _db.delete_hitl_from_db(request_id)
            print(f"  [hitl_store] Estado deletado do SQLite para {request_id}.")
        except Exception as e:
            print(f"  [hitl_store] Erro ao deletar do SQLite: {e}.")

    if request_id in _in_memory_store:
        del _in_memory_store[request_id]
        print(f"  [hitl_store] Estado deletado da memória para {request_id}.")


def list_all_hitl_states() -> list[dict]:
    """Lista estados HITL ativos e não expirados, combinando Redis/SQLite/memória."""
    states_by_id = {}

    r = _get_redis_client()
    if r:
        try:
            keys = r.keys("hitl:analysis:*")
            for key in keys:
                payload_str = r.get(key)
                if payload_str:
                    state = json.loads(payload_str)
                    states_by_id[state.get("request_id") or key.rsplit(":", 1)[-1]] = state
        except Exception as e:
            print(f"  [hitl_store] Erro ao listar chaves do Redis: {e}.")

    if _DB_AVAILABLE:
        try:
            for state in _db.list_hitl_from_db():
                states_by_id[state.get("request_id")] = state
        except Exception as e:
            print(f"  [hitl_store] Erro ao listar estados do SQLite: {e}.")

    for request_id, item in list(_in_memory_store.items()):
        if time.time() > item["expires_at"]:
            del _in_memory_store[request_id]
        else:
            state = json.loads(item["payload"])
            states_by_id[request_id] = state

    return list(states_by_id.values())
