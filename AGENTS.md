# AGENTS.md — credit-analysis-agent

## 1. Visão Geral
Este documento constitui a fonte canônica de verdade para a arquitetura, regras de negócio e interfaces do sistema multiagente de análise de crédito da organização. Desenvolvido integralmente utilizando a stack Python, o sistema foi projetado sob os princípios de desacoplamento absoluto de serviços e orquestração determinística de inteligência artificial.

Toda e qualquer comunicação inter-agentes ou requisições direcionadas às capacidades dos agentes são intermediadas de forma centralizada pelo **Sensedia AI Gateway**. Esta infraestrutura provê controle de taxa (rate limiting), rastreabilidade de requisições, segurança ponta a ponta e auditoria transparente sobre os fluxos cognitivos e interações do ecossistema de crédito.

---

## 2. Loop Agêntico (Orquestração por Turnos)
A execução do fluxo de análise de crédito é estruturada em uma sequência determinística de três turnos cognitivos híbridos (paralelo-serial). Um turno subsequente somente será iniciado após o encerramento e consolidação de todas as respostas do turno anterior:

1. **Turno 1 (T1) — Paralelo:** Execução simultânea das análises dos agentes `bureau` e `risk`. O objetivo é obter rapidamente a pontuação cadastral externa e realizar a modelagem prévia de risco financeiro.
2. **Turno 2 (T2) — Paralelo:** Execução do agente `compliance`. Este turno é isolado e dedicado a verificações profundas de segurança, conformidade legal e políticas corporativas de prevenção à lavagem de dinheiro (PLD) e financiamento ao terrorismo (FTP).
3. **Turno 3 (T3) — Serial:** Execução do agente `decision`. Este agente consome as saídas estruturadas geradas em T1 e T2 para consolidar o parecer técnico e proferir a resposta definitiva da proposta de crédito.

### Mecanismo de Short-circuit
Para otimizar custos e mitigar riscos operacionais, o sistema implementa um fluxo de desvio rápido (*short-circuit*). Caso qualquer agente em T1 ou T2 identifique uma falha impeditiva crítica ou suspeita severa de fraude, a execução dos turnos seguintes é interrompida imediatamente. Um processo de intervenção humana (**HITL - Human-In-The-Loop**) é disparado de forma instantânea para avaliação manual do caso.

---

## 3. Invariantes Críticos do Sistema
Estas diretrizes arquiteturais representam restrições técnicas inegociáveis. Qualquer desvio invalidará a segurança e a integridade da aplicação:

* **Zero Direct Calls (Comunicação via Gateway):** Absolutamente nenhum agente ou serviço interno tem permissão para realizar chamadas diretas a outro agente. Toda comunicação do ecossistema transita obrigatoriamente através do Sensedia AI Gateway, autenticada por fluxos robustos de **OAuth2** com a inclusão do cabeçalho de rastreamento padronizado W3C `traceparent` (OpenTelemetry) e com o cabeçalho adicional `X-Trace-Id` como fallback ativo de retrocompatibilidade.
* **Natureza Externa do Compliance Agent:** O `compliance-agent` é classificado formalmente como um agente A2A (Agent-to-Agent) externo. Ele não deve ser projetado, modelado ou integrado como se fosse um microsserviço padrão ou biblioteca interna da aplicação credit-analysis-agent.
* **HITL Assíncrono e Não-Bloqueante:** O fluxo de intervenção humana (HITL) é estritamente assíncrono e não-bloqueante. Quando a revisão humana é acionada, o estado da análise (T1 e T2) é serializado em Redis, SQLite local e memória de processo com TTL de expiração controlado por `HITL_TTL_SECONDS` (default: 86400s), um evento SSE `HITL_REQUIRED` é disparado para a interface AG-UI e o processo Python encerra imediatamente (liberando a thread). A retomada ocorre via endpoint seguro `POST /resume` que autentica o operador e executa assincronamente a consolidação em T3.
* **Rigidez e Governança do Orquestrador:** O arquivo `src/orchestrator.py` é o núcleo motor do sistema. Qualquer alteração estrutural, comportamental ou de ordem lógica neste componente requer obrigatoriamente a aprovação e submissão formal de um **ADR (Architecture Decision Record)** antes de sua implementação prática no repositório.

---

## 4. Contratos e SLAs dos Agentes
Para garantir a privacidade dos titulares e conformidade rígida com a Lei Geral de Proteção de Dados (LGPD), todas as requisições trafegam o CPF do cliente em formato mascarado (ex: `***.###.###-**`).

| Agente | Input do Contrato | Output Esperado | SLA Limite |
| :--- | :--- | :--- | :--- |
| **`bureau`** | CPF Mascarado | Score de crédito consolidado e histórico financeiro resumido. | `1500 ms` |
| **`risk`** | CPF Mascarado | Faixa de risco associada (A a G) e recomendação preliminar. | `2000 ms` |
| **`compliance`** | CPF Mascarado | Flags de conformidade, restrições criminais ou pendências jurídicas. | `3000 ms` |
| **`decision`** | Contexto acumulado de T1 e T2 | Parecer final de pré-aprovação, aprovação, rejeição ou HITL e justificativa. | `4000 ms` |

---

## 5. Workflow de Mudanças (OpenSpec)
Toda evolução arquitetural ou funcional implementada neste repositório deve obrigatoriamente seguir a esteira estruturada da metodologia OpenSpec. Atalhos não são permitidos. O fluxo linear de arquivos de especificação é:

`proposal.md → design.md → spec.md → tasks.md → prompt.md`

1. **`proposal.md`**: Define o escopo do problema, motivação de negócios, requisitos gerais e proposta de valor.
2. **`design.md`**: Detalha as escolhas de arquitetura de software, diagramas de fluxo e modelagem lógica.
3. **`spec.md`**: Formaliza de maneira rigorosa os contratos de APIs, novos esquemas JSON e transições de estado.
4. **`tasks.md`**: Decompõe a implementação em tarefas de engenharia atômicas, sequenciais, testáveis e com critérios de aceitação claros.
5. **`prompt.md`**: Consolida as instruções otimizadas para IA geradora com foco em desenvolvimento assistido (SPDD).

---

## 6. Architecture Decision Records (ADRs) Vigentes
O histórico e evolução técnica das decisões de design do sistema estão registrados sob as seguintes regras de vigência:

* **ADR-002 (ACCEPTED):** Estipula a adoção do modelo de integração A2A direta, proibindo acoplamentos manuais de bibliotecas.
* **ADR-004 (ACCEPTED):** Define e consolida o loop híbrido de execução por turnos e paralelização cognitiva (T1, T2 e T3).
* **ADR-005 (ACCEPTED):** Padroniza as regras para versionamento, retrocompatibilidade e evolução de APIs de compliance.
* **ADR-006 (ACCEPTED):** Define a adoção do OpenTelemetry SDK para rastreamento padronizado com propagação W3C (traceparent) mantendo retrocompatibilidade com X-Trace-Id.
* **ADR-007 (ACCEPTED):** Define a adoção de autenticação inter-agente via tokens JWT com a claim de audiência (aud) específica por agente e caching local com validação de expiração.
* **ADR-009 (ACCEPTED):** Define SQLite (`src/credit_analysis.db`) como store durável local para análises e estados HITL, com seed idempotente de `episodic_memory.json`.
* **ADR-001 (SUPERSEDED):** Substituído integralmente pelas diretrizes consolidadas nas decisões arquiteturais posteriores.
* **ADR-003 (REVISED):** Revisado detalhadamente em função das mudanças no pipeline do Gateway. Não deve ser considerado para novas implementações.

---

## 7. Testes de Qualidade e Evals
Para garantir a assertividade da tomada de decisão jurídica e de crédito, a integridade estrutural e funcional das trajetórias executadas pelo orquestrador deve ser sistematicamente aferida via framework **PromptFoo**.

## Como Rodar os Evals

### Suite existente (regressão)
```bash
cd credit-analysis-mas/credit-analysis-demo
npx promptfoo eval --config evals/orchestrator.yaml   # 12/12 ✓
npx promptfoo eval --config evals/trajectory.yaml     # T1/T2/T3 ✓
```

### Suite end-to-end (novos)
```bash
npx promptfoo eval --config evals/finops.yaml
npx promptfoo eval --config evals/security.yaml
```

### Suite completa
```bash
./run_all_evals.sh
```

### Variáveis de threshold (FinOps)
```bash
EVAL_COST_THRESHOLD_BRL=0.10 EVAL_TOKEN_THRESHOLD=4000 \
  npx promptfoo eval --config evals/finops.yaml
```

### Teste de chamada direta (segurança)
```bash
# Requer compliance-agent rodando na porta 8085
python evals/scripts/direct_call_test.py
```

---

## 8. Monitoramento de Custos (FinOps)
A viabilidade financeira do sistema multiagente é ativamente monitorada. Toda resposta gerada e interpretada pelas APIs de LLM deve computar e registrar seu custo estimado de execução. O orquestrador tem a obrigação de injetar o valor calculado nos metadados de saída de cada operação, respeitando exatamente a seguinte chave JSON de destino:

`output._meta.finops.estimated_cost_brl`

---

## 9. Variáveis de Ambiente Obrigatórias
O sistema requer as seguintes chaves de configuração declaradas em ambiente ou em arquivo `.env` local para sua correta inicialização:

```bash
# Autenticação e Credenciais no Sensedia AI Gateway
AI_GATEWAY_CLIENT_ID="<client-id-for-oauth>"
AI_GATEWAY_CLIENT_SECRET="<client-secret-for-oauth>"
AI_GATEWAY_OAUTH_ENDPOINT="https://gateway.sensedia.com/oauth/token"

# Endpoints e URLs de Integração Cognitiva
AI_GATEWAY_LLM_BASE_URL="https://gateway.sensedia.com/ai/v1"
AI_GATEWAY_MCP_BASE_URL="https://gateway.sensedia.com/mcp/v1"
MCP_SERVER_CREDIT="credit-mcp-server"

# Porta de Serviço Externa do Agente de Compliance (A2A)
A2A_COMPLIANCE_PORT=8085

# Mapeamento de audiências JWT para autenticação inter-agente (JSON string)
AI_GATEWAY_JWT_AUDIENCE_MAP='{"bureau-agent":"https://api.sensedia.com/aud/bureau","documents-agent":"https://api.sensedia.com/aud/documents","risk-agent":"https://api.sensedia.com/aud/risk","compliance-agent":"https://api.sensedia.com/aud/compliance","decision-agent":"https://api.sensedia.com/aud/decision"}'
```

---

## 10. Identidade dos Agentes (A2A Auth)
Para garantir o princípio do privilégio mínimo e o isolamento seguro nas comunicações Agent-to-Agent (A2A), o sistema implementa uma camada rigorosa de identidade e autenticação baseada em tokens JWT específicos por agente destino:

1. **Geração Dinâmica de Tokens por Audiência (`aud`):**
   - O orquestrador e os sub-agentes nunca compartilham um token genérico. Em vez disso, ao disparar uma chamada para um agente destino, o componente `gateway_auth.py` intercepta a chamada, pesquisa pelo identificador do agente e localiza a audiência específica correspondente.
   - A requisição de geração de token de Client Credentials enviada ao Sensedia AI Gateway passa a incluir a chave `audience` no corpo da requisição HTTP POST. O gateway então emite um token cuja claim `aud` é vinculada especificamente àquele sub-agente.

2. **Mapeamento de Audiências (`AI_GATEWAY_JWT_AUDIENCE_MAP`):**
   - O vínculo entre a identidade lógica do agente (ex: `"bureau-agent"`) e sua URI de audiência no Gateway é definido dinamicamente pela variável de ambiente `AI_GATEWAY_JWT_AUDIENCE_MAP` em formato JSON.

3. **Cache de Tokens Local e Gerenciamento de Expiração:**
   - Para maximizar a performance e evitar chamadas excessivas ao servidor OAuth2 do Gateway, os tokens são armazenados localmente em um cache em memória.
   - Antes de retornar um token em cache, o sistema decodifica o payload Base64 do JWT e avalia a claim de expiração (`exp`). O token em cache é reutilizado apenas se a validade atual for maior que a margem de segurança crítica de **30 segundos** antes do término oficial do token. Caso contrário, um novo token é requisitado automaticamente de forma transparente.

4. **Resiliência e Fallback:**
   - Caso a variável `AI_GATEWAY_JWT_AUDIENCE_MAP` não esteja definida ou não possua a mapeação para o agente destino, o sistema realiza um fallback automático e gracioso para gerar um token Client Credentials padrão (sem audience) emitindo um log do tipo `Warning`. Isso garante o funcionamento transparente da aplicação em ambientes locais, testes de integração simplificados ou cenários de desenvolvimento inicial.

---

## 11. Contexto de Sessão

* **Ao iniciar:** Leia `.agent/handoff.md`. Se não estiver vazio, o conteúdo representa o estado exato de onde a última sessão parou — siga a partir daí.
* **Ao encerrar:** Atualize `.agent/handoff.md` com:
  * O que foi implementado ou decidido nesta sessão
  * Estado atual dos arquivos modificados
  * Próximo passo concreto (ação específica, não direção genérica)
  * Qualquer invariante nova que emergiu durante o trabalho
