"""
gateway_auth.py
Obtém e renova o token OAuth2 do Sensedia AI Gateway.

Fluxo: client_credentials → Bearer token
O token é cacheado em memória e renovado automaticamente antes do vencimento.
"""

import os
import time
import httpx


class GatewayAuth:
    """Cache de token OAuth2 com renovação automática."""

    def __init__(self):
        self._token: str | None = None
        self._expires_at: float = 0

    def get_token(self) -> str:
        if self._token and time.time() < self._expires_at - 30:
            return self._token
        self._token, ttl = self._fetch_token()
        self._expires_at = time.time() + ttl
        return self._token

    @staticmethod
    def _fetch_token() -> tuple[str, int]:
        endpoint = os.environ["AI_GATEWAY_OAUTH_ENDPOINT"]
        client_id = os.environ["AI_GATEWAY_CLIENT_ID"]
        client_secret = os.environ["AI_GATEWAY_CLIENT_SECRET"]

        headers = {}
        try:
            from opentelemetry import trace
            from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
            propagator = TraceContextTextMapPropagator()
            propagator.inject(headers)
            current_span = trace.get_current_span()
            span_context = current_span.get_span_context() if current_span else None
            if span_context and span_context.is_valid:
                trace_id_hex = f"{span_context.trace_id:032x}"
                trace_id_str = f"{trace_id_hex[:8]}-{trace_id_hex[8:12]}-{trace_id_hex[12:16]}-{trace_id_hex[16:20]}-{trace_id_hex[20:]}"
                headers["X-Trace-Id"] = trace_id_str
        except Exception:
            pass

        resp = httpx.post(
            endpoint,
            data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
            },
            headers=headers,
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["access_token"], int(data.get("expires_in", 300))


# Singleton reutilizado pelo orchestrator e pelo executor de ferramentas
gateway_auth = GatewayAuth()
