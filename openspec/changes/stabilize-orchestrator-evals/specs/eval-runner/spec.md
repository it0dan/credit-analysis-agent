# Delta Spec — Runner de avaliações resiliente

## ADDED Requirements

### Requirement: Validação determinística do contrato do orquestrador
The system SHALL validate all thirteen orchestrator scenarios with deterministic assertions over the response JSON, without requiring an LLM judge.

#### Scenario: Execução da suíte principal
- **WHEN** `evals/orchestrator.yaml` is evaluated against the configured provider
- **THEN** compliance, fallback, security, happy-path, and HITL invariants are checked directly from the JSON contract

### Requirement: Controle configurável de carga
The runner SHALL serialize Gateway calls by default and SHALL allow concurrency and delay overrides through environment variables.

#### Scenario: Execução sem overrides
- **WHEN** the unified runner starts without load-control environment variables
- **THEN** Promptfoo runs at concurrency 1 with a 1000 ms delay between calls

### Requirement: Recuperação de falhas transitórias
The runner SHALL retry HTTP 5xx responses with backoff, and the orchestrator client SHALL expose its retry limit through `AI_GATEWAY_MAX_RETRIES`.

#### Scenario: Gateway retorna erro transitório
- **WHEN** the AI Gateway responds with an eligible HTTP 5xx error
- **THEN** the request is retried up to the configured limit with backoff

### Requirement: Token vigente por configuração
The runner SHALL obtain a new Gateway token before each Promptfoo configuration.

#### Scenario: Execução supera o TTL do JWT inicial
- **WHEN** an earlier configuration takes long enough for its JWT to expire
- **THEN** the next configuration starts with a newly obtained token

### Requirement: Retomada seletiva
The runner SHALL accept optional configuration paths and SHALL execute the complete configuration list when none are supplied.

#### Scenario: Configurações são informadas por argumento
- **WHEN** one or more configuration paths are passed to `run_all_evals.sh`
- **THEN** only those configurations are evaluated in the supplied order
