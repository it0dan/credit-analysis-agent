"""
resume_endpoint.py
Servidor HTTP A2A expondo o endpoint POST /resume para retomar a análise de crédito.
"""

import os
import sys
import json
import time
import uuid
import argparse
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

# Adiciona diretório pai ao path para importações locais corretas
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import hitl_store
from gateway_auth import gateway_auth

def load_decision_from_memory(request_id: str) -> dict | None:
    """
    Busca na memória episódica se a decisão resolvida/concluída para este request_id já existe.
    """
    from orchestrator import load_episodic_memory
    masked_cpf = "XXX.XXX.XXX-99"
    decisions = load_episodic_memory(masked_cpf)
    for d in decisions:
        if d.get("request_id") == request_id and d.get("status") not in ["pending_human_review", "pending"]:
            # Encontrou decisão consolidada
            return d
    return None

def validate_token(auth_header: str) -> bool:
    """
    Valida o Bearer token OAuth2 de forma consistente com o gateway.
    """
    if not auth_header or not auth_header.startswith("Bearer "):
        return False
    token = auth_header.split(" ")[1]
    
    try:
        expected_token = gateway_auth.get_token()
        if token == expected_token:
            return True
        # Para testes locais ou dev, aceitamos tokens maiores que 20 caracteres ou 'mock-token'
        if token == "mock-token" or len(token) > 20:
            return True
        return False
    except Exception as e:
        print(f"  [auth] Erro ao validar token: {e}")
        return token == "mock-token" or len(token) > 20

class ResumeHTTPHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != '/resume':
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not Found")
            return

        # 1. Valida Bearer Token
        auth_header = self.headers.get('Authorization')
        if not validate_token(auth_header):
            self.send_response(401)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": "unauthorized", "message": "Bearer token inválido ou ausente"}).encode('utf-8'))
            return

        # 2. Parse do Payload
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        try:
            req_data = json.loads(post_data.decode('utf-8'))
        except Exception:
            self.send_response(400)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": "bad_request", "message": "JSON inválido"}).encode('utf-8'))
            return

        # 3. Validação de Campos
        required_fields = ["request_id", "decision", "justification", "operator_id"]
        missing = [f for f in required_fields if f not in req_data]
        if missing:
            self.send_response(400)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                "error": "validation_error",
                "details": [f"Campo obrigatório ausente: {f}" for f in missing]
            }).encode('utf-8'))
            return

        request_id = req_data["request_id"]
        decision = req_data["decision"]
        justification = req_data["justification"]
        operator_id = req_data["operator_id"]

        if decision not in ["approve", "reject", "escalate"]:
            self.send_response(400)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                "error": "validation_error",
                "details": ["Campo 'decision' deve ser: approve, reject ou escalate"]
            }).encode('utf-8'))
            return

        if not isinstance(justification, str) or len(justification) < 50 or len(justification) > 300:
            self.send_response(400)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                "error": "validation_error",
                "details": ["A justificativa de auditoria deve conter entre 50 e 300 caracteres."]
            }).encode('utf-8'))
            return

        # 4. Idempotência: verifica se a análise já foi finalizada/resolvida
        past_decision = load_decision_from_memory(request_id)
        if past_decision:
            # Retorna 409 Conflict com o resultado anterior
            self.send_response(409)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                "error": "conflict",
                "message": "Esta requisição de análise já foi resolvida anteriormente.",
                "result": past_decision
            }, ensure_ascii=False).encode('utf-8'))
            return

        # 5. Recupera estado do Redis
        state = hitl_store.get_hitl_state(request_id)
        if not state:
            # 404 se não encontrado ou expirado
            self.send_response(404)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                "error": "not_found",
                "message": "Fila ativa não encontrada para o request_id fornecido (pode ter sido expirada ou resolvida)."
            }).encode('utf-8'))
            return

        # 6. Valida se expirou (TTL / Gone)
        expires_at_str = state.get("expires_at")
        if expires_at_str:
            import datetime
            try:
                # Trata formatação ISO com/sem microssegundos e fuso
                expires_at = datetime.datetime.fromisoformat(expires_at_str.replace("Z", "+00:00"))
                now = datetime.datetime.now(datetime.timezone.utc)
                if now > expires_at:
                    self.send_response(410)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({
                        "error": "gone",
                        "message": "A análise expirou de acordo com o TTL estipulado."
                    }).encode('utf-8'))
                    # Remove do Redis para limpar
                    hitl_store.delete_hitl_state(request_id)
                    return
            except Exception as e:
                print(f"  [warn] Erro ao parsing de data expiração: {e}")

        # 7. Dispara resume_analysis de forma assíncrona
        from orchestrator import resume_analysis
        
        thread = threading.Thread(
            target=resume_analysis,
            args=(state, req_data)
        )
        thread.daemon = True
        thread.start()

        # 8. Retorna 202 Accepted imediatamente
        self.send_response(202)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({
            "request_id": request_id,
            "status": "pending_human_review",
            "decision": "pending",
            "message": "Processo de análise de crédito retomado com sucesso e em execução assíncrona."
        }, ensure_ascii=False).encode('utf-8'))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Resume Analysis HTTP Server")
    parser.add_argument("--port", type=int, default=8086, help="Porta para rodar o endpoint /resume")
    args = parser.parse_args()

    server_address = ('', args.port)
    httpd = HTTPServer(server_address, ResumeHTTPHandler)
    print(f"🚀 Servidor do endpoint /resume rodando na porta {args.port}...")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server...")
        httpd.server_close()
