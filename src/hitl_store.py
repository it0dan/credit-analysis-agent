"""
hitl_store.py
Interface com o Redis para persistência de estado do HITL assíncrono.
Com fallback in-memory quando REDIS_URL não estiver configurado.
"""

import os
import json
import time

# Store in-memory fallback
_in_memory_store = {}

def _get_redis_client():
    redis_url = os.environ.get("REDIS_URL")
    if not redis_url:
        return None
    try:
        import redis
        # Parse redis URL or initialize client
        return redis.from_url(redis_url, decode_responses=True)
    except (ImportError, Exception) as e:
        print(f"  [hitl_store] Falha ao inicializar Redis client ({e}). Usando fallback in-memory.")
        return None

def save_hitl_state(request_id: str, state_dict: dict, ttl_seconds: int) -> None:
    """
    Salva o estado da análise no Redis com um tempo de expiração (TTL).
    Se o Redis não estiver disponível, salva na memória do processo (fallback).
    """
    # Garante serialização compatível
    payload_str = json.dumps(state_dict, ensure_ascii=False)
    
    r = _get_redis_client()
    if r:
        try:
            key = f"hitl:analysis:{request_id}"
            r.setex(key, ttl_seconds, payload_str)
            print(f"  [hitl_store] Estado salvo no Redis para {request_id} com TTL de {ttl_seconds}s.")
            return
        except Exception as e:
            print(f"  [hitl_store] Erro ao salvar no Redis: {e}. Salvando em memória...")
    
    # Fallback in-memory
    expires_at = time.time() + ttl_seconds
    _in_memory_store[request_id] = {
        "payload": payload_str,
        "expires_at": expires_at
    }
    print(f"  [hitl_store] Estado salvo em memória para {request_id} (expira em {ttl_seconds}s).")

def get_hitl_state(request_id: str) -> dict | None:
    """
    Recupera o estado do Redis. Retorna None se não existir ou tiver expirado.
    """
    r = _get_redis_client()
    if r:
        try:
            key = f"hitl:analysis:{request_id}"
            payload_str = r.get(key)
            if payload_str:
                return json.loads(payload_str)
            print(f"  [hitl_store] Estado não encontrado no Redis para {request_id}.")
            return None
        except Exception as e:
            print(f"  [hitl_store] Erro ao ler do Redis: {e}. Lendo da memória...")
            
    # Fallback in-memory
    item = _in_memory_store.get(request_id)
    if item:
        # Valida expiração (TTL)
        if time.time() > item["expires_at"]:
            print(f"  [hitl_store] Estado em memória expirado para {request_id}.")
            delete_hitl_state(request_id)
            return None
        return json.loads(item["payload"])
    
    return None

def delete_hitl_state(request_id: str) -> None:
    """
    Deleta o estado do Redis ou da memória.
    """
    r = _get_redis_client()
    if r:
        try:
            key = f"hitl:analysis:{request_id}"
            r.delete(key)
            print(f"  [hitl_store] Estado deletado do Redis para {request_id}.")
            return
        except Exception as e:
            print(f"  [hitl_store] Erro ao deletar do Redis: {e}.")
            
    # Fallback in-memory
    if request_id in _in_memory_store:
        del _in_memory_store[request_id]
        print(f"  [hitl_store] Estado deletado da memória para {request_id}.")

def list_all_hitl_states() -> list[dict]:
    """
    Retorna uma lista com todos os estados HITL ativos e não expirados.
    """
    states = []
    r = _get_redis_client()
    if r:
        try:
            keys = r.keys("hitl:analysis:*")
            for key in keys:
                payload_str = r.get(key)
                if payload_str:
                    states.append(json.loads(payload_str))
            return states
        except Exception as e:
            print(f"  [hitl_store] Erro ao listar chaves do Redis: {e}.")
    
    # Fallback in-memory
    for request_id, item in list(_in_memory_store.items()):
        if time.time() > item["expires_at"]:
            del _in_memory_store[request_id]
        else:
            states.append(json.loads(item["payload"]))
    return states

