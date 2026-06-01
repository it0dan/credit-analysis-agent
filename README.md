# Sistema de Análise de Crédito Multiagente (Arquitetura v2 Homologada)

Este repositório contém o MVP do motor de análise de crédito multiagente baseado na arquitetura de agentes autônomos, utilizando o **Sensedia AI Gateway** e LLMs de última geração (**Gemini 2.5 Flash Lite**).

A versão **v2** introduz uma homologação completa da arquitetura-alvo com 100% de cobertura de testes, validações de trajetória real e robustez avançada no loop agêntico.

---

## 📂 Estrutura do Projeto

```
credit-analysis-agent/
├── README.md                          ← Documentação geral da arquitetura
├── run_all_evals.sh                   ← Orquestrador global de testes/evals
├── openspec/                          ← Contratos OpenAPI e esquemas de dados oficiais
├── evals/                             ← Evals de trajetórias de fluxo v2 (5 cenários)
└── src/                               ← Implementação de referência do runtime
    ├── .env.example                   ← Variáveis de ambiente (copiar para .env)
    ├── gateway_auth.py            ← Autenticação OAuth2 no Sensedia AI Gateway
    ├── mock_agents.py             ← Provedor de ferramentas locais para simulações
    ├── bureau_agent.py            ← Contrato e esquemas de validação do AgentBureau
    ├── compliance_agent.py        ← Runtime do AgentCompliance (com servidor HTTP A2A)
    ├── risk_agent.py              ← Contrato e esquemas do AgentRisk
    ├── decision_agent.py          ← Contrato e esquemas do AgentDecision
    ├── episodic_memory.json       ← Repositório JSON persistente de memória episódica (LTM)
    ├── orchestrator.py            ← Orquestrador principal com loop agêntico autoreparável
    ├── orchestrator_provider.py   ← Provedor Promptfoo isolado para parsing determinístico de JSON
    └── run_evals.sh               ← Script local de execução de evals clássicos
```

---

## 🏛️ Arquitetura e Pilares da v2

A arquitetura v2 implementa os padrões modernos de sistemas agênticos corporativos seguindo 4 pilares de Engenharia de Contexto:

```
                  ┌──────────────────────────────────────────────┐
                  │          Orquestrador (orchestrator.py)      │
                  └──────┬────────────────────────────────┬──────┘
                         │                                │
      (OAuth2 Bearer via gateway_auth)      (Episodic Memory / Event Store)
                         ▼                                ▼
            ┌─────────────────────────┐      ┌─────────────────────────┐
            │   Sensedia AI Gateway   │      │  episodic_memory.json   │
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
                         ├─→ compliance_check()  ──[A2A HTTP POST]──→ compliance_agent.py (Port 8080)
                         ├─→ decision_synthesize()
                         └─→ handoff_to_human()
```

### 1. Contexto & Memória de Longo Prazo (LTM)
* **Isolate (Isolamento)**: Cada turno é uma requisição HTTP REST independente e sem estado para o Gateway.
* **Memória Episódica Persistente**: Persistida em `episodic_memory.json` indexada por CPF. Armazena os resultados das análises passadas, garantindo que o agente reconheça recorrências de fraude ou decisões prévias em execuções subsequentes.
* **Ofuscação Semântica contra Premature Stopping**: Pequenos LLMs sofrem de viés de parada antecipada ao ler palavras como `approved` ou `rejected` no histórico. Na memória e contexto, mapeamos o status para códigos neutros (`CODE_A` para aprovado, `CODE_R` para rejeitado, `CODE_P` para pendente) e removemos as justificativas textuais complexas do contexto operacional ativo.

### 2. Robustez do Loop & Auto-Reparação (Self-Healing)
* **Simulação de Fallback de Tool-Calling**: Corrige o erro `MALFORMED_FUNCTION_CALL` quando o LLM retorna chamadas de ferramentas encapsuladas em blocos de código markdown (`default_api.execute_tool(...)` etc.) em vez de chamadas estruturadas puras.
* **Guardas de Conformidade Ativa**: O orquestrador detecta automaticamente se o modelo tentou encerrar a execução sem passar pelos passos obrigatórios (como verificação de conformidade ou handoff HITL) e injeta instruções corretivas transparentes.
* **Normalizador de Assinatura de Ferramenta**: Traduz argumentos planos enviados de forma incorreta pelo LLM em estruturas aninhadas exigidas pelas assinaturas rígidas dos esquemas (`decision_synthesize`).

### 3. Comunicação A2A (Agent-to-Agent) Distribuída
* O `compliance_agent.py` atua como um microserviço HTTP real (`ComplianceA2AHandler` rodando na porta `8080`), simulando comunicação entre contêineres independentes.
* **Rastreabilidade de Ponta a Ponta**: Propagação obrigatória do header `X-Trace-Id` que correlaciona cada chamada de subagente de forma única em logs distribuídos.

### 4. FinOps & Custos Reais
* Monitoramento preciso e imediato do consumo real de tokens (entrada, saída e cache) a cada turno da API do Gemini.
* Cálculo monetizado em Reais (BRL) baseado nas tabelas de preço oficiais da API, formatado a 6 casas decimais.

---

## 🎯 Cenários de Teste & Trajetória Esperada

A suite de testes cobre 5 fluxos fundamentais descritos em `evals/trajectory.yaml`:

| Cenário | Descrição e Comportamento Esperado | Sequência (Trajectory) Exigida |
| :--- | :--- | :--- |
| `auto_approve` | Solicitação ≤ R$ 50k, sem restrições. Aprovado automaticamente. | `bureau` ➔ `docs` ➔ `risk` ➔ `compliance` ➔ `decision` |
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
pip install -r requirements.txt   # Ou: pip install openai httpx python-dotenv
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

Temos duas suites de validação prontas que garantem 100% de compatibilidade e qualidade:

### 1. Rodar os testes de Trajetória (Cenários v2):
Executa o Promptfoo com a nova especificação de testes de comportamento de fluxo:
```bash
export AI_GATEWAY_TOKEN=$(src/.venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); from gateway_auth import gateway_auth; print(gateway_auth.get_token())")
npx promptfoo eval --config evals/trajectory.yaml
```

### 2. Rodar a Suite Global de Homologação:
O script unificado na pasta raiz executa sequencialmente todos os testes, garantindo retrocompatibilidade total com as validações clássicas de decisão e novos contratos:
```bash
./run_all_evals.sh
```

---

## 📈 Tabela de Evolução da Arquitetura

| Camada | Versão Anterior | Implementado na v2 (Atual) | Próximo Alvo (v3) |
| :--- | :--- | :--- | :--- |
| **Agentic Loop** | Sequenciamento fixo rígido em código Python | **Loop puro dirigido pelo LLM** com suporte a auto-reparação estrutural. | Loop puro com retry autônomo baseado em erros HTTP. |
| **Trajectory Evals** | Inexistente (apenas asserts estáticos de string) | **Validação dinâmica via Promptfoo** (`trajectory.yaml`) garantindo a ordem das chamadas. | Integração de grafos de dependência complexos no Promptfoo. |
| **Comunicação A2A** | Apenas funções locais mockadas em Python | **Servidor HTTP A2A Real** (`compliance_agent.py`) com propagação de headers de rastreamento. | Migração dos demais agentes (Bureau, Risco e Decisão) para microserviços HTTP. |
| **FinOps** | Métrica de tokens ausente ou estática | **Cálculo exato em tempo real** baseado em metadados de resposta e conversão BRL com 6 decimais. | Consolidação dos custos em logs centralizados no OpenTelemetry. |
| **Memória LTM** | Sem persistência de histórico entre chamadas | **Event store estruturado (`episodic_memory.json`)** com ofuscação semântica de stop antecipado. | Uso de banco vetorial (Vector Store) integrado com cache do Sensedia Gateway. |
| **Robustez de Ferramentas** | Quebrava em caso de respostas fora do padrão estruturado | **Simulador de Fallback de Código Python** e tradutor automático de assinaturas inválidas. | Middleware de validação sintática no próprio proxy do Sensedia Gateway. |

---

> 🔒 **LGPD & Segurança**: Todas as operações respeitam as diretrizes de proteção de dados, utilizando tokens e IDs efêmeros para CPFs simulados e sem armazenar PII sem consentimento explícito.