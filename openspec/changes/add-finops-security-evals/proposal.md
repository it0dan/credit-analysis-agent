# Proposta — Fechar a Suite de Evals: FinOps + Security

**Data:** 2026-06-13  
**Autor:** Dan (apresentador NodeBR 2026-06-17)  
**Status:** Aprovado para implementação

---

## Motivação

A palestra "Harness Engineering: Guias, Sensores e Evals para Agentes em Produção" precisa demonstrar, em palco, que o harness do `credit-analysis-agent` não é só sobre trajetória de execução — é também sobre **custo verificável** e **postura de segurança auditável**.

Os evals de trajectória já provam *o quê* o agente faz. Os evals de FinOps e Security provam *quanto custa* e *com quais credenciais* ele opera. Juntos, fecham o loop conceitual: Guides × Sensores × Evals.

Os arquivos `evals/finops.yaml` e `evals/security.yaml` existem em rascunho, mas estão incompletos (campos errados, variáveis indefinidas, testes faltantes). Esta mudança os conclui com qualidade de produção.

---

## Escopo

**Dentro do escopo:**
- Completar `evals/finops.yaml` com todos os asserts necessários (por cenário, W3C trace, span, tokens)
- Completar `evals/security.yaml` com validação de `aud` por agente, fallback gracioso, propagação de trace e mascaramento de CPF
- Criar `evals/thresholds.yaml` para centralizar thresholds de custo por cenário
- Atualizar `run_all_evals.sh` para incluir os dois novos configs, abortar no primeiro erro e imprimir tempo total

**Fora do escopo:**
- Alterações no loop do orquestrador (`orchestrator.py`)
- Novos sub-agentes
- Mudanças no Gateway ou na autenticação
- Enriquecimento do `_meta` (já está completo — veja `design.md`)

---

## Stakeholders

- **Dan** — apresentador NodeBR, precisa da suite verde antes de 2026-06-17
- **Comunidade NodeBR** — audiência que verifica as demos ao vivo
