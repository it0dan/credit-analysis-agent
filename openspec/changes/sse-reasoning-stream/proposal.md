# Proposal — SSE reasoning stream (`credit-analysis-agent`)

## Problema
O portal de cliente do frontend (`credit-analysis-frontend`) utiliza um componente `<ReasoningStream>` para renderizar na tela o progresso passo a passo das fases de análise de crédito realizadas pelos agentes (`bureau`, `risk`, `compliance`, `decision`, etc.). Atualmente, o frontend simula essas etapas via timers artificiais no lado do cliente. 

Isso acarreta os seguintes problemas:
1. **Inconsistência de latência**: A animação não reflete as latências reais do Sensedia AI Gateway e das chamadas aos LLMs do backend.
2. **Falta de visibilidade do Short-circuit**: Se a esteira abortar precocemente por fraude (short-circuit) ou demandar HITL, a timeline simulada não acompanha o estado real com precisão imediata.
3. **Falta de observabilidade**: Dificulta a depuração do comportamento do loop agêntico real em tempo de execução sem acesso direto aos logs brutos do servidor.

## Solução
Implementar uma infraestrutura de Server-Sent Events (SSE) no backend (`credit-analysis-agent`) canalizada por `request_id`, emitindo eventos do ciclo de vida da análise em tempo real diretamente do loop do orquestrador.

## Resultados Esperados
1. O frontend poderá escutar o endpoint `GET /analysis/:id/events` e substituir totalmente a simulação de timers por eventos reais gerados dinamicamente no backend.
2. Suporte a replay gracioso: se a análise já terminou, o cliente que carregar a página de status posteriormente receberá os eventos consolidados a partir do banco de dados (SQLite) de forma instantânea e o stream se encerrará.
3. A observabilidade em tempo real é obtida com zero interferência na lógica pura e determinística dirigida por LLM do orquestrador.
