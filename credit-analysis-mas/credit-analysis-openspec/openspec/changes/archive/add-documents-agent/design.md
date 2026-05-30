# Design: Agente de Validação de Documentos (AgentDocuments)

**Change ID:** add-documents-agent  
**Status:** ACCEPTED  
**Autor:** Danilo Amaral  
**Data:** 2026-05-28  

---

## Contexto

O **AgentDocuments** executa a Etapa 2 da sequência A2A do orquestrador. Ele recebe URLs dos arquivos (identidade e holerite/extrato), faz a chamada às ferramentas OCR de validação e extração de dados e unifica as respostas. O output deste agente é essencial para o `AgentRisk` calibrar o modelo de probabilidade de default usando a renda comprovada real.

Este documento registra as decisões de engenharia e escolhas de design exclusivas para este sub-agente.

---

## Decisões Técnicas deste Change

### DT-001 — Retry com Backoff Estendido (5s por tentativa)

> [!NOTE]
> APIs de OCR baseadas em nuvem sofrem de maior variação de latência e timeouts transientes no processamento de imagens e PDFs multifolhas do que simples consultas a bancos de dados.

- **Problema:** Um timeout simples na primeira tentativa descartaria a análise de documentos, enviando a proposta diretamente para análise manual (HITL). Isso aumenta a fila humana desnecessariamente.
- **Decisão:** Implementar a política de 2 retries (total de até 3 tentativas) com exponential backoff (1s após tentativa 1, 2s após tentativa 2). O timeout individual da ferramenta é de **5s**.
- **Razão:** O tempo médio de resposta (P95) das APIs de OCR sob carga é de ~3.5s. Definir um limite de 5s garante margem operacional segura, e os retries resolvem problemas transientes (como erros de upload ou gateway timeout).
- **Consequência:** No pior cenário de erro persistente (3 timeouts de 5s + 3s de backoff acumulado), o agente consome 18s. Isso excede o SLO inicial de 8s do orquestrador. No entanto, o tradeoff é aceitável: falha permanente em documentos resulta em HITL obrigatório (`docs_unverified`), e 18s de processamento no pior caso é aceitável para um fluxo de contingência humana.

---

### DT-002 — Tolerância Inteligente de Nome (Fuzzy Matching)

- **Problema:** Validações determinísticas estritas (ex: `document_name === applicant_name`) causam falsas reprovações em casos legítimos devido a acentuações faltantes, caixa alta/baixa, ou abreviações de sobrenomes intermediários (ex: "João Silva" vs "João da Silva" ou "João S. Silva").
- **Decisão:** O `AgentDocuments` delegará a inteligência de fuzzy matching ao próprio LLM na etapa de síntese de decisão (Turno 2). A ferramenta MCP `validate_identity` retorna o nome bruto lido no documento (`document_name`) e uma flag de validade técnica do documento. O LLM do agente compara o `document_name` com o `applicant_name` cadastrado.
- **Razão:** LLMs são excepcionalmente bons em avaliar similaridade de nomes e abreviações culturais sem a necessidade de escrever regras heurísticas complexas em código (regex, algoritmos de Levenshtein rígidos).
- **Consequência:**
  - O prompt de sistema especifica explicitamente as regras toleradas (abreviações comuns e falta de acento) e os limites de reprovação (sobrenomes totalmente diferentes, pessoas distintas).
  - Em caso de divergência grave, o agente retorna `identity_valid: false` com status `"ok"`. A decisão final de recusar ou encaminhar é delegada ao `AgentOrchestrator` e `AgentRisk`.

---

### DT-003 — Separação de Papéis: Confirmação de Renda vs Decisão de Risco

- **Problema:** O agente de documentos deve recusar um solicitante que apresentar comprovante com renda "baixa"?
- **Decisão:** Não. O `AgentDocuments` tem papel puramente técnico e analítico: extrair, confirmar a veracidade do comprovante e registrar o `income_value`. Ele nunca julga se a renda é "suficiente" para o empréstimo solicitado.
- **Razão:** O julgamento da suficiência e capacidade de pagamento depende do valor da parcela, taxa de juros e do modelo estatístico que roda dentro do `AgentRisk`.
- **Consequência:** O `AgentDocuments` reporta `income_confirmed: true` e `income_value: 1200.00` como sucesso, mesmo que esse valor seja insuficiente para o empréstimo solicitado de R$ 40.000.

---

## Perguntas em Aberto

> [!TIP]
> **Como lidar com comprovantes contendo múltiplos meses (ex: extratos bancários de 3 meses)?**
> A ferramenta `verify_income` é responsável por consolidar e retornar a média líquida ou o último mês fechado. O agente apenas repassa o valor numérico obtido da resposta da ferramenta MCP.

---

## Decisões Arquiteturais Referenciadas

| ADR | Título | Aplicação neste agente |
| :--- | :--- | :--- |
| **ADR-001** | Sequência serial vs paralelo | AgentDocuments é a Etapa 2, necessitando rodar após o AgentBureau para garantir a ordem lógica. |
| **ADR-002** | A2A vs chamada direta MCP | O orquestrador aciona o `AgentDocuments` via protocolo A2A, e este aciona o `mcp-documents` localmente. |
