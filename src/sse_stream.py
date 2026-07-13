"""
sse_stream.py
Canal SSE unicast por request_id para observabilidade em tempo real do loop agêntico.
Non-blocking: emit_event usa put_nowait; erros de fila são descartados silenciosamente.
"""
import queue
import json
import threading
from datetime import datetime, timezone

_channels: dict[str, list[queue.Queue]] = {}
_lock = threading.Lock()

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

def create_channel(request_id: str) -> None:
    with _lock:
        if request_id not in _channels:
            _channels[request_id] = []
            print(f"  [sse_stream] Canal criado para {request_id}")

def is_channel_active(request_id: str) -> bool:
    with _lock:
        return request_id in _channels

def register_client(request_id: str) -> queue.Queue | None:
    q = queue.Queue(maxsize=200)
    with _lock:
        if request_id not in _channels:
            return None
        _channels[request_id].append(q)
    print(f"  [sse_stream] Cliente registrado em {request_id}. Total: {len(_channels[request_id])}")
    return q

def emit_event(request_id: str, event: dict) -> None:
    """Non-blocking: descarta se fila cheia ou canal inexistente."""
    event.setdefault("timestamp", _now())
    with _lock:
        queues = list(_channels.get(request_id, []))
    for q in queues:
        try:
            q.put_nowait(event)
        except queue.Full:
            pass

def close_channel(request_id: str) -> None:
    """Envia sentinel None para todos os clientes e remove o canal."""
    with _lock:
        queues = list(_channels.pop(request_id, []))
    for q in queues:
        try:
            q.put_nowait(None)  # sentinel: cliente deve fechar stream
        except queue.Full:
            pass
    if queues:
        print(f"  [sse_stream] Canal fechado para {request_id} ({len(queues)} clientes notificados)")

def unregister_client(request_id: str, q: queue.Queue) -> None:
    with _lock:
        lst = _channels.get(request_id, [])
        if q in lst:
            lst.remove(q)

def stream_end() -> bytes:
    return b'event: stream_end\ndata: {"type":"stream_end"}\n\n'

def format_sse(event: dict) -> bytes:
    """Formata evento como texto SSE."""
    event_type = event.get("type", "message")
    data = json.dumps(event, ensure_ascii=False)
    return f"event: {event_type}\ndata: {data}\n\n".encode("utf-8")

def format_keepalive() -> bytes:
    return f"event: keepalive\ndata: {json.dumps({'type': 'keepalive', 'timestamp': _now()})}\n\n".encode("utf-8")
