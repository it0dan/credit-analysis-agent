"""
hitl_interrupt.py
Geração e emissão do evento de interrupção (HITL_REQUIRED) para o frontend conectado via SSE.
"""

import queue
import json

# Filas de eventos ativas para cada cliente SSE conectado
_sse_queues = []

def build_interrupt_event(request_id: str, trace_id: str, cpf_masked: str, reason: str, expires_at: str) -> dict:
    """
    Constrói o payload do evento de interrupção conforme especificado no schema da AG-UI.
    """
    return {
        "type": "HITL_REQUIRED",
        "request_id": request_id,
        "trace_id": trace_id,
        "cpf_masked": cpf_masked,
        "reason": reason,
        "resume_endpoint": "/resume",
        "expires_at": expires_at
    }

def emit_interrupt_event(event: dict) -> None:
    """
    Emite o evento via SSE para todas as conexões de frontend ativas.
    """
    print(f"  [sse] Emitindo evento HITL_REQUIRED para request_id={event['request_id']}.")
    
    # Roda uma cópia para evitar problemas de concorrência ao modificar a lista
    active_queues = list(_sse_queues)
    for q in active_queues:
        try:
            q.put_nowait(event)
        except queue.Full:
            pass
        except Exception as e:
            print(f"  [sse] Erro ao enviar evento para fila SSE: {e}")

def register_sse_client() -> queue.Queue:
    """
    Registra uma nova conexão de cliente SSE (retorna a fila dedicada).
    """
    q = queue.Queue(maxsize=100)
    _sse_queues.append(q)
    print(f"  [sse] Cliente SSE registrado. Conexões ativas: {len(_sse_queues)}.")
    return q

def unregister_sse_client(q: queue.Queue) -> None:
    """
    Remove o registro de uma conexão de cliente SSE.
    """
    if q in _sse_queues:
        _sse_queues.remove(q)
    print(f"  [sse] Cliente SSE desregistrado. Conexões ativas: {len(_sse_queues)}.")
