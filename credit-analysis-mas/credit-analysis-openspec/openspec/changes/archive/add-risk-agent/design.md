# Design: Agente de Risco

**Change ID:** add-risk-agent
**Status:** ACCEPTED
**Autor:** Danilo Amaral
**Data:** 2026-05-29

---

## Contexto

O **AgentRisk** executa a **Etapa 3** da sequência A2A do orquestrador. Ele atua como o motor de decisão quantitativa do sistema. Recebe dados financeiros refinados do solicitante e avalia a capacidade de crédito, estimando se a solicitação deve ser aprovada do ponto de vista puramente estatístico de risco e inadimplência.

Este documento registra as decisões técnicas específicas deste agente para orientar o desenvolvimento do seu runtime e prompts.

---

## Diagrama C4 — Nível de Componente

```
┌──────────────────────────────────────────────────────────────────┐
│  Sistema de Análise de Crédito [Container: Sensedia AI Gateway]  │
│                                                                  │
│  AgentOrchestrator ──A2A: risk.evaluate──▶ AgentRisk             │
│                                              │                   │
│  ┌───────────────────────────────────────────┼──────────────┐   │
│  │  AgentRisk [Component]                    │              │   │
│  │                                           ▼              │   │
│  │  ┌──────────────┐   ┌─────────────────────────────────┐  │   │
│  │  │ Context      │   │ Risk Engine (LLM)               │  │   │
│  │  │ Receiver     │   │                                 │  │   │
│  │  │ (valida e    │   │  Aplica playbooks de crédito e  │  │   │
│  │  │  isola input)│   │  chama ferramenta mcp-risk      │  │   │
│  │  └──────┬───────┘   └─────────────┬───────────────────┘  │   │
│  │         └─────────────────────────┘                      │   │
│  │                        │                                 │   │
│  │             ┌──────────┴──────────┐                      │   │
│  │             ▼                     ▼                      │   │
│  │       [status: "ok"]       [status: "error"]             │   │
│  │       retorna scores e     escalabilidade HITL           │   │
│  │       tier de risco        (risk_unavailable)            │   │
│  │                                                          │   │
│  └──────────────────────────────────────────────────────────┘   │
│                   │ MCP                                          │
│                   ▼                                              │
│            [mcp-risk server]                                     │
│     (Executa equações estatísticas de PD e Score)                 │
└──────────────────────────────────────────────────────────────────┘
```

---

## Decisões Técnicas deste Change

### DT-001 — Isolamento de PII e Viés (Princípio de Equidade)

**Problema:** Modelos de crédito não devem conter preconceitos de raça, gênero, CEP ou outros dados pessoais protegidos (fairness). Além disso, dados como CPF não devem circular desnecessariamente (LGPD).

**Decisão:** O AgentRisk receberá **zero** informações que permitam a identificação direta do indivíduo (PII). Ele terá acesso apenas a números:
- `bureau_score` (0–1000)
- `income_value` (Renda comprovada líquida mensal)
- `requested_amount` (Valor do crédito solicitado)
- `request_id` (Para correlação transacional)

**Razão:**
- Garante total conformidade regulatória com a LGPD e políticas antitruste/antidiscriminação.
- Isola o processo cognitivo de avaliação de risco às variáveis puramente de capacidade de pagamento e perfil de crédito consolidado.

**Consequência:**
- O payload de entrada do A2A `risk.evaluate` é estritamente livre de dados textuais de cadastro.
- Se o orquestrador passar qualquer campo extra (ex: nome, CPF), o `AgentRisk` deve retornar um erro de validação.

---

### DT-002 — Motor Estatístico em MCP Dedicado (`mcp-risk`)

**Problema:** LLMs são excelentes em raciocínio semântico, mas ruins em aritmética precisa e cálculo de fórmulas matemáticas complexas em ponto flutuante. Como calcular a Probabilidade de Default (PD) e o score de risco interno com precisão determinística?

**Decisão:** Toda a matemática estatística pesada será encapsulada na ferramenta `evaluate_risk_model` fornecida pelo **`mcp-risk`**. O AgentRisk (LLM) atua como o orquestrador local desse sub-domínio, validando regras de negócio e limites regulatórios, além de justificar o output.

**Razão:**
- Evita alucinações aritméticas do LLM.
- Permite que o time de Ciência de Dados atualize o modelo estatístico (Regressão Logística ou XGBoost) no servidor MCP sem a necessidade de reescrever prompts ou alterar o runtime do agente.

**Consequência:**
- A especificação cria formalmente o MCP Server `mcp-risk` e sua ferramenta `evaluate_risk_model`.

---

## Engenharia do Modelo Estatístico (`evaluate_risk_model`)

O modelo estatístico simulado realiza as seguintes computações:

1.  **Comprometimento de Renda (Income Commitment - IC):**
    Assumindo uma amortização teórica em 12 parcelas sem juros na v1 para fins de análise simplificada:
    $$\text{IC} = \frac{\text{requested\_amount} / 12}{\text{income\_value}}$$
    *   Se $IC > 0.30$ (comprometimento superior a 30%), a probabilidade de default aumenta exponencialmente.

2.  **Score de Risco Interno (Internal Score - IS):**
    Composto pela ponderação entre o score de bureau externo e o comprometimento de renda:
    $$\text{IS} = (\text{bureau\_score} \times 0.6) + ((1 - \text{IC}) \times 400 \times 0.4)$$
    *Nota: Se o IC for maior que 1 (renda insuficiente para cobrir a parcela simulada), o componente de renda zera.*

3.  **Faixa de Risco (Risk Tier):**
    *   **Low Risk:** $\text{IS} \ge 70$ e $\text{PD} \le 0.05$
    *   **Medium Risk:** $35 \le \text{IS} < 70$ e $0.05 < \text{PD} \le 0.15$
    *   **High Risk:** $\text{IS} < 35$ ou $\text{PD} > 0.15$

---

## Formato de Saída Contratual A2A

```json
{
  "request_id": "string (UUID)",
  "internal_score": "integer (0–100)",
  "default_probability": "number (0.00–1.00)",
  "risk_tier": "enum: low | medium | high",
  "income_commitment_ratio": "number (0.00–99.99)",
  "status": "enum: ok | error | timeout",
  "reason": "string (presente em caso de erro, ex: 'risk_calculation_failed')",
  "processing_time_ms": "number"
}
```
