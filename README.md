# BLAST — Business-Loss Aware Structural Triage

Final-year B.Tech CS research project (VIT Vellore). BLAST ranks **concurrent** microservice
incidents by expected business-capability loss, treating prioritization as a *set-selection*
problem rather than a per-incident scoring problem — because concurrent incidents have
overlapping blast radii, and scoring each independently double-counts the overlap.

Formally: rank incidents by expected business-capability coverage under an independent-cascade
failure-propagation model over a business-dependency graph, with a submodular objective —
greedy ordering admits a (1 − 1/e) approximation guarantee.

**Scope boundary.** BLAST starts *after* incident detection and root-cause localization. It does
no anomaly detection, no RCA, no log parsing — upstream systems hand it incident candidates.

---

## Current status

The full evaluation pipeline is built and run against RCAEval's Online Boutique benchmark
(RE2-OB, 90 fault-injection cases: 5 target services × 6 fault types × 3 repetitions).

**Headline result (Gate 4): MIXED, reported honestly rather than forced into a clean pass.**

- BLAST beats its own independent-scoring ablation on **ranking quality** (NDCG@5: 0.954 vs
  0.916, Cliff's δ=0.277, a genuine small effect) — set-selection measurably improves the
  accuracy of *which incident to fix first*.
- It does **not** show a practically meaningful advantage on **Cumulative Business Loss** — the
  metric that most directly matters for triage — despite reaching statistical significance
  (p<0.001, Cliff's δ=-0.023, deep in "negligible" territory; n=90 scenarios gives the test
  power to detect a trivial effect on its own).
- A follow-up synthetic heterogeneity sweep tested a natural explanation (maybe the real
  benchmark's capability footprints are too structurally homogeneous for set-selection's CBL
  advantage to show up) and **did not confirm it** — a simple independent-scoring baseline
  outperforms greedy set-selection on CBL across the *entire* synthetic heterogeneity range
  tested. The likely reason: CBL under uniform repair cost is closer to a weighted-completion-
  time *scheduling* problem than to the *coverage-maximization* problem the submodular greedy
  provably solves well — these were assumed synonymous and turned out not to be.
- A separate, unrelated finding: propagation across the service graph is essentially absent in
  this benchmark (0/20 tested edges show significant propagation) — faults stay largely
  contained to the target service.

Every non-obvious decision behind these results — including the two that didn't confirm the
working hypothesis — is recorded as an ADR in [`context/01_DECISION_LOG.md`](context/01_DECISION_LOG.md).
Start there for the full reasoning; `README.md` here is the orientation, not the record.

## Read this first

| File | Why |
|---|---|
| [`CLAUDE.md`](CLAUDE.md) | Project instructions, current position, hard rules |
| [`context/07_NEXT_PHASE_PLAN.md`](context/07_NEXT_PHASE_PLAN.md) | The post-pilot diagnosis and the plan that produced the current results |
| [`context/01_DECISION_LOG.md`](context/01_DECISION_LOG.md) | Every accepted decision (20 ADRs), including the honest negative/mixed findings |
| [`context/03_RESEARCH_DESIGN.md`](context/03_RESEARCH_DESIGN.md) | Research questions, formal model, ground-truth methodology, baselines, metrics |
| [`context/02_ARCHITECTURE.md`](context/02_ARCHITECTURE.md) | Module specs, pipeline stages, repo layout rationale |
| [`JOURNEY_TYPING_RULE.md`](JOURNEY_TYPING_RULE.md) | How individual traces are classified into journey types |

---

## Repository layout

```
scripts/
  pipeline/       reproducible pipeline, in dependency order (data -> journeys ->
                  capability model -> ground truth -> evaluation -> heterogeneity sweep)
  exploration/    one-off inspection/download scripts, not part of a dependency chain
business_overlay/ declared business-value YAML (relative units, never currency — ADR-002)
config/splits/    frozen train/test manifest (ADR-012)
results/
  data/           every CSV/JSON artifact the pipeline produces
  tables/         LaTeX tables
  figures/        plots (incl. the heterogeneity-sweep figure)
dashboard/        the Streamlit app (results explorer + interactive ranker)
context/          full research documentation: master plan, decision log, architecture,
                  research design, literature review, session history
data/             gitignored — raw traces, deleted after distillation per ADR-004
```

## Reproducing the pipeline

```bash
pip install -r requirements.txt

# Full pipeline, in order (each stage checkpoints to results/data/):
python scripts/pipeline/run_full_re2ob_pipeline.py       # download -> distill -> delete raw traces
python scripts/pipeline/verify_service_graph.py
python scripts/pipeline/build_train_test_split.py
python scripts/pipeline/build_incident_capability_model.py
python scripts/pipeline/run_probabilistic_blast.py
python scripts/pipeline/build_ground_truth_scenarios.py
python scripts/pipeline/run_evaluation.py                 # Gate 4
python scripts/pipeline/run_heterogeneity_sweep.py
python scripts/pipeline/audit_propagation_prevalence.py
```

All scripts assume the repository root as the working directory.

## Running the dashboard

```bash
streamlit run dashboard/app.py
```

---

## Hard rules (see `CLAUDE.md` for the full list)

- Never fabricate data — a value not derivable from RCAEval or a declared overlay file does
  not go in the graph.
- Never leak train into test — enforced by an explicit split manifest, not convention.
- Business values are relative units, never currency.
- Every non-obvious decision gets an ADR, including negative results.
- Determinism is mandatory — every RNG is seeded.
