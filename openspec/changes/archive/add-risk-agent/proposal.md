# Proposal: Agente de Risco

**Change ID:** add-risk-agent
**Status:** PROPOSED
**Autor:** Danilo Amaral
**Data:** 2026-05-29

---

## Motivação

O **AgentRisk (Agente de Risco)** é o cérebro estatístico e financeiro do sistema de análise de crédito. Ele executa a **Etapa 3** da sequência A2A do orquestrador, sendo responsável por calcular a probabilidade de inadimplência (Probability of Default - PD), gerar o score de risco interno e atribuir uma faixa de risco (Risk Tier).

Sem a especificação formal do AgentRisk:
1. O orquestrador depende de mocks pretos que impossibilitam a calibragem correta das faixas de decisão.
2. O sistema não possui regras claras para avaliar o comprometimento de renda (parcela simulada / renda líquida comprovada) em relação ao montante solicitado.
3. Não há isolamento de contexto adequado sobre os critérios matemáticos e estatísticos de risco de crédito em relação às outras verificações (como dados pessoais diretos ou compliance).

---

## Escopo da Mudança

### Incluído
- Identidade e responsabilidades do **AgentRisk**.
- Engenharia de contexto isolada: restrição de parâmetros de entrada às informações estritamente financeiras (score do bureau, renda comprovada e valor solicitado).
- Definição do cálculo analítico de Risco (score interno de 0 a 100, probabilidade de default e faixa de risco).
- Política de tolerância a falhas e escalabilidade para HITL com a flag `risk_unavailable` em caso de erro técnico.
- Guides operacionais, políticas de execução e anti-exemplos críticos (como viés ou alucinação estatística).
- Sensores e métricas para monitoramento no Sensedia AI Gateway.
- Formato de saída contratual (consumido pelo orquestrador e repassado para o `AgentDecision`).
- Prompt derivado da especificação (SPDD) para o AgentRisk.

### Excluído
- Implementação física de modelos de Machine Learning (Python/scikit-learn ou ferramentas estatísticas equivalentes).
- Modelagem de taxas de juros ou prazos customizados para o parcelamento (será simulada uma amortização padrão na v1).
- Integração em tempo real com bancos de dados de histórico financeiro interno (memória semântica resolve isso na v1).

---

## Design de Alto Nível

```
AgentOrchestrator
        │ A2A: risk.evaluate
        │ Input: { bureau_score, income_value, requested_amount, request_id }
        ▼
┌─────────────────────────────────┐
│           AgentRisk             │
│                                 │
│  1. Receber contexto isolado    │  ← Sem nomes, CPFs ou links de documentos
│  2. Avaliar capacidade de pago  │  ← Comprometimento de renda em relação ao valor
│  3. Computar Score Interno      │  ← Correlação entre bureau_score e renda
│  4. Definir Faixa de Risco      │  → low, medium, high
└─────────────────────────────────┘
        │ Output: { internal_score, default_probability, risk_tier, status }
        ▼
AgentOrchestrator
  → Se status: "error" ou "timeout" → Escala para HITL (flag: risk_unavailable)
  → Se status: "ok"                  → Segue para compliance.check
```

---

## Comparativo de Isolamento de Contexto

| Sub-Agente | Contexto Recebido | O que NÃO deve saber (Isolamento) |
|---|---|---|
| **AgentBureau** | CPF Mascarado, Request ID | Renda, valor solicitado, regras de risco. |
| **AgentDocuments** | URLs dos Documentos, Nome, Request ID | Score de bureau, valor solicitado, restrições financeiras. |
| **AgentRisk** | Score de Bureau, Renda, Valor Solicitado, Request ID | **CPF, nome real do cliente, gênero, e-mail, documentos brutos.** |
| **AgentCompliance** | CPF Mascarado, Request ID | Renda, score de bureau, valor solicitado, probabilidade de default. |

---

## Impacto em Specs Existentes

| Spec | Tipo de impacto | Descrição |
|---|---|---|
| `credit-analysis/spec.md` | ADDED | Integração do novo sub-agente: AgentRisk e definição de suas interfaces de A2A na Etapa 3. |

---

## Tarefas de Implementação

Ver `tasks.md` para o checklist atômico de execução.

---

## Critérios de Aceite deste Proposal

- [ ] Especificação do **AgentRisk** revisada e aprovada pelo usuário.
- [ ] Regras matemáticas de composição do score de risco interno e probabilidade de default documentadas.
- [ ] Schema contratual de entrada e saída unificado com a implementação atual do orquestrador.
- [ ] Guides definindo o comportamento do agente perante rendas comprovadas nulas ou inconsistentes.
- [ ] Prompt SPDD do AgentRisk estruturado e isolado, livre de dados pessoais identificáveis (PII).
- [ ] Evals mínimos validados: aprovação de baixo risco, comportamento em alto comprometimento de renda, e tratamento de erro de timeout técnico.
