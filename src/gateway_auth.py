"""
gateway_auth.py
Obtém e renova o token OAuth2 do Sensedia AI Gateway por agente (com aud claim).

Fluxo: client_credentials com 'audience' opcional → Bearer token
Os tokens são cacheados por audience e renovados automaticamente antes do vencimento.
"""

import os
import json
import time
import httpx


class GatewayAuth:
    """Cache de token OAuth2 com renovação automática por audience."""

    def __init__(self):
        # Cache mapeando a claim 'audience' -> (token, expires_at)
        self._cache: dict[str, tuple[str, float]] = {}
        
        # Token e tempo de expiração padrão (compatibilidade)
        self._token: str | None = None
        self._expires_at: float = 0

    def get_token(self) -> str:
        """
        Retorna o token padrão de compatibilidade.
        """
        if self._token and time.time() < self._expires_at - 30:
            return self._token
        self._token, ttl = self._fetch_token()
        self._expires_at = time.time() + ttl
        return self._token

    def get_agent_token(self, target_agent: str) -> str:
        """
        Retorna o token JWT com a claim 'aud' específica para o agente destino.
        Caso AI_GATEWAY_JWT_AUDIENCE_MAP não esteja configurado, usa o token padrão (fallback).
        """
        aud_map_str = os.environ.get("AI_GATEWAY_JWT_AUDIENCE_MAP")
        if not aud_map_str:
            print(f"  [warn] AI_GATEWAY_JWT_AUDIENCE_MAP não definida. Usando token padrão fallback para '{target_agent}'.")
            return self.get_token()

        try:
            aud_map = json.loads(aud_map_str)
        except Exception as e:
            print(f"  [warn] Erro ao fazer parsing de AI_GATEWAY_JWT_AUDIENCE_MAP ({e}). Usando token padrão fallback.")
            return self.get_token()

        audience = aud_map.get(target_agent)
        if not audience:
            print(f"  [warn] Agente '{target_agent}' não configurado no mapa de audience. Usando token padrão fallback.")
            return self.get_token()

        # Verifica cache específico para esta audience
        cached = self._cache.get(audience)
        if cached:
            token, expires_at = cached
            if time.time() < expires_at - 30:
                return token

        # Solicita novo token com audience específica
        print(f"  [auth] Solicitando token com claim 'aud' específica para '{target_agent}' (aud: {audience})...")
        token, ttl = self._fetch_token(audience=audience)
        expires_at = time.time() + ttl
        self._cache[audience] = (token, expires_at)
        return token

    @staticmethod
    def _fetch_token(audience: str | None = None) -> tuple[str, int]:
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

        data = {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        }
        if audience:
            data["audience"] = audience

        resp = httpx.post(
            endpoint,
            data=data,
            headers=headers,
            timeout=10,
        )
        resp.raise_for_status()
        res_data = resp.json()
        return res_data["access_token"], int(res_data.get("expires_in", 300))


# Singleton reutilizado pelo orquestrador e pelo executor de ferramentas
gateway_auth = GatewayAuth()
