# Tasks: Agente de Risco

**Change ID:** add-risk-agent
**Derivado de:** proposal.md

> Marque cada item com [x] conforme concluído.
> Não avance para a fase Apply sem todas as tasks de Spec Definition concluídas.

---

## Fase 1 — Spec Definition

### 1.1 Identidade e responsabilidades
- [x] Definir identidade: nome, papel, modelo de fundação, runtime
- [x] Documentar responsabilidades: o que DEVE e NÃO DEVE fazer (exclusão de PII)
- [x] Registrar explicitamente: comportamento sob falha do bureau ou renda ilegível

### 1.2 Engenharia de contexto
- [x] Definir janela de contexto: dados recebidos do orquestrador (score, renda, valor solicitado, request_id)
- [x] Documentar política de isolamento: não recebimento de PII para assegurar equidade e conformidade
- [x] Definir formato de output contratual de risco para o orquestrador

### 1.3 Ferramentas MCP (mcp-risk)
- [x] Definir a ferramenta MCP de cálculo determinístico: `evaluate_risk_model`
- [x] Definir schemas de input/output para a chamada da ferramenta MCP
- [x] Documentar equações de risco a serem aplicadas no servidor MCP (Amortização teórica em 12 parcelas, IC, IS, Risk Tiers)
- [x] Definir timeouts e política de retry da ferramenta MCP

### 1.4 Guides e Sensores (feedforward/feedback)
- [x] Escrever política de execução de risco
- [x] Documentar anti-exemplos críticos:
  - Anti-exemplo 1: alucinar o cálculo estatístico internamente em vez de chamar o `mcp-risk`
  - Anti-exemplo 2: assumir ou chutar renda quando o `income_value` for 0 ou ilegível
  - Anti-exemplo 3: expor dados de CPF ou informações confidenciais do solicitante
- [x] Listar métricas de risco a monitorar no Sensedia AI Gateway
- [x] Definir alertas de FinOps e latência de processamento

---

## Fase 2 — Prompt (SPDD)

### 2.1 Derivação do prompt
- [x] Seção: Identidade e papel do AgentRisk
- [x] Seção: Contexto financeiro isolado recebido
- [x] Seção: Ferramentas disponíveis (`evaluate_risk_model`)
- [x] Seção: Regras de processamento e prioridades de validação
- [x] Seção: Tratamento de renda nula / ilegível
- [x] Seção: Anti-exemplos de viés e alucinação matemática
- [x] Seção: Formato exclusivo de retorno JSON estrito

### 2.2 Validação do prompt
- [x] Verificar rastreabilidade de todas as regras com a especificação
- [x] Confirmar que o prompt não contém referências a dados de CPF ou nomes reais
- [x] Revisar que o prompt induz o agente a utilizar unicamente o `mcp-risk` para computar os dados estatísticos

---

## Fase 3 — Archive e Fusão de Specs

- [x] Mesclar a especificação do AgentRisk no arquivo principal `openspec/specs/credit-analysis/spec.md`
- [x] Atualizar o arquivo global `project.md` se houver alguma inconsistência
- [x] Mover a pasta `changes/add-risk-agent/` para `changes/archive/`
