# ADR-002: Protocolo A2A vs chamada direta de ferramentas MCP

**Status:** ACCEPTED
**Data:** 2026-05-25
**Change de origem:** add-orchestrator-agent
**Decididores:** Danilo Amaral

---

## Contexto

O AgentOrchestrator precisa coordenar 5 sub-agentes especializados. Existem duas
abordagens arquiteturais para essa comunicação:

1. O orquestrador chama diretamente as ferramentas MCP de cada domínio
   (ex: `mcp-bureau.get_score`, `mcp-ocr.validate`)
2. O orquestrador delega para sub-agentes via protocolo A2A, e cada sub-agente
   gerencia suas próprias ferramentas MCP internamente

A escolha define o nível de acoplamento, a separação de responsabilidades e
a capacidade de evolução independente de cada domínio.

---

## Opções Consideradas

### Opção A — Chamada direta de ferramentas MCP pelo orquestrador

O orquestrador conhece e chama diretamente todas as ferramentas:
`get_credit_score`, `validate_document`, `run_risk_model`, `check_kyc`, etc.

**Prós:**
- Menos saltos de rede (menor latência)
- Implementação mais simples na v1
- Menos componentes para operar

**Contras:**
- Orquestrador acumula responsabilidade de todos os domínios
- Qualquer mudança em um MCP Server exige atualização do prompt do orquestrador
- Impossível trocar a lógica interna de um domínio sem afetar o orquestrador
- Contexto do orquestrador cresce com detalhes de cada ferramenta (custo de tokens)
- Contradiz o conceito de MCP padronizando a conexão vertical apresentado na palestra

---

### Opção B — Delegação via A2A para sub-agentes especializados (escolhida)

O orquestrador delega tarefas de domínio para sub-agentes via A2A.
Cada sub-agente é responsável por suas próprias ferramentas MCP.

**Prós:**
- Separação clara de responsabilidades: orquestrador coordena, sub-agentes executam
- Sub-agentes evoluem independentemente (trocar MCP Server de bureau não afeta orquestrador)
- Orquestrador mantém contexto enxuto (não precisa conhecer schemas de cada ferramenta)
- Alinhado com os protocolos da palestra: MCP vertical + A2A horizontal
- Cada sub-agente pode ter seu próprio harness de evals independente

**Contras:**
- Mais componentes para operar e monitorar
- Latência adicional por salto A2A (~100-200ms por chamada)
- Complexidade maior de observabilidade (traces cruzam múltiplos agentes)

---

## Decisão

**Opção B — Delegação via A2A**, pelos seguintes motivos:

A separação de responsabilidades e a capacidade de evolução independente dos domínios
superam o custo de latência adicional. O sistema é uma demonstração de arquitetura
agêntica, portanto a clareza dos protocolos (MCP vertical + A2A horizontal) tem
valor intrínseco para comunicar os conceitos da palestra.

A latência adicional (~500-1000ms total para 5 chamadas A2A) é aceitável dentro
do SLO de 8s definido para o fluxo automático.

---

## Consequências

**Positivas:**
- Cada sub-agente tem prompt, harness e eval próprios (manutenção isolada)
- Mudanças em MCP Servers não propagam para o orquestrador
- Arquitetura comunica claramente os conceitos MCP + A2A da palestra
- Sensedia AI Gateway pode aplicar políticas (rate limit, AuthZ) por sub-agente

**Negativas:**
- +500-1000ms de latência vs chamada direta
- Traces precisam correlacionar múltiplos agentes (suportado pelo Sensedia)
- Operação de 6 agentes em vez de 1

**Critério de revisão:**
Se latência P95 ultrapassar 7s de forma consistente e a análise de profiling
apontar A2A como gargalo → avaliar colapso de sub-agentes de menor complexidade
(ex: Documentos) em ferramentas diretas do orquestrador.

---

## Referências

- Slides da palestra: Protocolos & Integrações (MCP + A2A)
- Decisão técnica DT-002 em `changes/add-orchestrator-agent/design.md`
- SLOs globais em `openspec/project.md`
