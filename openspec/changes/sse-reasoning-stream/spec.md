# Specification — SSE reasoning stream (`credit-analysis-agent`)

## Contratos do Módulo `sse_stream.py`

```python
def create_channel(request_id: str) -> None
def register_client(request_id: str) -> queue.Queue
def emit_event(request_id: str, event: dict) -> None
def close_channel(request_id: str) -> None
def unregister_client(request_id: str, q: queue.Queue) -> None
def format_sse(event: dict) -> bytes
def format_keepalive() -> bytes
```

## Esquema dos Eventos SSE

Cada linha de dados transmitida segue a convenção do formato `text/event-stream`:
```
event: <tipo_do_evento>
data: <payload_json_compactado>\n\n
```

### Eventos Definidos

#### 1. `analysis_started`
Emitido imediatamente ao abrir o canal e iniciar o orquestrador.
```json
{
  "type": "analysis_started",
  "request_id": "string",
  "trace_id": "string (UUID)",
  "timestamp": "string (ISO 8601 UTC)"
}
```

#### 2. `agent_started`
Emitido antes da chamada da ferramenta associada ao agente.
```json
{
  "type": "agent_started",
  "request_id": "string",
  "agent": "bureau_get_score | documents_validate | risk_evaluate | compliance_check | decision_synthesize | handoff_to_human",
  "turn": "T1 | T2 | T3",
  "timestamp": "string"
}
```

#### 3. `agent_completed`
Emitido após o processamento da ferramenta do subagente.
```json
{
  "type": "agent_completed",
  "request_id": "string",
  "agent": "string",
  "turn": "T1 | T2 | T3",
  "status": "success | error",
  "latency_ms": 1200,
  "score": 650,                // Apenas bureau (opcional)
  "risk_tier": "medium",       // Apenas risk (opcional)
  "kyc_approved": true,        // Apenas compliance (opcional)
  "timestamp": "string"
}
```

#### 4. `hitl_required`
Emitido quando há um desvio (short-circuit) ou limite excedido que exige revisão humana.
```json
{
  "type": "hitl_required",
  "request_id": "string",
  "reason": "string",
  "timestamp": "string"
}
```

#### 5. `analysis_done`
Emitido quando a análise é resolvida com veredito final.
```json
{
  "type": "analysis_done",
  "request_id": "string",
  "status": "approved | rejected | pending_human_review",
  "decision": "approved | rejected | pending",
  "approved_amount": 50000.0,  // float ou null
  "justification": "string",
  "finops_cost_brl": 0.123456,
  "timestamp": "string"
}
```

#### 6. `keepalive`
Disparado a cada 15 segundos para evitar o encerramento prematuro da conexão HTTP por timeouts de proxies intermediários.
```json
{
  "type": "keepalive",
  "timestamp": "string"
}
```

## Contrato do Endpoint `GET /analysis/:id/events`
* **Path**: `/analysis/:id/events`
* **Método**: `GET`
* **Response Headers**:
  ```http
  Content-Type: text/event-stream; charset=utf-8
  Cache-Control: no-cache
  Connection: keep-alive
  X-Accel-Buffering: no
  Access-Control-Allow-Origin: *
  Access-Control-Allow-Methods: GET, POST, OPTIONS
  Access-Control-Allow-Headers: Content-Type, Authorization, X-Trace-Id
  ```

## Contrato de Persistência no SQLite (`analysis_events`)
Schema da nova tabela no SQLite (`src/credit_analysis.db`):
```sql
CREATE TABLE IF NOT EXISTS analysis_events (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    event_data TEXT NOT NULL,   -- Armazena o JSON completo do evento
    created_at TEXT NOT NULL,
    FOREIGN KEY (request_id) REFERENCES analyses(request_id)
);
CREATE INDEX IF NOT EXISTS idx_analysis_events_request ON analysis_events(request_id);
CREATE INDEX IF NOT EXISTS idx_analysis_events_created ON analysis_events(created_at);
```

## Regras de Segurança e Conformidade
* **Máscaras de PII**: Sob nenhuma circunstância o CPF do solicitante, nomes em formato legível, tokens JWT ou credenciais sensíveis devem ser trafegados nos payloads de eventos SSE.
* **Sem vazamento técnico**: Evitar expor no JSON os parâmetros brutos (`args`) enviados às ferramentas ou `span_id` internos gerados pelo OpenTelemetry.
