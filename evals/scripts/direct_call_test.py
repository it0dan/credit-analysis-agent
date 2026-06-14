"""
Testa que o compliance-agent rejeita chamadas sem token válido do Gateway.
Retorna JSON com direct_call_rejected: true se receber 401/403/connection refused.
"""
import httpx
import json
import os

COMPLIANCE_URL = os.getenv("COMPLIANCE_DIRECT_URL", "http://localhost:8085")

def test_direct_call():
    try:
        r = httpx.post(
            f"{COMPLIANCE_URL}/v1/compliance",
            json={
                "applicant_masked_cpf": "XXX.XXX.XXX-99",
                "request_id": "test-direct-00000000",
                "trace_id": "test-trace"
            },
            # Sem header Authorization — simula chamada direta sem Gateway
            timeout=5.0
        )
        rejected = r.status_code in (401, 403)
        return {"direct_call_rejected": rejected, "status_code": r.status_code}
    except (httpx.ConnectError, httpx.TimeoutException):
        return {"direct_call_rejected": True, "reason": "connection_refused"}

if __name__ == "__main__":
    print(json.dumps(test_direct_call()))
