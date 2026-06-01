# Spec: Human-in-the-Loop (HITL) Assíncrono

**Change ID:** hitl-async
**Status:** ACCEPTED
**Autor:** Danilo Amaral
**Data:** 2026-06-01

---

## 1. Contrato OpenAPI YAML (`POST /resume`)

O contrato OpenAPI abaixo especifica o endpoint utilizado para a mesa de crédito submeter decisões humanas e retomar o orquestrador para execução do Turno 3 (T3).

```yaml
openapi: 3.0.3
info:
  title: Credit Analysis Async HITL API
  version: 1.0.0
  description: Especificação técnica para retomar o processo de análise de crédito a partir de uma intervenção humana assíncrona.
paths:
  /resume:
    post:
      summary: Retoma uma análise de crédito suspensa por intervenção humana
      description: Hidrata os resultados intermediários de T1 e T2 do Redis e executa o Turno 3 (T3 - decision_synthesize) síncronamente para emitir a resposta definitiva.
      security:
        - OAuth2Bearer: []
      parameters:
        - name: X-Trace-Id
          in: header
          required: false
          schema:
            type: string
          description: Identificador de trace propagado end-to-end (W3C traceparent).
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required:
                - request_id
                - decision
                - justification
                - operator_id
              properties:
                request_id:
                  type: string
                  format: uuid
                  description: Identificador único e universal da requisição de crédito.
                decision:
                  type: string
                  enum: [approve, reject, escalate]
                  description: Decisão do operador humano de crédito.
                justification:
                  type: string
                  minLength: 50
                  maxLength: 300
                  description: Justificativa de auditoria fundamentada da decisão.
                operator_id:
                  type: string
                  description: Identificador do analista de crédito que tomou a decisão.
      responses:
        '200':
          description: Análise retomada e concluída com sucesso. Retorna o output final de crédito.
          headers:
            X-Trace-Id:
              schema:
                type: string
              description: O identificador de trace original preservado.
          content:
            application/json:
              schema:
                type: object
                required:
                  - request_id
                  - status
                  - decision
                  - requested_amount
                  - approved_amount
                  - justification
                  - conditions
                  - trace_id
                  - processing_time_ms
                  - agents_consulted
                properties:
                  request_id:
                    type: string
                    format: uuid
                  status:
                    type: string
                    enum: [approved, rejected, pending_human_review]
                  decision:
                    type: string
                    enum: [approved, rejected, adjusted, pending]
                  requested_amount:
                    type: number
                  approved_amount:
                    type: number
                    nullable: true
                  justification:
                    type: string
                  conditions:
                    type: array
                    items:
                      type: string
                  trace_id:
                    type: string
                  processing_time_ms:
                    type: integer
                  agents_consulted:
                    type: array
                    items:
                      type: string
        '400':
          description: Requisição inválida. Erro de validação de campos.
          content:
            application/json:
              schema:
                type: object
                properties:
                  error:
                    type: string
                  details:
                    type: array
                    items:
                      type: string
        '401':
          description: Não autorizado. Bearer token OAuth2 ausente ou inválido.
        '403':
          description: Proibido. Escopo ou permissão insuficiente para o endpoint.
        '404':
          description: Não encontrado. O request_id não existe na fila ativa ou já foi processado/deletado.
        '409':
          description: Conflito de Idempotência. Essa requisição já está sendo processada ou já foi resolvida anteriormente.
        '410':
          description: Tempo Excedido (Gone). A análise expirou de acordo com o TTL estipulado.
components:
  securitySchemes:
    OAuth2Bearer:
      type: http
      scheme: bearer
      bearerFormat: JWT
```

---

## 2. JSON Schema da Análise Serializada (Redis Payload)

Este schema define a estrutura exata do JSON que é persistido no Redis na chave `hitl:analysis:{request_id}` para permitir hidratação segura e re-inicialização a partir do Runner 2.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "SerializedCreditAnalysis",
  "description": "Representação serializada do estado da análise de crédito nos estágios T1 e T2",
  "type": "object",
  "required": [
    "request_id",
    "trace_id",
    "cpf_masked",
    "created_at",
    "expires_at",
    "t1_results",
    "t2_results",
    "hitl_reason",
    "hitl_triggered_by"
  ],
  "properties": {
    "request_id": {
      "type": "string",
      "format": "uuid"
    },
    "trace_id": {
      "type": "string"
    },
    "cpf_masked": {
      "type": "string",
      "pattern": "^\\*\\*\\*\\.\\*\\*\\*\\.\\*\\*\\*-XX$"
    },
    "created_at": {
      "type": "string",
      "format": "date-time"
    },
    "expires_at": {
      "type": "string",
      "format": "date-time"
    },
    "t1_results": {
      "type": "object",
      "required": ["bureau", "risk"],
      "properties": {
        "bureau": {
          "type": "object",
          "required": ["score", "restrictions", "status"],
          "properties": {
            "score": { "type": "integer", "minimum": 0, "maximum": 1000 },
            "restrictions": {
              "type": "array",
              "items": { "type": "string" }
            },
            "status": { "type": "string" }
          }
        },
        "risk": {
          "type": "object",
          "required": ["internal_score", "default_probability", "risk_tier", "status"],
          "properties": {
            "internal_score": { "type": "integer", "minimum": 0, "maximum": 1000 },
            "default_probability": { "type": "number", "minimum": 0.0, "maximum": 1.0 },
            "risk_tier": { "type": "string", "enum": ["low", "medium", "high"] },
            "status": { "type": "string" }
          }
        }
      }
    },
    "t2_results": {
      "type": "object",
      "required": ["compliance"],
      "properties": {
        "compliance": {
          "type": "object",
          "required": ["kyc_approved", "pld_clear", "lgpd_consent", "status"],
          "properties": {
            "kyc_approved": { "type": "boolean" },
            "pld_clear": { "type": "boolean" },
            "lgpd_consent": { "type": "boolean" },
            "status": { "type": "string" }
          }
        }
      }
    },
    "hitl_reason": {
      "type": "string"
    },
    "hitl_triggered_by": {
      "type": "string",
      "enum": ["orchestrator", "compliance", "risk"]
    }
  }
}
```

---

## 3. JSON Schema do Interrupt Event (Canal SSE)

Representação do payload enviado via Server-Sent Events (SSE) para informar à AG-UI que há uma requisição aguardando operador.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "AGUIInterruptEvent",
  "description": "Payload de interrupção SSE para a interface de atendimento humana",
  "type": "object",
  "required": [
    "type",
    "request_id",
    "trace_id",
    "cpf_masked",
    "reason",
    "resume_endpoint",
    "expires_at"
  ],
  "properties": {
    "type": {
      "type": "string",
      "const": "HITL_REQUIRED"
    },
    "request_id": {
      "type": "string",
      "format": "uuid"
    },
    "trace_id": {
      "type": "string"
    },
    "cpf_masked": {
      "type": "string",
      "pattern": "^\\*\\*\\*\\.\\*\\*\\*\\.\\*\\*\\*-XX$"
    },
    "reason": {
      "type": "string",
      "description": "Motivo do acionamento humano (ex: threshold_exceeded, fallback_error)"
    },
    "resume_endpoint": {
      "type": "string",
      "const": "/resume"
    },
    "expires_at": {
      "type": "string",
      "format": "date-time"
    }
  }
}
```

---

## 4. SLAs (Service Level Agreements)

### TTL da Fila de Análise
- **SLA:** Toda requisição síncrona pausada ficará retida por um período máximo ditado pela configuração `HITL_TTL_SECONDS` (padrão de 24 horas - `86400` segundos).
- **Comportamento em Expiração:** Se a análise atingir a expiração do TTL no Redis sem ação do operador, a requisição é deletada de forma automática pelo Redis. Qualquer requisição futura a `/resume` para este ID resultará em `410 Gone`. O sistema emitirá um evento para o barramento comunicando o cancelamento por timeout e o status final do caso será marcado como `expired`, disparando a notificação ao cliente final para reinício do pedido de análise se desejado.

### Timeout de Decisão e Desbloqueio
- O tempo que o analista leva para decidir é assíncrono e isolado. Portanto, não consome recursos de computação do cluster e não bloqueia novas requisições síncronas de crédito automáticas de outros clientes (sem contenção de thread pool ou database connection pool).

---

## 5. Definition of Done (DoD)

Para este change ser considerado concluído e aceito, as seguintes condições devem ser satisfeitas:

1. **Zero Bloqueio Python:** Nenhum processo, runner local, thread ou worker assíncrono Python deve ficar em espera síncrona (como loops, `time.sleep()`, wait ativo) aguardando decisões humanas. O processo original deve ser encerrado imediatamente após a serialização do estado no Redis.
2. **Consistência do Estado Hidratado (Sem Re-execução):** O estado hidratado no Redis (`t1_results` e `t2_results`) deve conter absolutamente todas as informações necessárias para que o Turno 3 (T3 - decision_synthesize) execute perfeitamente, sem que o Runner 2 precise invocar novamente bureaus de crédito, OCRs de documentos, ou sub-agentes de T1 e T2.
3. **Preservação End-to-End do `X-Trace-Id`:** O cabeçalho de tracing `X-Trace-Id` (ou traceparent no padrão W3C) deve ser mantido idêntico do início do request original (POST `/analyze`), salvo com o estado serializado, hidratado no POST `/resume` e apresentado no resultado final consolidado.
4. **Idempotência do Endpoint `/resume`:** Chamadas concorrentes ao endpoint `/resume` para o mesmo `request_id` devem ser bloqueadas de forma atômica, retornando `409 Conflict` se a operação já estiver em andamento ou se a análise correspondente já tiver sido resolvida.
5. **PromptFoo Test Suit Passando:** O novo cenário PromptFoo `hitl_async` (especificamente configurado no `trajectory.yaml` / `orchestrator.yaml`) deve executar com sucesso e validar a conformidade das trajetórias assíncronas de ponta a ponta.
