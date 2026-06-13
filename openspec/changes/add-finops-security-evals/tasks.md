# Tasks — Evals FinOps + Security

**Data:** 2026-06-13  
**Ordem de execução:** sequencial (cada task depende da anterior)

---

## Checklist

- [x] **T0** — Reconhecimento: inspecionar `_meta` atual, ADRs vigentes, configs de referência  
  _Conclusão: `_meta` já completo. ADR-008 não necessário. Bugs identificados nos YAMLs existentes._

- [ ] **T1** — Criar `evals/thresholds.yaml` com thresholds por cenário e data de validade  
  _Arquivo centraliza os thresholds de custo para evitar magic numbers nos YAMLs._

- [ ] **T2** — Reescrever `evals/finops.yaml` corrigindo bugs e adicionando todos os asserts da spec  
  _Bugs: `tokens_used` → `total_tokens`; variáveis indefinidas; testes faltantes._  
  _Adicionar: F1–F8 conforme tabela em `spec.md`._

- [ ] **T3** — Reescrever `evals/security.yaml` completando todos os asserts da spec  
  _Bugs: arquivo truncado; assertions de aud incorretas._  
  _Adicionar: S1–S6 conforme tabela em `spec.md`._

- [ ] **T4** — Atualizar `run_all_evals.sh` para incluir finops e security, abortar no primeiro erro, imprimir tempo total  
  _Adicionar `evals/finops.yaml` e `evals/security.yaml` ao array `CONFIGS`. Adicionar `set -e` e timer com `date +%s`._

- [ ] **T5** — Smoke test individual: `npx promptfoo eval --config evals/finops.yaml`  
  _Verificar que todos os asserts passam._

- [ ] **T6** — Smoke test individual: `npx promptfoo eval --config evals/security.yaml`  
  _Verificar que todos os asserts passam._

- [ ] **T7** — Suite completa cronometrada: `time ./run_all_evals.sh`  
  _Verificar: < 2 minutos, 100% verde, sem CPF em claro nos logs._

- [ ] **T8** — Verificar que nenhum CPF em claro aparece em `eval-results.json` ou logs  
  _Grep por `\d{3}\.\d{3}\.\d{3}-\d{2}` no output capturado._

---

## Nota sobre ADR-008

**Não necessário.** Inspeção confirmou que `_meta.finops` e `_meta.auth` já estão emitidos pelo orquestrador sem nenhuma mudança contratual. Ver `design.md` para detalhes.
