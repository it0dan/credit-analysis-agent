# Design: Human-in-the-Loop (HITL) Assíncrono

**Change ID:** hitl-async
**Status:** ACCEPTED
**Autor:** Danilo Amaral
**Data:** 2026-06-01

---

## Contexto

Esta especificação técnica de design descreve a transição do fluxo HITL de síncrono para assíncrono. Esta mudança elimina o bloqueio de threads de CPU/RAM em Python, permitindo que a infraestrutura escale horizontalmente de forma elástica, reduzindo custos operacionais (FinOps) e aumentando a confiabilidade (AIOps).

---

## Diagrama de Fluxo Completo (ASCII)

Abaixo está o ciclo de vida completo da requisição de crédito utilizando o modelo assíncrono:

```
    PROCESSO DE ANÁLISE INICIAL (RUNNER 1)
 ┌──────────────────────────────────────────┐
 │  Solicitação de Crédito (POST /analyze)  │  ◄── [Entrada do Cliente]
 └────────────────────┬─────────────────────┘
                      │ (X-Trace-Id)
                      ▼
 ┌──────────────────────────────────────────┐
 │       Executa Turno 1 (T1)               │  ◄── [bureau_get_score / documents_validate]
 └────────────────────┬─────────────────────┘
                      │
                      ▼
 ┌──────────────────────────────────────────┐
 │       Executa Turno 2 (T2)               │  ◄── [risk_evaluate / compliance_check]
 └────────────────────┬─────────────────────┘
                      │
                      ▼
 ┌──────────────────────────────────────────┐
 │    Short-Circuit / Detecção de HITL      │  ◄── [Excede R$ 50k ou falha operacional]
 └────────────────────┬─────────────────────┘
                      │
                      ▼
 ┌──────────────────────────────────────────┐
 │   Serialização de Estado para o Redis    │  ◄── [hitl_store.py armazena dados brutos de T1/T2]
 └────────────────────┬─────────────────────┘
                      │
                      ▼
 ┌──────────────────────────────────────────┐
 │   Disparo de Notificação SSE (AG-UI)     │  ◄── [Contrato HITL_REQUIRED emitido]
 └────────────────────┬─────────────────────┘
                      │
                      ▼
 ┌──────────────────────────────────────────┐
 │      Encerrar Processo Python (1)        │  ◄── [Retorna 202 Accepted, libera CPU/RAM]
 └──────────────────────────────────────────┘

========================= INTERVALO ASSÍNCRONO =========================
     Operador analisa o painel na AG-UI no seu próprio tempo de resposta.

 ┌──────────────────────────────────────────┐
 │       Operador emite a decisão           │
 └────────────────────┬─────────────────────┘
                      │
                      ▼
 ┌──────────────────────────────────────────┐
 │   POST /resume (AG-UI ──▶ Runner 2)     │  ◄── [Passa Bearer Token + Corpo do JSON]
 └────────────────────┬─────────────────────┘
                      │ (X-Trace-Id preservado)
                      ▼
    PROCESSO DE RETOMADA E EXECUÇÃO FINAL (RUNNER 2)
 ┌──────────────────────────────────────────┐
 │     Validação de Idempotência e TTL      │  ◄── [Evita execução duplicada ou tardia]
 └────────────────────┬─────────────────────┘
                      │
                      ▼
 ┌──────────────────────────────────────────┐
 │   Hidratação do Estado a partir do Redis │  ◄── [Recupera T1 & T2 sem re-executar tools]
 └────────────────────┬─────────────────────┘
                      │
                      ▼
 ┌──────────────────────────────────────────┐
 │       Executa Turno 3 (T3)               │  ◄── [decision_synthesize + Output final]
 └────────────────────┬─────────────────────┘
                      │
                      ▼
 ┌──────────────────────────────────────────┐
 │  Retorno 200 OK / Gravação Memória       │  ◄── [Salva na memória episódica]
 └──────────────────────────────────────────┘
```

---

## Schema da Análise Serializada (Redis Payload)

O estado intermediário é persistido sob a chave `hitl:analysis:{request_id}` com a seguinte estrutura de dados JSON:

```json
{
  "request_id": "uuid",
  "trace_id": "W3C traceparent",
  "cpf_masked": "***.***.***-XX",
  "created_at": "ISO8601",
  "expires_at": "ISO8601",
  "t1_results": {
    "bureau": {
      "score": 780,
      "restrictions": [],
      "status": "ok"
    },
    "risk": {
      "internal_score": 820,
      "default_probability": 0.04,
      "risk_tier": "low",
      "status": "ok"
    }
  },
  "t2_results": {
    "compliance": {
      "kyc_approved": true,
      "pld_clear": true,
      "lgpd_consent": true,
      "status": "ok"
    }
  },
  "hitl_reason": "string",
  "hitl_triggered_by": "orchestrator | compliance | risk"
}
```

---

## Endpoint de Retomada: `POST /resume`

O endpoint exposto para retomar a análise a partir da decisão humana obedece aos seguintes requisitos:

- **Autenticação:** Bearer token OAuth2 de nível corporativo (idêntico ao utilizado pelo Sensedia AI Gateway).
- **Idempotência:** Garantida pelo `request_id` enviado no corpo da requisição. Se o `request_id` já tiver sido processado ou deletado do Redis, a API responde com um código apropriado, evitando re-execuções duplicadas.
- **Propagação de Tracing:** O cabeçalho `X-Trace-Id` (ou W3C traceparent) passado na chamada original de `/analyze` e salvo no Redis deve ser injetado nas chamadas internas do Runner 2 e retornado no cabeçalho HTTP da resposta e no payload de output final da decisão.
- **Resposta:** Executa síncronamente o T3 utilizando os dados serializados + decisão do operador, retornando a decisão final consolidada em formato JSON.

### Payload de Requisição (Request Body)
```json
{
  "request_id": "d88b4382-7489-4d64-8393-01ef3df8c3aa",
  "decision": "approve",
  "justification": "Cliente com ótimo histórico interno e renda confirmada acima do padrão regional.",
  "operator_id": "op-98124"
}
```

- Valores permitidos para `"decision"`: `approve`, `reject`, `escalate`.

---

## Armazenamento Temporário (Redis Store)

- **Configuração:** O componente de conexão `hitl_store.py` fará a interface com a instância do Redis configurada pelas variáveis de ambiente.
- **SLA e Retenção:** O TTL do Redis é definido em segundos pela variável de ambiente `HITL_TTL_SECONDS` (default de `86400` segundos = 24 horas).
- **Expiração:** Após o tempo configurado, a chave expira automaticamente do Redis, impedindo que requisições desatualizadas permaneçam ativas na fila.

---

## Contrato de Evento de Interrupção AG-UI (Canal SSE)

Quando o fluxo de crédito precisa de aprovação humana, o Runner 1 emite uma notificação Server-Sent Events (SSE) para o painel de atendimento contendo o seguinte formato JSON:

```json
{
  "type": "HITL_REQUIRED",
  "request_id": "d88b4382-7489-4d64-8393-01ef3df8c3aa",
  "trace_id": "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01",
  "cpf_masked": "***.***.***-99",
  "reason": "threshold_exceeded",
  "resume_endpoint": "/resume",
  "expires_at": "2026-06-02T13:55:18Z"
}
```

---

## Decisões Técnicas (DT)

### DT-001 — Preservação de Estado via Redis em vez de Banco de Dados Relacional

- **Problema:** O estado da análise contém dados brutos volumosos de APIs de terceiros. Persistir esses dados estruturados temporários em colunas de banco de dados relacional clássico (PostgreSQL) geraria sobrecarga de escritas/updates e complexidade de schema rígido.
- **Decisão:** Utilizar Redis como armazenamento temporário do tipo Key-Value para os payloads serializados em formato JSON de curta duração.
- **Razão:** O tempo de acesso é extremamente baixo (< 2ms), o gerenciamento de expiração por TTL é nativo do Redis, diminuindo complexidade operacional, e a eliminação automática de propostas expiradas limpa a base sem necessidade de rotinas crons pesadas.

### DT-002 — Idempotência Absoluta por request_id

- **Problema:** Um operador ou script pode clicar duas vezes em "Confirmar Decisão", disparando requisições paralelas concorrentes para o `/resume` do mesmo caso.
- **Decisão:** A leitura e remoção do estado do Redis no `/resume` deve ser atômica. Se um processo Runner 2 ler o estado, ele deve ser marcado como `processing` ou deletado do Redis imediatamente. Se outra requisição com o mesmo `request_id` entrar em seguida, receberá `409 Conflict`.
- **Consequência:** Garante consistência transacional e impede dupla aprovação/emissão de crédito.

### DT-003 — Propagação do X-Trace-Id no Resume

- **Problema:** Quando a requisição é retomada de forma assíncrona pelo Runner 2 no endpoint `/resume`, o trace original iniciado na chamada `/analyze` do cliente pode ser perdido na observabilidade se um novo trace for gerado.
- **Decisão:** O traceparent original é armazenado junto ao JSON no Redis (`trace_id`). Ao hidratar o estado no Runner 2, o orquestrador obrigatoriamente injeta esse ID no contexto de observabilidade e nos cabeçalhos HTTP, garantindo correlação de ponta a ponta no Sensedia AI Gateway.
