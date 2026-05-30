# ADR-001: Sequência serial vs paralelo entre sub-agentes

**Status:** SUPERSEDED — substituído pelo ADR-004 (2026-05-30)
**Data:** 2026-05-25
**Change de origem:** add-orchestrator-agent
**Decididores:** Danilo Amaral

---

## Contexto

O AgentOrchestrator precisa coordenar 5 sub-agentes (Bureau, Documentos, Risco,
Compliance, Decisão) para compor uma análise de crédito. A ordem e o modo de
execução impactam diretamente latência, rastreabilidade e custo.

Dois dos sub-agentes iniciais (Bureau e Documentos) são funcionalmente independentes
entre si — Bureau consulta score externo, Documentos valida identidade. Não há
dependência de dados entre eles. Isso abre a possibilidade de execução paralela.

---

## Opções Consideradas

### Opção A — Serial puro (escolhida)
Todos os sub-agentes executam em sequência fixa:
`Bureau → Documentos → Risco → Compliance → Decisão`

**Prós:**
- Rastreabilidade completa: cada etapa tem input/output explícito no trace
- Simplicidade de implementação e debugging
- Falha em qualquer etapa interrompe imediatamente, sem desperdício de recursos
- Evals são determinísticos: mesma sequência sempre

**Contras:**
- Latência acumulada: ~3s extra vs execução paralela de Bureau + Documentos
- Subutiliza a capacidade do gateway quando sub-agentes são independentes

---

### Opção B — Paralelo para Bureau + Documentos, serial para o restante
Bureau e Documentos executam em paralelo. Risco aguarda ambos. Compliance e
Decisão executam em sequência após Risco.

**Prós:**
- Redução de ~3s na latência total
- Melhor utilização de recursos

**Contras:**
- Complexidade de orquestração: o agente precisa gerenciar estado de duas
  execuções concorrentes
- Traces paralelos são mais difíceis de correlacionar e auditar
- Erros parciais (um falha, outro não) criam estados intermediários ambíguos
- Evals precisam considerar ordem não-determinística de chegada dos resultados

---

### Opção C — Totalmente paralelo (Bureau + Documentos + Risco + Compliance)
Todos os sub-agentes independentes executam em paralelo. Apenas Decisão aguarda.

**Prós:**
- Latência mínima teórica

**Contras:**
- Risco depende de Bureau (score) e Documentos (renda confirmada) — seria
  necessário introduzir uma barreira de sincronização, tornando a lógica complexa
- Compliance pode ser acionado com dados incompletos se Bureau ou Documentos
  ainda não retornaram
- Alto risco de alucinação no AgentDecision ao consolidar resultados chegando
  fora de ordem

---

## Decisão

**Opção A — Serial puro**, pelo menos até a v1 do sistema estar validada em produção.

A rastreabilidade e a simplicidade de evals superam o ganho de latência nesta fase.
O SLO definido (< 8s para créditos até R$ 50k) é atingível com execução serial,
considerando os timeouts definidos por sub-agente.

---

## Consequências

**Positivas:**
- Traces limpos e auditáveis no Sensedia AI Gateway
- Evals determinísticos e reproduzíveis com PromptFoo
- Prompt do orquestrador mais simples (sem lógica de fork/join)

**Negativas:**
- Latência ~3s acima do que seria possível com Opção B
- Se Bureau ou Documentos tiverem alta latência no P95, o SLO pode ser pressionado

**Critério de revisão:**
Após 30 dias de dados de SLO em produção, avaliar:
- Se latência P95 > 7s em mais de 5% das requisições → migrar para Opção B
- Manter serial se P95 < 6s em 95% dos casos

---

## Referências

- Decisão técnica DT-001 em `changes/add-orchestrator-agent/design.md`
- SLOs globais em `openspec/project.md`
