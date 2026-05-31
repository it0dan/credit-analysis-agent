# ADR-005: Estratégia de versionamento de contrato para o AgentCompliance isolado

**Status:** ACCEPTED  
**Data:** 2026-05-31  
**Change de origem:** isolate-compliance-agent  
**Decididores:** Danilo Amaral  

---

## Contexto

Como parte da evolução da arquitetura v2 para a v3 do sistema de análise de crédito, o `compliance_agent` (AgentCompliance) está sendo extraído para um microsserviço independente, com repositório, ciclo de vida e deploy separados.

**Motivação Técnica:** O domínio de compliance regulatório (KYC, PLD/COAF, consentimento LGPD) é uma capacidade organizacional crítica e transversal. Outros sistemas internos da instituição (como onboarding de clientes, contas, seguros e recuperação de crédito) precisam consumir essas mesmas validações regulatórias sem herdar acoplamento com o sistema de análise de crédito. 

Como a legislação de PLD e KYC (COAF/BACEN) e as diretrizes da LGPD mudam em ritmos próprios e acelerados, o ciclo de deploy do `compliance_agent` precisa ser totalmente desacoplado.

**Desafio:** Múltiplos consumidores em ambientes produtivos distintos passarão a consumir o agente via chamadas de rede A2A. É imperativo definir uma estratégia de versionamento robusta para o contrato (definido no Agent Card `compliance-agent-card.json`) que permita evoluções independentes do agente de compliance sem quebrar os sistemas consumidores existentes (especialmente o loop do orquestrador de crédito).

---

## Opções Consideradas

### Opção A — Versionamento por URL Path (ex: `/v1/compliance`, `/v2/compliance`)

Toda mudança que altere o contrato de forma incompatível gera uma nova rota principal exposta no Sensedia AI Gateway.

* **Prós:**
  * Altamente visível e explícito para desenvolvedores e ferramentas de rede.
  * Facilidade extrema de roteamento e políticas no Sensedia AI Gateway (roteamento por prefixo `/v1/*` para o pod v1, `/v2/*` para o pod v2).
  * Suporte nativo e simples em qualquer linguagem ou biblioteca cliente HTTP.
  * Logs e métricas de uso por versão segregados nativamente no nível do API Gateway.
* **Contras:**
  * Poluição de URI ao longo do tempo se novas versões majoritárias forem criadas com frequência.

---

### Opção B — Versionamento por Accept Header (Content Negotiation)

A versão do contrato é definida no header da requisição, por exemplo:  
`Accept: application/vnd.sensedia.compliance.v1+json`

* **Prós:**
  * Mantém a URI limpa e focada exclusivamente no recurso (`/compliance`).
  * Alinhado com o purismo REST de que a versão é uma representação do recurso, e não o recurso em si.
* **Contras:**
  * Dificulta o roteamento rápido e a aplicação de políticas baseadas em regex simples de URI no API Gateway.
  * Menos intuitivo para ferramentas de teste rápido (curl, Postman) e documentações simples.
  * Requer que o gateway ou a aplicação inspecione o corpo ou headers complexos para direcionar o tráfego.

---

### Opção C — Versionamento por Query Parameter (ex: `/compliance?version=1`)

A versão é passada como parâmetro na string de consulta.

* **Prós:**
  * Simples de ler e entender.
* **Contras:**
  * Dificulta o caching e o roteamento baseado em prefixos no API Gateway.
  * Mistura parâmetros funcionais de busca/comportamento com controle de versão de contrato.

---

## Decisão

A escolha é a **Opção A — Versionamento por URL Path (ex: `/v1/compliance`)**, operado em conjunto com o **Sensedia AI Gateway** como API Facade e ponto único de entrada.

### Justificativa Técnica e de Negócio:
1. **Roteamento Desacoplado no Gateway:** O Sensedia AI Gateway pode gerenciar o ciclo de vida das versões com extrema facilidade, mapeando as rotas públicas `/v1/compliance` e `/v2/compliance` para instâncias ou microsserviços rodando em containers totalmente diferentes no cluster Kubernetes.
2. **Observabilidade e FinOps:** Permite segregar métricas de latência (TTFT), taxas de erro e custos de tokens (FinOps) do Gemini de forma isolada por versão do contrato direto nos dashboards do Gateway.
3. **Simplicidade Operacional:** Em um time pequeno, a facilidade de configurar regras de segurança (OAuth2 scopes diferenciados) e limites de requisição (Rate Limiting) por versão de rota na console do Gateway supera qualquer benefício estético das outras abordagens.

---

## Regras e Diretrizes do Ciclo de Vida do Contrato

Para gerenciar o ciclo de evolução do contrato sem gerar atritos, são estabelecidas as seguintes políticas:

### 1. Política de Breaking vs. Non-Breaking Changes

#### Non-Breaking Changes (Compatíveis com versões anteriores):
* **Definição:** Adição de campos opcionais no JSON de request, adição de novos campos no JSON de resposta, ou acréscimo de novas skills internas/ferramentas MCP opcionais.
* **Ação:** Implementadas e implantadas **em tempo de execução na mesma rota** (ex: mantendo-se na rota `/v1/compliance`).
* **Princípio Exigido:** Todos os consumidores (incluindo o `orchestrator.py`) devem seguir o **Princípio da Robustez (Lei de Postel)**: *Seja conservador no que você envia, seja liberal no que você recebe*. Consumidores devem ignorar silenciosamente campos desconhecidos retornados no payload de resposta (Deserialização Tolerante).

#### Breaking Changes (Incompatíveis):
* **Definição:** Remoção ou renomeação de campos existentes em requests/responses, alteração do tipo de dados de um campo (ex: mudar `kyc_approved` de boolean para string), alteração de cabeçalhos obrigatórios, ou mudanças semânticas que afetem o fluxo crítico (ex: tornar uma regra de PLD impeditiva opcional).
* **Ação:** Criação obrigatória de uma nova versão principal (ex: `/v2/compliance`) e novo deploy do microsserviço correspondente.

### 2. Política de Deprecação (Deprecation & Sunset)
* **Tempo de Transição Mínimo:** Qualquer versão depreciada (ex: v1 após o lançamento da v2) deve ser mantida ativa por no mínimo **90 dias** em ambientes de Homologação e Produção.
* **Sinalização via Gateway:** O Sensedia AI Gateway passará a injetar os headers padrão HTTP da RFC 8594 (`Deprecation`) e RFC 8470 (`Sunset`) nas respostas das requisições para caminhos de versões antigas, sinalizando a data limite de encerramento do serviço.
* **Monitoramento Ativo:** A desativação definitiva de uma rota no Gateway só ocorrerá quando as métricas de telemetria do Sensedia apontarem volume zero de requisições reais nos últimos 15 dias consecutivos.

### 3. Idempotência e Rastreabilidade (Constraints Técnicas)
* **Idempotência por `request_id`:** O microsserviço de compliance isolado deve persistir os resultados das análises temporariamente associados ao `request_id` do corpo da mensagem. Requisições repetidas com o mesmo `request_id` dentro da janela de TTL (padrão 24h) devem retornar imediatamente o mesmo veredito sem reexecutar o loop de LLM, economizando tokens.
* **Trace Propagation:** O header `X-Trace-Id` recebido pelo Gateway é obrigatoriamente propagado para o microsserviço de compliance, que por sua vez deve registrá-lo em seus logs e devolvê-lo no header de resposta, mantendo o rastreamento distribuído unificado.

---

## Exemplos Concretos

### Exemplo 1: Evolução Não-Quebrante (Non-Breaking Change)

**Cenário:** O time de compliance decide adicionar uma pontuação numérica interna de KYC baseada em novos birôs.

* **Alteração no Request (Não-Quebrante):** Nenhum campo existente é removido.
* **Alteração no Response (Não-Quebrante):** Adição do campo opcional `kyc_score`.
  ```json
  // Payload retornado na mesma rota /v1/compliance
  {
    "request_id": "c1a2b3c4-d5e6-7f8a-9b0c-1d2e3f4a5b6c",
    "kyc_approved": true,
    "pld_clear": true,
    "lgpd_consent": true,
    "status": "ok",
    "reason": "null",
    "kyc_score": 850 // Novo campo não-quebrante (adicional)
  }
  ```
* **Impacto no Orquestrador:** O `orchestrator.py` continua funcionando normalmente, pois ignora o campo `kyc_score` desconhecido até que decida utilizá-lo.

---

### Exemplo 2: Evolução Quebrante (Breaking Change)

**Cenário:** O time de compliance é obrigado a mudar o formato de retorno do campo `kyc_approved` de boolean (`true`/`false`) para uma estrutura rica contendo o nível de confiança (`high`, `medium`, `low`).

* **Alteração no Response (Quebrante):** `kyc_approved` deixa de ser boolean.
  ```json
  // Se enviado na v1 quebraria o orchestrator.py de crédito!
  {
    "kyc_approved": {
      "result": "approved",
      "confidence": "high"
    }
  }
  ```
* **Tratamento:** O microsserviço de compliance publica uma nova imagem de container e o Sensedia AI Gateway expõe o novo caminho `/v2/compliance`. 
* O orquestrador de crédito continua batendo em `/v1/compliance` consumindo a representação antiga (com boolean) até ser migrado e testado no ciclo v3, quando passará a consumir `/v2/compliance`.

---

## Consequências

**Positivas:**
* **Isolamento de Deploy:** O time de compliance pode fazer deploys diários de novas regras de PLD e KYC sem afetar o core de crédito.
* **Compatibilidade Assegurada:** Garante que o pipeline clássico e os evals do `credit-analysis-mas` continuem passando sem quebras abruptas.
* **Governança Unificada:** O Sensedia AI Gateway atua como o centralizador de políticas, assegurando segurança de acesso via escopos OAuth2 (`compliance:verify`).

**Negativas:**
* **Gerenciamento de Múltiplos Deploys:** Caso ocorram breaking changes frequentes, o time de infraestrutura precisará manter múltiplas versões do microsserviço de compliance ativas simultaneamente no cluster Kubernetes (ex: v1 e v2).

---

## Referências

* Google A2A Specification (`/.well-known/agent.json`) em `compliance-agent-card.json`
* ADR-002 (Delegação via A2A) em `openspec/adr/adr-002-a2a-vs-direct-tools.md`
* Especificações gerais de contratos em `credit-analysis-openspec/openspec/specs/credit-analysis/spec.md`
