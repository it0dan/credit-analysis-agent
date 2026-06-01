# Proposal: Agente de Compliance

**Change ID:** add-compliance-agent
**Status:** PROPOSED
**Autor:** Danilo Amaral
**Data:** 2026-05-26

---

## Motivação

O AgentCompliance é o guardião regulatório do sistema de análise de crédito.
Ele executa a Etapa 4 da sequência A2A do orquestrador, verificando KYC, PLD e
conformidade LGPD antes que qualquer decisão de crédito seja emitida.

Diferente de todos os outros sub-agentes, o AgentCompliance **não tem fallback**.
Um erro, timeout ou resultado inconclusivo não escala para HITL — resulta em
recusa imediata. Essa restrição é intencional e regulatória: operar sem
verificação de compliance é inaceitável independente do custo ao negócio.

Sem o AgentCompliance especificado, o orquestrador não tem contrato claro para
a Etapa 4, e o sistema carece do agente de maior criticidade regulatória.

---

## Escopo da Mudança

### Incluído
- Identidade e responsabilidades do AgentCompliance
- Engenharia de contexto: o que recebe do orquestrador, o que retorna
- Ferramentas MCP: `mcp-kyc` — schemas de input/output de cada ferramenta
- Política de recusa imediata: quando e como rejeitar sem fallback
- Guides: políticas de execução, restrições e anti-exemplos
- Sensores: métricas e alertas específicos do compliance
- Formato de saída contratual (consumido pelo orquestrador)
- Prompt derivado da spec (SPDD)

### Excluído
- Implementação interna do `mcp-kyc` (MCP Server dedicado)
- Integração com sistemas externos de KYC/PLD (Serasa, COAF, etc.)
- Configuração do Sensedia AI Gateway para este agente
- Eval suite (change separado após todos os sub-agentes estarem especificados,
  ou ao final deste change se o padrão do orquestrador for seguido)

---

## Design de Alto Nível

```
AgentOrchestrator
        │ A2A: compliance.check
        │ Input: { applicant_masked_cpf, request_id }
        ▼
┌─────────────────────────────────┐
│        AgentCompliance          │
│                                 │
│  1. Receber contexto isolado    │  ← apenas CPF mascarado + request_id
│  2. Chamar mcp-kyc              │  → verify_kyc, check_pld, verify_lgpd_consent
│  3. Avaliar resultado           │
│     KYC ok + PLD ok + LGPD ok  │  → retornar approved: true
│     Qualquer falha/timeout      │  → retornar rejected: true (sem escalada)
└─────────────────────────────────┘
        │ Output: { kyc_approved, pld_clear, lgpd_consent, status, reason }
        ▼
AgentOrchestrator
  → se kyc_approved: false ou pld_clear: false → RECUSA IMEDIATA
  → se status: "error" ou "timeout"            → RECUSA IMEDIATA
```

---

## Diferencial em relação aos demais sub-agentes

| Característica         | AgentBureau / AgentRisk / AgentDocuments | AgentCompliance       |
|------------------------|------------------------------------------|-----------------------|
| Fallback em erro       | Escala para HITL                         | **Recusa imediata**   |
| Fallback em timeout    | Escala para HITL                         | **Recusa imediata**   |
| Resultado inconclusivo | Escala para HITL                         | **Recusa imediata**   |
| Pode ser pulado?       | Não (por política do orquestrador)       | **Não, sob nenhuma hipótese** |

---

## Impacto em Specs Existentes

| Spec                        | Tipo de impacto | Descrição                                              |
|-----------------------------|-----------------|--------------------------------------------------------|
| `credit-analysis/spec.md`   | ADDED           | Novo sub-agente: AgentCompliance + ferramenta mcp-kyc  |

---

## Tarefas de Implementação

Ver `tasks.md` para checklist atômico.

---

## Critérios de Aceite deste Proposal

- [ ] Spec do AgentCompliance revisada e aprovada
- [ ] Política de recusa imediata sem fallback documentada e justificada
- [ ] Schema completo do `mcp-kyc` com as 3 ferramentas (verify_kyc, check_pld, verify_lgpd_consent)
- [ ] Guides cobrindo pelo menos 3 anti-exemplos críticos (incluindo tentativa de fallback)
- [ ] Prompt derivado da spec com Prioridade 1 sendo recusa imediata em qualquer falha
- [ ] Eval mínimo: aprovação KYC/PLD ok, recusa KYC falso, recusa PLD positivo, recusa por timeout
