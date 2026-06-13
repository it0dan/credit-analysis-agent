# Tasks — Evals FinOps + Security

**Data:** 2026-06-13  
**Ordem de execução:** sequencial (cada task depende da anterior)

---

## Checklist

- [x] **T0** — Reconhecimento: inspecionar `_meta` atual, ADRs vigentes, configs de referência  
  _Conclusão: `_meta` já completo. ADR-008 não necessário. Bugs identificados nos YAMLs existentes._

- [x] **T1** — Criar `evals/thresholds.yaml` com thresholds por cenário e data de validade  
  _Arquivo centraliza os thresholds de custo para evitar magic numbers nos YAMLs._

- [x] **T2** — Reescrever `evals/finops.yaml` corrigindo bugs e adicionando todos os asserts da spec  
  _Bugs: `tokens_used` → `total_tokens`; variáveis indefinidas; testes faltantes._  
  _Adicionar: F1–F8 conforme tabela em `spec.md`._  
  _Fix extra: process.env não propaga para JS asserts — thresholds hardcoded._

- [x] **T3** — Reescrever `evals/security.yaml` completando todos os asserts da spec  
  _Bugs: arquivo truncado; assertions de aud incorretas._  
  _Adicionar: S1–S5 (AUDIENCE_MAP não configurado → ADR-007 fallback gracioso)._

- [x] **T4** — Atualizar `run_all_evals.sh` para incluir finops e security, abortar no primeiro erro, imprimir tempo total  
  _Adicionado finops.yaml e security.yaml ao array CONFIGS. Timer com date +%s. Abort-on-error._

- [x] **T5** — Smoke test individual: `npx promptfoo eval --config evals/finops.yaml` — **8/8 ✓**

- [x] **T6** — Smoke test individual: `npx promptfoo eval --config evals/security.yaml` — **5/5 ✓**

- [x] **T7** — Suite completa cronometrada — **63s para os 4 principais (< 2min ✓)**

- [x] **T8** — CPF em claro — **nenhum encontrado em eval-results.json ✓**

---

## Nota sobre ADR-008

**Não necessário.** Inspeção confirmou que `_meta.finops` e `_meta.auth` já estão emitidos pelo orquestrador sem nenhuma mudança contratual. Ver `design.md` para detalhes.
