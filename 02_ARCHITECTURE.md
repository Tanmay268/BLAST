# 02 — System Architecture

**Project:** BLAST — Business-Loss Aware Structural Triage
**Status:** Authoritative. Interface changes require an ADR.
**Last updated:** 2026-08-17

---

## 1. Architectural principles

Four rules that govern every decision below. They exist because a research prototype has different failure modes than a product.

1. **Offline batch, not online service.** We process released datasets. No streaming ingestion, no live agents, no Kubernetes operator. Every module is a pure function from files to files. *(This is what makes the project feasible on a laptop — see ADR-003.)*
2. **Every stage checkpoints to disk.** Graph construction is expensive and trace parsing is slow. Each stage writes an artifact the next stage reads. You must be able to re-run ranking a hundred times without re-parsing a single trace.
3. **The business overlay is data, never code.** Hardcoding business weights makes the sensitivity analysis (RQ1 robustness) impossible and makes the artifact unreusable.
4. **Determinism is mandatory.** Seeded RNG everywhere. A paper whose numbers move between runs cannot be defended.

---

## 2. Pipeline overview

```
┌─────────────────────────────────────────────────────────────────┐
│  STAGE 0 — DATA ACQUISITION                       (one-off)     │
│  RCAEval RE2/RE3 → local store, per-fault-case directories       │
│  out: data/raw/<system>/<case_id>/{traces,metrics,meta}          │
└────────────────────────────┬────────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  STAGE 1 — TRACE DISTILLATION                    (expensive)     │
│  Parse traces → journeys → compact per-case summary.             │
│  RAW TRACES ARE DISCARDED AFTER THIS STAGE. ← storage survival   │
│  out: data/interim/<system>/<case_id>/journeys.parquet           │
└────────────────────────────┬────────────────────────────────────┘
                             ▼
        ┌────────────────────┴────────────────────┐
        ▼                                         ▼
┌───────────────────────┐            ┌────────────────────────────┐
│ STAGE 2A              │            │ STAGE 2B                   │
│ GRAPH CONSTRUCTION    │            │ GROUND TRUTH EXTRACTION    │
│ traces → topology     │            │ baseline vs fault window   │
│ + business overlay    │            │ → measured impact vector   │
│ → heterogeneous BDG   │            │ + business valuation       │
│ out: graph/<system>   │            │ out: labels/<system>       │
│      .graphml/.pkl    │            │      ground_truth.parquet  │
└───────────┬───────────┘            └─────────────┬──────────────┘
            │                                      │
            ▼                                      │
┌───────────────────────────────┐                  │
│ STAGE 3 — TRANSMISSION        │◄─────────────────┤ (TRAIN split only)
│ LEARNING                      │                  │
│ estimate p(u,v) per edge      │                  │
│ out: graph/<system>/edge_p    │                  │
└───────────┬───────────────────┘                  │
            ▼                                      │
┌───────────────────────────────┐                  │
│ STAGE 4 — IMPACT ENGINE       │                  │
│ Monte Carlo independent       │                  │
│ cascade → expected loss L(S)  │                  │
│ + propagation paths           │                  │
└───────────┬───────────────────┘                  │
            ▼                                      │
┌───────────────────────────────┐                  │
│ STAGE 5 — RANKER              │                  │
│ greedy submodular ordering    │                  │
│ + explanation generation      │                  │
│ out: results/rankings.parquet │                  │
└───────────┬───────────────────┘                  │
            ▼                                      ▼
┌─────────────────────────────────────────────────────────────────┐
│  STAGE 6 — EVALUATION HARNESS       (TEST split only)            │
│  BLAST + 9 baselines × N scenarios → metrics, stats, figures     │
│  out: results/tables/*.tex, results/figures/*.pdf                │
└────────────────────────────┬────────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  STAGE 7 — DASHBOARD (Streamlit, thin)                           │
│  ranked queue · graph view · propagation path · why-this-first   │
└─────────────────────────────────────────────────────────────────┘
```

**The dashed dependency matters:** Stage 3 consumes ground-truth labels, so it must see **only the training split**. Wiring this wrong creates the data leak flagged as TV-4. Enforce it in code with an explicit split manifest, not by convention.

---

## 3. Module specifications

### M1 — `blast.ingest`
Fetch and verify RCAEval archives; normalise per-case directory layout; emit a manifest with checksums.
**Interface:** `ingest(system: str, variant: str) -> Manifest`
**Owns:** nothing scientific. Keep it dumb.

### M2 — `blast.traces`
The workhorse. Parses distributed traces into journeys.

- **Journey** = one root span plus its full span tree = one end-to-end user request.
- **Journey type** = keyed by entry endpoint (e.g. `POST /checkout`).
- **Outcome** ∈ {`success`, `failed`, `degraded`} — `failed` if any span carries an error status; `degraded` if total duration > baseline p99 for that journey type.

**Interface:** `distill(case_dir) -> JourneySummary`
**Output schema** (`journeys.parquet`, one row per journey type per window):
`case_id, window ∈ {baseline, fault}, journey_type, n_total, n_success, n_failed, n_degraded, p50_ms, p95_ms, p99_ms, services_touched (list), endpoints_touched (list)`

> ⚠️ **This is the stage that will consume your time and disk.** Write it to stream (never load a whole system's traces into memory), process one case at a time, checkpoint after each case, and be resumable after a crash. Budget 2–3 weeks. See the Phase 2 gate.

### M3 — `blast.graph`
Builds the heterogeneous Business Dependency Graph.

- **Topology from traces:** parent→child span relationships aggregated across all baseline journeys → `Service --calls--> Service`, `Service --reads/writes--> Datastore`, `Service --exposes--> Endpoint`. Edge attributes: call count, error rate, latency distribution, sync/async flag.
- **Business layer from overlay YAML:** `Capability` nodes and `Endpoint --realises--> Capability` edges.

**Interface:** `build(system, journeys, overlay) -> BDG`
**Representation:** `networkx.MultiDiGraph` in memory; GraphML + pickle on disk. **Not** PyG/DGL — those are needed only inside the GAT baseline (B8) and importing a graph-DL framework as the core representation buys nothing at 12–64 nodes. (ADR-005)

### M4 — `blast.overlay`
Loads, validates, and versions business overlay specifications. Schema-validated (pydantic). Multiple overlays per system for sensitivity analysis.

```yaml
# business_overlay/online_boutique.yaml
version: 1
system: online-boutique
value_model: revenue_weighted
capabilities:
  - id: complete_purchase
    display: "Complete a Purchase"
    value_per_min: 100.0          # relative units, NOT claimed currency
    realised_by: ["POST /cart/checkout"]
    sla: { availability: 0.999, latency_p99_ms: 2000 }
  - id: browse_catalogue
    display: "Browse Products"
    value_per_min: 20.0
    realised_by: ["GET /", "GET /product/{id}"]
```

> Note `value_per_min` is documented as **relative units**, never as dollars. Claiming currency you did not measure is the fastest way to lose a reviewer.

### M5 — `blast.transmission` ← **novel component, RQ2**
Estimates `p(u,v)` = P(v degraded | u degraded) from the training fault cases.

Three estimators, compared in ablation A7:
1. **MLE with Laplace smoothing** — `(co_degraded + α) / (u_degraded + α + β)`. Simple, interpretable, the default.
2. **Bayesian Beta-Binomial** — proper uncertainty; feeds confidence scores in the output.
3. **Feature-based logistic regression** — predicts `p` from edge features (sync/async, retry config, call ratio, historical error correlation, cache presence). **Generalises to unseen edges** — this is what makes the method deployable on a system with no incident history, and it is worth a paragraph in the paper.

**Interface:** `fit(bdg, train_cases) -> EdgeProbabilities`
**Sparsity is the real problem:** with ~270 cases over ~40 edges, many edges will have near-zero observations. Smoothing and the feature-based fallback are not optional niceties — they are load-bearing.

### M6 — `blast.impact` ← **novel component**
Expected business loss under the independent cascade model.

- Monte Carlo: sample `R` cascade realisations (start `R=1000`, tune for variance), compute expected impaired-capability value.
- **Optimisation:** precompute *reverse reachable sets* (the standard RIS trick from the influence-maximization literature) so that repeated `L(S)` queries during greedy selection are cheap. At 12–64 nodes this is fast regardless, but implementing RIS is what lets you honestly claim scalability.
- Also returns the **top-k most probable propagation paths** from incident to impaired capability — this is the explanation, and it is free.

**Interface:** `expected_loss(bdg, edge_p, incident_set, overlay) -> (loss, paths, confidence)`

### M7 — `blast.rank` ← **novel component, RQ3**
Greedy marginal-gain ordering with the cost-normalised rule from `03_RESEARCH_DESIGN.md` §2.3. Lazy evaluation (CELF) since the objective is submodular — cheap to add, gives a nice constant-factor speedup, and demonstrates you understood the structure.

**Output per incident:** rank, expected loss, marginal loss reduction, impaired capabilities, propagation paths, confidence, natural-language reason.

### M8 — `blast.baselines`
All nine baselines behind one interface so the harness treats them uniformly.
**Interface:** `class Ranker(Protocol): def rank(scenario) -> list[IncidentRanking]`
Uniformity here is what makes the evaluation harness simple and the comparison fair.

### M9 — `blast.eval`
Scenario sampling, metric computation, statistical tests, LaTeX table and figure emission.
**One command must regenerate every number in the paper.** Build this early; it is the thing you will run most.

### M10 — `blast.dashboard`
Streamlit. Deliberately thin (ADR-008). Four views: ranked incident queue; interactive BDG; propagation path for a selected incident; side-by-side BLAST vs baseline ordering. Its job is the viva demo and the paper's screenshot — not production readiness.

---

## 4. Repository layout

```
blast/
├── README.md
├── pyproject.toml              # pinned deps
├── docs/                       # these documents
│   ├── 00_MASTER_PLAN.md
│   ├── 01_DECISION_LOG.md
│   ├── 02_ARCHITECTURE.md
│   ├── 03_RESEARCH_DESIGN.md
│   └── 04_LITERATURE_GAP.md
├── src/blast/
│   ├── ingest.py  traces.py  graph.py  overlay.py
│   ├── transmission.py  impact.py  rank.py
│   ├── baselines/  eval/  dashboard/
├── business_overlay/           # YAML value models (released artifact)
├── config/
│   ├── experiment.yaml         # all hyperparameters, one place
│   └── splits/                 # explicit train/test manifests (TV-4)
├── data/                       # gitignored
│   ├── raw/ interim/ processed/
├── results/                    # tables/, figures/, logs/
├── scripts/                    # run_all.sh, reproduce_paper.sh
├── tests/
├── notebooks/                  # exploration only, never load-bearing
└── paper/                      # LaTeX, bib, figures
```

**Rule:** nothing in `notebooks/` may be required to reproduce a paper number. Notebooks are for looking, `src/` is for claiming.

---

## 5. Technology decisions

| Concern | Choice | Why (short form — full rationale in ADRs) |
|---|---|---|
| Language | Python 3.11+ | Ecosystem; you already know it |
| Graph | `networkx` | 12–64 nodes; readability beats speed here (ADR-005) |
| Trace/data | `polars` + `pyarrow`/Parquet | Streaming, memory-frugal, essential at 16 GB (ADR-004) |
| Numerics | `numpy`, `scipy` | — |
| ML baselines | `scikit-learn`, `lightgbm` | B7 |
| GNN baseline | `torch` (CPU) + `torch-geometric` | B8 only; small graphs train fine on CPU |
| Config | `hydra` or plain YAML + `pydantic` | Sweeps and validation |
| Experiment tracking | MLflow local, or CSV + git | Must survive; avoid cloud lock-in |
| Dashboard | `streamlit` | Fastest path to a demo |
| Testing | `pytest` | — |
| Env | `uv` | Fast, lockfile-based, reproducible |

---

## 6. Resource budget (16 GB RAM, no GPU)

| Stage | Peak RAM | Disk | Time |
|---|---|---|---|
| Trace distillation | < 4 GB (streaming) | raw: **10s of GB, transient** → distilled: < 1 GB | hours per system |
| Graph construction | < 1 GB | < 100 MB | minutes |
| Transmission learning | < 2 GB | < 10 MB | minutes |
| Impact (MC, R=1000) | < 2 GB | — | seconds per scenario |
| Full evaluation sweep | < 4 GB | < 1 GB | hours |
| GAT baseline (CPU) | < 4 GB | — | minutes |

**The binding constraint is disk during Stage 1, not RAM.** Mitigations, in priority order: process one fault case at a time; delete raw traces immediately after distillation; start with Online Boutique only; treat Train Ticket (64 services) as a stretch goal with subsetting. **This is the Phase 2 gate in the master plan** — measure before you commit.

---

## 7. Interface contracts (freeze these early)

```python
@dataclass(frozen=True)
class Incident:
    id: str; timestamp: datetime
    affected_service: str
    fault_type: str          # cpu|mem|disk|socket|delay|loss|code
    technical_severity: float  # 0-1, from upstream detector
    affected_endpoints: list[str]
    error_rate: float; latency_delta_ms: float

@dataclass(frozen=True)
class Scenario:
    id: str; system: str
    incidents: list[Incident]
    ground_truth_order: list[str]     # incident ids, worst first
    ground_truth_losses: dict[str, float]

@dataclass(frozen=True)
class IncidentRanking:
    incident_id: str; rank: int
    expected_loss: float; marginal_loss_reduction: float
    impaired_capabilities: list[str]
    propagation_paths: list[list[str]]
    confidence: float; reason: str
```

Freeze these in week 5. Every module and every baseline speaks only these three types. Changing them later means touching everything.

---

## 8. What this architecture deliberately excludes

Each exclusion has an ADR. Summarised here so the boundary is visible in one place:

- ❌ Live Kubernetes deployment / operator — infeasible on the hardware, and not needed for the research claim
- ❌ Real-time streaming ingestion — offline batch is sufficient and vastly simpler
- ❌ Anomaly detection / root cause localization — explicitly upstream, per your project brief
- ❌ Reinforcement learning for weight tuning — no environment to train against, no reward signal, high risk, low novelty (ADR-006)
- ❌ Graph transformers, community detection, GraphSAGE as *core* method — over-engineering at 12–64 nodes (ADR-005)
- ❌ Log parsing — traces suffice; logs triple storage for no gain (ADR-009)
- ❌ Ten node types and twenty node attributes — cut to four types (ADR-007); the rest are unpopulatable from available data

**Every one of these is documented as future work in the paper.** Excluded ≠ forgotten. A "Limitations and Future Work" section that names them shows deliberate scoping rather than ignorance, and that reads as maturity.
