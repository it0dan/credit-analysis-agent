# ADR-004: Fluxo Híbrido Paralelo-Serial entre Sub-agentes

**Status:** ACCEPTED — revoga e substitui o ADR-001 (2026-05-25)
**Data:** 2026-05-30
**Change de origem:** add-orchestrator-agent
**Decididores:** Danilo Amaral, AgentOrchestrador

---

## Contexto

O ADR-001 original definiu a adoção de um fluxo sequencial estritamente serial (`Bureau → Documentos → Risco → Compliance → Decisão`) para a v1 do sistema de análise de crédito. A justificativa residia na facilidade de implementação, traces limpos no Sensedia AI Gateway e asserções determinísticas de sequência nos testes do PromptFoo.

Durante a evolução para o loop agêntico puro na v2 (2026-05-29) e validações com o gateway, identificamos dois impeditivos severos na abordagem serial:
1. **Detecção de Erros Simultâneos:** No cenário adversarial `multi_error` (onde os serviços do Bureau e de Documentos falham simultaneamente), uma execução serial curta o fluxo na primeira falha (Bureau no Turno 1) e escala imediatamente para análise humana. Isso impede que o orquestrador descubra a falha de validação de documentos, impossibilitando a emissão das duas flags simultâneas exigidas pelo contrato de fallback (`"bureau_unavailable"` e `"docs_unverified"`).
2. **Latência Acumulada:** A execução em série de sub-agentes independentes (Bureau e Documentos na primeira etapa, Risco e Compliance na segunda) somava ~3 segundos extras desnecessários ao fluxo total de análise, pressionando o SLO de < 8s definido na especificação.

---

## Opções Consideradas

### Opção A — Serial Puro (ADR-001 original)
Todos os sub-agentes executam um por turno, em ordem estrita.

* **Prós:** Asserções de trajetória são 100% determinísticas em ordem de chaves.
* **Contras:** Latência alta e incapacidade de detectar erros paralelos de infraestrutura.

### Opção B — Fluxo Híbrido Paralelo-Serial (Escolhida)
Paralelização das etapas que não apresentam dependências de dados entre si:
* **Turno 1:** Execução paralela de `bureau_get_score` + `documents_validate` (independentes).
* **Turno 2:** Execução paralela de `risk_evaluate` + `compliance_check` (ambos utilizam dados coletados no Turno 1).
* **Turno 3:** Consolidação final com `decision_synthesize` ou `handoff_to_human`.

* **Prós:** 
  * Redução imediata de ~3s no P95 de latência total da análise de crédito.
  * Habilita a detecção simultânea de indisponibilidades técnicas no cenário `multi_error`.
  * Roteamento limpo e elegante guiado inteiramente pelo `SYSTEM_PROMPT` no loop puro.
* **Contras:** 
  * Trajectory Evals do PromptFoo não podem usar verificações rígidas de sequência estrita (como `tool_sequence_equals`) devido a pequenas variações de ordenação no retorno do mesmo turno pelo LLM.

---

## Decisão

Adotar a **Opção B — Fluxo Híbrido Paralelo-Serial**, revogando formalmente o ADR-001.

A paralelização de sub-agentes independentes provou ser indispensável para satisfazer os critérios de aceitação do `multi_error` e as metas globais de performance (SLOs) sem alterar a robustez das decisões tomadas pelo orquestrador.

---

## Consequências

**Positivas:**
* Redução de latência total da análise em cerca de 3 segundos.
* Cobertura técnica completa e detecção limpa de falhas simultâneas.
* Melhor custo-benefício de FinOps no Gateway devido à redução de turnos gerais no LLM.

**Negativas:**
* Os asserts de trajetória no PromptFoo em `evals/orchestrator.yaml` passam a utilizar asserções baseadas em inclusões e subconjuntos (ex: `contains` ou scripts JavaScript) em vez de ordenações rígidas de string, acomodando variações de turno concorrente perfeitamente.

---

## Referências

* ADR-001: Sequência serial vs paralelo (revogado)
* ADR-003: Do loop híbrido ao loop agêntico puro
* `credit-analysis-demo/orchestrator.py` v2 — implementação de loop puro híbrido
