# Sistema de Análise de Crédito Multiagente

Este repositório contém o motor de análise de crédito multiagente baseado na arquitetura de agentes autônomos, utilizando o **Sensedia AI Gateway** e LLMs de última geração (**Gemini 2.5 Flash Lite**).

O projeto implementa uma arquitetura agêntica em estágio de desenvolvimento ativo (v0 / baseline), com cobertura completa de evals, validação de trajetórias reais e robustez no loop agêntico.

---

## 📂 Estrutura do Projeto

```
credit-analysis-agent/
├── README.md                          ← Documentação geral da arquitetura
├── AGENTS.md                          ← Especificação dos agentes e invariantes críticos
├── HANDOFF.md                         ← Registro de estado e orientações de retomada
├── requirements.txt                   ← Dependências oficiais de OpenTelemetry
├── run_all_evals.sh                   ← Orquestrador global de testes/evals
├── openspec/                          ← Contratos OpenAPI, ADRs e esquemas de dados oficiais
│   └── adr/                           ← Registros de decisões de arquitetura (ADRs)
├── evals/                             ← Evals de trajetórias de fluxo (5 cenários)
└── src/                               ← Implementação de referência do runtime
    ├── .env.example                   ← Variáveis de ambiente (copiar para .env)
    ├── gateway_auth.py            ← Autenticação OAuth2 no Sensedia AI Gateway e injeção de traces
    ├── mock_agents.py             ← Provedor de ferramentas locais para simulações
    ├── bureau_agent.py            ← Contrato e esquemas de validação do AgentBureau
    ├── compliance_agent.py        ← Runtime do AgentCompliance (com servidor HTTP A2A)
    ├── risk_agent.py              ← Contrato e esquemas do AgentRisk
    ├── decision_agent.py          ← Contrato e esquemas do AgentDecision
    ├── db.py                      ← Store SQLite durável local (credit_analysis.db)
    ├── sse_stream.py              ← Engine de streaming de progresso agêntico via Server-Sent Events (SSE)
    ├── episodic_memory.json       ← Repositório JSON persistente de memória episódica (LTM)
    ├── orchestrator.py            ← Orquestrador principal com loop agêntico e suporte a spans OTel
    ├── orchestrator_provider.py   ← Provedor Promptfoo isolado para parsing determinístico de JSON
    ├── otel_setup.py              ← Inicialização do OpenTelemetry SDK e propagador W3C
    ├── hitl_store.py              ← Fila de persistência de estado do Redis/SQLite com fallback em memória
    ├── hitl_interrupt.py          ← Em## 🏛️ Arquitetura e Pilares da Solução

A arquitetura do sistema implementa os padrões modernos de sistemas agênticos corporativos seguindo 4 pilares de Engenharia de Contexto:

```
                  ┌──────────────────────────────────────────────┐
                  │          Orquestrador (orchestrator.py)      │
                  └──────┬────────────────────────────────┬──────┘
                         │                                │
      (OAuth2 Bearer via gateway_auth)      (SQLite / Episodic Memory / Event Store)
                         ▼                                ▼
            ┌─────────────────────────┐      ┌─────────────────────────┐
            │   Sensedia AI Gateway   │      │ credit_analysis.db      │
            └────────────┬────────────┘      └─────────────────────────┘
                         ▼
             [Gemini 2.5 Flash Lite]
                         │ (Loop Agêntico Autoreparável)
                         ▼
            ┌─────────────────────────┐
            │      mock_agents.py     │
            └────────────┬────────────┘
                         ├─→ bureau_get_score()
                         ├─→ documents_validate()
                         ├─→ risk_evaluate()
                         ├─→ compliance_check()  ──[A2A HTTP POST]──→ compliance_agent.py (Port 8080/8085)
                         ├─→ decision_synthesize()
                         └─→ handoff_to_human()
```

### 1. Contexto & Memória de Longo Prazo (LTM)
* **Isolate (Isolamento)**: Cada turno é uma requisição HTTP REST independente e sem estado para o Gateway.
* **Persistência SQLite Durável & Memória Episódica**: Persistida no SQLite local (`credit_analysis.db` via `src/db.py`) com seed idempotente a partir de `episodic_memory.json`. Armazena os resultados de análises passadas, garantindo que o agente reconheça recorrências ou histórico prévio.
* **Ofuscação Semântica contra Premature Stopping**: Pequenos LLMs sofrem de viés de parada antecipada ao ler palavras como `approved` ou `rejected` no histórico. Na memória e contexto, mapeamos o status para códigos neutros (`CODE_PA` para pré-aprovado, `CODE_A` para aprovado final, `CODE_R` para rejeitado, `CODE_P` para pendente) e removemos justificativas textuais complexas do contexto ativo.

### 2. Robustez do Loop & Auto-Reparação (Self-Healing)
* **Simulação de Fallback de Tool-Calling**: Corrige o erro `MALFORMED_FUNCTION_CALL` quando o LLM retorna chamadas de ferramentas encapsuladas em blocos de código markdown (`default_api.execute_tool(...)` etc.) em vez de chamadas estruturadas puras.
* **Guardas de Conformidade Ativa**: O orquestrador detecta automaticamente se o modelo tentou encerrar a execução sem passar pelos passos obrigatórios (como verificação de conformidade ou handoff HITL) e injeta instruções corretivas transparentes.
* **Normalizador de Assinatura de Ferramenta**: Traduz argumentos planos enviados de forma incorreta pelo LLM em estruturas aninhadas exigidas pelas assinaturas rígidas dos esquemas (`decision_synthesize`).

### 3. Comunicação A2A (Agent-to-Agent) Distribuída
* O `compliance_agent.py` atua como um agente A2A externo (servidor Node.js rodando na porta `8085` ou mock Python A2A na porta `8080`), simulando comunicação entre serviços independentes.
* **Rastreabilidade de Ponta a Ponta**: Propagação obrigatória dos cabeçalhos `traceparent` (OpenTelemetry W3C) e `X-Trace-Id` que correlacionam cada chamada de subagente de forma única em logs distribuídos.

### 4. Streaming SSE & Transparência Agêntica
* O motor emite eventos em tempo real via Server-Sent Events (SSE) na rota `GET /analysis/:request_id/events` (`sse_stream.py`).
* Eventos emitidos: `analysis_started`, `agent_started`, `agent_completed`, `hitl_required`, `analysis_done`.
* Replay automático de eventos a partir do banco de dados SQLite para reconexões do frontend.

### 5. Regra de Negócio: Pré-Aprovação Automática
* O fluxo automático de análise bem-sucedido encerra em `pre_approved` (pré-aprovado) quando a solicitação é ≤ R$ 50.000 e sem impedimentos.
* O status `approved` (aprovado) é estritamente reservado para confirmação humana via fluxo HITL (`POST /resume` com `decision=approve`).

### 6. FinOps & Custos Reais
* Monitoramento preciso e imediato do consumo real de tokens (entrada, saída e cache) a cada turno da API do Gemini.
* Cálculo monetizado em Reais (BRL) baseado nas tabelas de preço oficiais da API, formatado a 6 casas decimais e exposto em `_meta.finops`.

---

## 🎯 Cenários de Teste & Trajetória Esperada

A suite de testes cobre 5 fluxos fundamentais descritos em `evals/trajectory.yaml`:

| Cenário | Descrição e Comportamento Esperado | Sequência (Trajectory) Exigida |
| :--- | :--- | :--- |
| `auto_approve` | Solicitação ≤ R$ 50k, sem restrições. Pré-aprovado automaticamente (`pre_approved`). | `bureau` ➔ `docs` ➔ `risk` ➔ `compliance` ➔ `decision` |
| `hitl_required` | Solicitação > R$ 50k. Requer revisão humana obrigatória. | `bureau` ➔ `docs` ➔ `risk` ➔ `compliance` ➔ `decision` ➔ `handoff` |
| `compliance_fail` | Falha nos testes de KYC/PLD. Negado imediatamente por Compliance. | `bureau` ➔ `docs` ➔ `risk` ➔ `compliance` ➔ **STOP** (sem decisão final) |
| `bureau_error` | Erro crítico/indisponibilidade no Bureau. Encaminha para revisão humana direta. | `bureau` (falha) ➔ `handoff` ➔ **STOP** |
| `multi_error` | Falha simultânea no Bureau e na verificação de documentos. Escalado. | `bureau` (falha) ➔ `docs` (falha) ➔ `handoff` ➔ **STOP** |

---

## ⚡ Setup e Execução

### Pré-requisitos
* Python 3.10 ou superior
* Node.js v18+ (para execução do Promptfoo)

### Instalação das dependências
```bash
cd src
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Configuração das Variáveis de Ambiente
Copie o arquivo de exemplo e insira suas chaves do Sensedia AI Gateway:
```bash
cp .env.example .env
```

Campos obrigatórios no `.env`:
```ini
AI_GATEWAY_CLIENT_ID=seu_client_id
AI_GATEWAY_CLIENT_SECRET=seu_client_secret
AI_GATEWAY_OAUTH_ENDPOINT=https://api.sensedia.com/oauth/token
AI_GATEWAY_LLM_BASE_URL=https://api.sensedia.com/gateway/llm/v1
```

---

## 🧪 Rodando os Evals de Trajetória e Decisão

Temos suítes de validação que garantem compatibilidade e qualidade:

### 1. Rodar os testes de Trajetória:
Executa o Promptfoo com a especificação de testes de comportamento de fluxo:
```bash
export AI_GATEWAY_TOKEN=$(src/.venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); from gateway_auth import gateway_auth; print(gateway_auth.get_token())")
npx promptfoo eval --config evals/trajectory.yaml
```

### 2. Rodar a Suite Global de Homologação:
O script unificado na pasta raiz executa sequencialmente todos os testes:
```bash
./run_all_evals.sh
```

---

## ⛓️ Observabilidade & Tracing (OpenTelemetry)

A arquitetura de observabilidade conta com a integração do **OpenTelemetry SDK**:
* **Rastreamento Padronizado W3C**: Utilização do padrão global `traceparent` (W3C), garantindo interoperabilidade com proxies de mercado e APMs (Jaeger, Tempo, Datadog, Arize Phoenix). O `X-Trace-Id` continua sendo propagado em paralelo como fallback.
* **Mapeamento de Spans Cognitivos**: 
  * `analysis.t1`: Cobre a execução paralela de Bureau de Crédito e Validação de Documentos, estendendo-se até o cálculo final de Risco.
  * `analysis.t2`: Cobre a execução isolada de Compliance.
  * `analysis.t3`: Cobre a consolidação final da proposta de crédito e síntese explicável (Decision).
* **Logging de Eventos de Ferramenta**: Cada chamada de sub-agente registra um evento OTel com o nome do agente, latência real de rede em milissegundos e resultado (`success`, `fail` ou `timeout`).
* **Enriquecimento FinOps**: O `trace_id` W3C e o `span_id` da execução completa são formalmente expostos no objeto de saída de metadados em `_meta.finops`.

---

## ⏳ HITL Assíncrono (Human-in-the-Loop)

O sistema implementa o **HITL Assíncrono baseado em eventos**:
1. **Pausa Não-Bloqueante (`serialize_and_pause`)**: Quando o valor solicitado ultrapassa R$ 50k ou ocorrem múltiplos erros técnicos simultâneos, o orquestrador serializa o estado atual das fases T1 e T2 no Redis/SQLite (com expiração governada por `HITL_TTL_SECONDS`), emite um evento SSE `HITL_REQUIRED` contendo o `traceparent` e o ID da requisição para a interface gráfica e finaliza o processo Python sem reter threads.
2. **Retomada Assíncrona (`POST /resume`)**: Disponibiliza um servidor HTTP A2A dedicado na porta `8086`. O endpoint `/resume`:
   * Valida a autenticação do analista via Bearer Token OAuth2.
   * Valida que o estado não expirou (retorna `410 Gone` se o TTL expirou).
   * Implementa **idempotência de auditoria** contra chamadas concorrentes (retorna `409 Conflict` caso a análise já esteja resolvida).
   * Dispara a execução do Turno 3 (T3 - `decision_synthesize`) de forma assíncrona em uma thread em background e retorna imediatamente `202 Accepted` para o chamador.
3. **Causal Link de Tracing**: No `resume_analysis`, a nova span de T3 reconstrói e cria um `trace.Link` apontando para o `SpanContext` original serializado, garantindo auditoria ponta a ponta.

---

## 📈 Tabela de Evolução da Arquitetura

| Camada | Estado Atual (v0 / Baseline) | Visão de Futuro / Próximos Passos |
| :--- | :--- | :--- |
| **Agentic Loop** | **Loop puro dirigido pelo LLM** com auto-reparação sintática e guardas de conformidade. | Loop com retries autônomos por classe de erro HTTP e fallback de LLM. |
| **Trajectory Evals** | **Validação dinâmica via Promptfoo** (`trajectory.yaml`, `finops.yaml`, `security.yaml`). | Integração de grafos de dependência complexos e red-teaming de prompt injection. |
| **Comunicação A2A / Ferramentas** | **Compliance A2A em Node.js (porta 8085)** + Mocks Python locais em `mock_agents.py`. | Decomposição de Bureau, Risco e Decisão em Servidores MCP (Model Context Protocol). |
| **FinOps & Tracing** | **Cálculo exato em tempo real (BRL)** e **tracing distribuído W3C OpenTelemetry**. | Envio centralizado de spans e métricas de custo para OTel Collector e Arize Phoenix. |
| **Intervenção Humana (HITL)** | **HITL assíncrono não-bloqueante** via Redis/SQLite, `/resume` POST API, SSE e links de tracing. | Interface de cockpit com suporte total a SSE e fila em tempo real. |
| **Memória LTM** | **SQLite local (`db.py`)** + **Event store (`episodic_memory.json`)** com ofuscação semântica. | Memória vetorial (SQLite-vec / Pgvector) integrada com cache semântico no AI Gateway. |
| **Robustez de Ferramentas** | **Simulador de Fallback de Código Python** e tradutor automático de assinaturas inválidas. | Middleware de validação sintática e contratual no próprio proxy do Sensedia AI Gateway. |

---

> 🔒 **LGPD & Segurança**: Todas as operações respeitam as diretrizes de proteção de dados, utilizando tokens e IDs efêmeros para CPFs simulados e sem armazenar PII sem consentimento explícito.
estática com trace ad-hoc | **Cálculo exato em tempo real** e **tracing distribuído com OpenTelemetry (W3C)**. | Consolidação centralizada de custos em coletores OpenTelemetry. |
| **Intervenção Humana (HITL)** | Síncrona, bloqueante e com contenção de threads | **HITL assíncrono não-bloqueante** via Redis, `/resume` POST API, SSE e links de tracing. | Interface UI integrada nativamente com SSE real. |
| **Memória LTM** | Sem persistência de histórico entre chamadas | **Event store estruturado (`episodic_memory.json`)** com ofuscação semântica de stop antecipado. | Uso de banco vetorial (Vector Store) integrado com cache do Sensedia Gateway. |
| **Robustez de Ferramentas** | Quebrava em caso de respostas fora do padrão estruturado | **Simulador de Fallback de Código Python** e tradutor automático de assinaturas inválidas. | Middleware de validação sintática no próprio proxy do Sensedia Gateway. |

---

> 🔒 **LGPD & Segurança**: Todas as operações respeitam as diretrizes de proteção de dados, utilizando tokens e IDs efêmeros para CPFs simulados e sem armazenar PII sem consentimento explícito.