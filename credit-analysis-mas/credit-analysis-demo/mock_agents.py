"""
mock_agents.py
Sub-agentes simulados como funções locais para o walking skeleton.

Cada função representa um sub-agente e retorna dados fixos por cenário.
Na v2, cada função será substituída por uma chamada A2A real ao sub-agente.

Rastreabilidade:
  spec.md § Sequência de Delegação A2A (inputs/outputs por etapa)
"""

import json
import uuid
from typing import Any


def _normalize_dict(d: Any) -> Any:
    """
    Remove envelopes aninhados desnecessários do Sensedia AI Gateway.
    Se o dict contiver uma única chave terminando em '_response' com um campo 'results',
    desembrulha o resultado.
    """
    if not isinstance(d, dict):
        return d
    
    # Se o dict tem chaves como 'bureau_get_score_response', etc.
    for k, v in list(d.items()):
        if isinstance(k, str) and k.endswith("_response") and isinstance(v, dict) and "results" in v:
            results = v["results"]
            if isinstance(results, list) and len(results) > 0:
                first = results[0]
                if isinstance(first, str):
                    try:
                        parsed = json.loads(first)
                        return _normalize_dict(parsed)
                    except Exception:
                        pass
                elif isinstance(first, dict):
                    return _normalize_dict(first)
        if isinstance(v, dict):
            d[k] = _normalize_dict(v)
        elif isinstance(v, list):
            d[k] = [_normalize_dict(item) if isinstance(item, dict) else item for item in v]
    return d


# ─────────────────────────────────────────────────────────────────────────────
# Cenários disponíveis para demo
#
# Passe scenario= ao instanciar MockAgents:
#   "auto_approve"    → todos ok, valor baixo  → aprovação automática
#   "hitl_required"   → todos ok, valor alto   → HITL obrigatório
#   "compliance_fail" → compliance bloqueia    → recusa imediata
#   "bureau_error"    → bureau falha           → fallback HITL
#   "multi_error"     → bureau + docs falham   → fallback HITL com múltiplos erros
# ─────────────────────────────────────────────────────────────────────────────

SCENARIOS: dict[str, dict] = {
    "auto_approve": {
        "bureau":     {"score": 780, "restrictions": [], "status": "ok"},
        "documents":  {"identity_valid": True, "income_confirmed": True,
                       "income_value": 8000, "status": "ok"},
        "risk":       {"internal_score": 82, "default_probability": 0.04,
                       "risk_tier": "low", "status": "ok"},
        "compliance": {"kyc_approved": True, "pld_clear": True,
                       "lgpd_consent": True, "status": "ok"},
        "decision":   {"decision": "approved", "confidence": 0.94,
                       "justification": "Score 780, renda R$8k confirmada, "
                                        "risco baixo, compliance ok.",
                       "conditions": []},
    },
    "hitl_required": {
        "bureau":     {"score": 800, "restrictions": [], "status": "ok"},
        "documents":  {"identity_valid": True, "income_confirmed": True,
                       "income_value": 15000, "status": "ok"},
        "risk":       {"internal_score": 88, "default_probability": 0.03,
                       "risk_tier": "low", "status": "ok"},
        "compliance": {"kyc_approved": True, "pld_clear": True,
                       "lgpd_consent": True, "status": "ok"},
        "decision":   {"decision": "approved", "confidence": 0.96,
                       "justification": "Score 800, renda R$15k confirmada, "
                                        "risco muito baixo, compliance ok.",
                       "conditions": []},
    },
    "compliance_fail": {
        "bureau":     {"score": 750, "restrictions": [], "status": "ok"},
        "documents":  {"identity_valid": True, "income_confirmed": True,
                       "income_value": 6000, "status": "ok"},
        "risk":       {"internal_score": 75, "default_probability": 0.08,
                       "risk_tier": "medium", "status": "ok"},
        "compliance": {"kyc_approved": False, "pld_clear": False,
                       "lgpd_consent": True, "status": "ok"},
        "decision":   None,  # nunca chamado neste cenário
    },
    "bureau_error": {
        "bureau":     {"status": "error", "error": "timeout"},
        "documents":  None,
        "risk":       None,
        "compliance": None,
        "decision":   None,
    },
    # [CORREÇÃO A] Cenário multi_error — fecha gap entre eval [HITL-2] e mocks
    # bureau + documents falham simultaneamente → fallback_error com
    # flags bureau_unavailable e docs_unverified. Compliance retorna ok
    # (não chegamos a chamá-lo neste cenário, mas o mock está disponível).
    "multi_error": {
        "bureau":     {"status": "error", "error": "timeout"},
        "documents":  {"status": "error", "error": "timeout"},
        "risk":       None,
        "compliance": {"kyc_approved": True, "pld_clear": True,
                       "lgpd_consent": True, "status": "ok"},
        "decision":   None,
    },
}


class MockAgents:
    """
    Sub-agentes simulados como funções locais.
    Substitua cada método por uma chamada A2A real na v2.
    """

    def __init__(self, scenario: str = "auto_approve", bureau_attempts: list[dict] = None):
        if scenario not in SCENARIOS:
            raise ValueError(
                f"Cenário inválido: '{scenario}'. "
                f"Disponíveis: {list(SCENARIOS.keys())}"
            )
        self.scenario = scenario
        self._data = SCENARIOS[scenario]
        self._bureau_attempts = list(bureau_attempts) if bureau_attempts is not None else None
        self._bureau_call_count = 0

    # [ORIGEM: spec.md § Etapa 1 — bureau.get_score]
    def bureau_get_score(self, applicant_masked_cpf: str,
                         request_id: str, trace_id: str = None) -> dict[str, Any]:
        if self._bureau_attempts is not None and self._bureau_call_count < len(self._bureau_attempts):
            result = dict(self._bureau_attempts[self._bureau_call_count])
            self._bureau_call_count += 1
        else:
            if self._data.get("bureau") is None:
                return _normalize_dict({"status": "error", "error": "not_applicable",
                        "request_id": request_id, "trace_id": trace_id or request_id})
            result = dict(self._data["bureau"])
        
        result["request_id"] = request_id
        result["trace_id"] = trace_id or request_id
        return _normalize_dict(result)

    # [ORIGEM: spec.md § Etapa 2 — documents.validate]
    def documents_validate(self, document_urls: list[str],
                            applicant_name: str,
                            request_id: str, trace_id: str = None) -> dict[str, Any]:
        if self._data.get("documents") is None:
            return _normalize_dict({"status": "error", "error": "not_applicable",
                    "request_id": request_id, "trace_id": trace_id or request_id})
        result = dict(self._data["documents"])
        result["request_id"] = request_id
        result["trace_id"] = trace_id or request_id
        return _normalize_dict(result)

    # [ORIGEM: spec.md § Etapa 3 — risk.evaluate]
    def risk_evaluate(self, bureau_score: int, income_value: float,
                      requested_amount: float,
                      request_id: str, trace_id: str = None) -> dict[str, Any]:
        if self._data.get("risk") is None:
            return _normalize_dict({"status": "error", "error": "not_applicable",
                    "request_id": request_id, "trace_id": trace_id or request_id})
        result = dict(self._data["risk"])
        result["request_id"] = request_id
        result["trace_id"] = trace_id or request_id
        return _normalize_dict(result)

    # [ORIGEM: spec.md § Etapa 4 — compliance.check]
    def compliance_check(self, applicant_masked_cpf: str,
                          request_id: str, trace_id: str = None) -> dict[str, Any]:
        if self._data.get("compliance") is None:
            return _normalize_dict({"status": "error", "error": "not_applicable",
                    "request_id": request_id, "trace_id": trace_id or request_id})
        result = dict(self._data["compliance"])
        result["request_id"] = request_id
        result["trace_id"] = trace_id or request_id
        return _normalize_dict(result)

    # [ORIGEM: compliance-agent/spec.md § Ferramenta: verify_kyc]
    def verify_kyc(self, applicant_masked_cpf: str,
                   request_id: str, trace_id: str = None) -> dict[str, Any]:
        if self.scenario == "bureau_error":
            return _normalize_dict({"status": "error", "error": "timeout",
                    "request_id": request_id, "trace_id": trace_id or request_id})
        if self.scenario == "compliance_fail":
            return _normalize_dict({
                "kyc_approved": False,
                "identity_match": False,
                "document_valid": False,
                "status": "rejected",
                "reason": "identity_mismatch",
                "request_id": request_id,
                "trace_id": trace_id or request_id,
            })
        return _normalize_dict({
            "kyc_approved": True,
            "identity_match": True,
            "document_valid": True,
            "status": "ok",
            "request_id": request_id,
            "trace_id": trace_id or request_id,
        })

    # [ORIGEM: compliance-agent/spec.md § Ferramenta: check_pld]
    def check_pld(self, applicant_masked_cpf: str,
                  request_id: str, trace_id: str = None) -> dict[str, Any]:
        if self.scenario == "compliance_fail":
            return _normalize_dict({
                "pld_clear": False,
                "sanctions_match": True,
                "risk_level": "high",
                "status": "rejected",
                "reason": "sanctions_list_match",
                "request_id": request_id,
                "trace_id": trace_id or request_id,
            })
        return _normalize_dict({
            "pld_clear": True,
            "sanctions_match": False,
            "risk_level": "none",
            "status": "ok",
            "request_id": request_id,
            "trace_id": trace_id or request_id,
        })

    # [ORIGEM: compliance-agent/spec.md § Ferramenta: verify_lgpd_consent]
    def verify_lgpd_consent(self, applicant_masked_cpf: str,
                            request_id: str, trace_id: str = None) -> dict[str, Any]:
        return _normalize_dict({
            "lgpd_consent": True,
            "consent_date": "2026-01-10T10:00:00Z",
            "consent_scope": ["credit_analysis"],
            "status": "ok",
            "request_id": request_id,
            "trace_id": trace_id or request_id,
        })

    # [ORIGEM: spec.md § Etapa 5 — decision.synthesize]
    def decision_synthesize(self, bureau_result: dict, documents_result: dict,
                            risk_result: dict, compliance_result: dict,
                            requested_amount: float,
                            request_id: str, trace_id: str = None) -> dict[str, Any]:
        # Unpack / normalize enveloped inputs
        bureau_result = _normalize_dict(bureau_result)
        documents_result = _normalize_dict(documents_result)
        risk_result = _normalize_dict(risk_result)
        compliance_result = _normalize_dict(compliance_result)

        if self._data.get("decision") is None:
            return _normalize_dict({"status": "error", "error": "not_applicable",
                    "request_id": request_id, "trace_id": trace_id or request_id})
        result = dict(self._data["decision"])
        result["trace_id"] = trace_id or request_id
        result["request_id"] = request_id
        return _normalize_dict(result)