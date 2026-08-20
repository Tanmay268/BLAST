# CLAUDE.md — BLAST

Instructions for Claude Code working in this repository. Read `context/` before doing anything substantive.

---

## What this project is

**BLAST — Business-Loss Aware Structural Triage for Microservice Incidents.**
Tanmay's final-year B.Tech CS research project (VIT Vellore). Two outputs: a publishable research paper and a working prototype.

**The claim, in one sentence:**
> Incident prioritization is a *set-selection* problem, not a scoring problem — because concurrent incidents have overlapping blast radii, and every existing method double-counts them.

Formally: rank incidents by expected business-capability coverage under an independent-cascade failure-propagation model over a heterogeneous business-dependency graph, with per-edge transmission probabilities **learned from telemetry**. The objective is monotone submodular, so greedy ordering admits a (1−1/e) approximation guarantee.

**Scope boundary — this matters.** BLAST starts *after* incident detection and root-cause localization. It does no anomaly detection, no failure classification, no RCA, no log parsing. Upstream systems are black boxes that hand us incident candidates. Do not let scope drift upstream (ADR-001).

---

## Read these first

| File | Why |
|---|---|
| `context/README.md` | Index and orientation |
| `context/07_NEXT_PHASE_PLAN.md` | **Authoritative for the next ~4 weeks.** Post-pilot diagnosis, corrected task order, gates |
| `context/00_MASTER_PLAN.md` | Phases, gates, risks, current position |
| `context/03_RESEARCH_DESIGN.md` | RQs, formal model, **ground truth methodology**, baselines, metrics, ablations |
| `context/02_ARCHITECTURE.md` | Module specs, interfaces, repo layout, resource budget |
| `context/01_DECISION_LOG.md` | 13 accepted ADRs (+6 pending, listed in 07) — every decision and what was rejected |
| `context/04_LITERATURE_GAP.md` | Related work, the gap, positioning statement |
| `context/05_SESSION_LOG.md` | How the plan was derived; the user's stated constraints |
| `context/source/PROJECT_CONTEXT.pdf` | The original project brief |

**`03_RESEARCH_DESIGN.md` §3 (ground truth) is the most important section in the whole set.** If you are unsure whether something is valid, check it against §3.

---

## Hard rules

These are not preferences. Violating any of them damages the research.

1. **Never fabricate data.** No invented revenue figures, no synthetic node attributes, no placeholder metrics presented as measurements. If a value cannot be populated from RCAEval data or a declared overlay file, it does not go in the graph (ADR-007).
2. **Never leak train into test.** Transmission probabilities are learned from the training split only. `config/splits/` is the manifest and it is frozen before modelling. Enforce with assertions in code, not convention (ADR-012).
3. **Business values are relative units, never currency.** Never write `$` or claim dollars. The overlay declares relative weights (ADR-002).
4. **Every non-obvious decision gets an ADR** appended to `context/01_DECISION_LOG.md`. Use the template at the bottom of that file. Never delete an ADR — supersede it.
5. **Determinism is mandatory.** Seed every RNG. Monte Carlo cascade sampling must be seeded and the seed recorded. Paper numbers must not move between runs.
6. **Raw traces are deleted after distillation.** Disk is the binding constraint. Stream, distill, delete, checkpoint per case (ADR-004).
7. **Nothing in `notebooks/` may be required to reproduce a paper number.** Notebooks are for looking; `src/` is for claiming.
8. **Do not add scope without an ADR.** See "Known temptations" below.

---

## Hardware constraints

Development target is a **laptop: 16 GB RAM, no GPU, no Kubernetes cluster.** Everything is offline batch processing over released datasets — no live cluster, no streaming ingestion, no agents (ADR-003).

Do not propose solutions requiring a cluster, cloud GPUs, or live fault injection. If a task seems to need one, the design is wrong — re-read ADR-002 and ADR-003.

---

## Tech stack

| Concern | Choice |
|---|---|
| Language | Python 3.11+ |
| Env | `uv` (lockfile, reproducible) |
| Graph | `networkx` — **not** PyG/DGL for the core (ADR-005) |
| Data | `polars` + Parquet, streaming (ADR-004) |
| Numerics | `numpy`, `scipy` |
| ML baselines | `scikit-learn`, `lightgbm` |
| GNN **baseline only** | `torch` CPU + `torch-geometric` |
| Config | YAML + `pydantic` |
| Dashboard | `streamlit`, thin (ADR-008) |
| Tests | `pytest` |

---

## Repo layout

```
src/blast/
  ingest.py transmission.py    # M1, M5
  traces.py impact.py          # M2, M6
  graph.py  rank.py            # M3, M7
  overlay.py
  baselines/ eval/ dashboard/  # M8, M9, M10
business_overlay/              # YAML value models (released artifact)
config/experiment.yaml         # all hyperparameters, one place
config/splits/                 # frozen train/test manifests
data/raw|interim|processed/    # gitignored
results/tables|figures|logs/
scripts/run_all.sh reproduce_paper.sh
tests/ notebooks/ paper/
context/                       # these documents
```

---

## Frozen interfaces

Every module and every baseline speaks only these three types. Changing them means touching everything — do not change casually.

```python
@dataclass(frozen=True)
class Incident:
    id: str; timestamp: datetime
    affected_service: str
    fault_type: str            # cpu|mem|disk|socket|delay|loss|code
    technical_severity: float  # 0-1, from upstream detector
    affected_endpoints: list[str]
    error_rate: float; latency_delta_ms: float

@dataclass(frozen=True)
class Scenario:
    id: str; system: str
    incidents: list[Incident]
    ground_truth_order: list[str]        # incident ids, worst first
    ground_truth_losses: dict[str, float]

@dataclass(frozen=True)
class IncidentRanking:
    incident_id: str; rank: int
    expected_loss: float; marginal_loss_reduction: float
    impaired_capabilities: list[str]
    propagation_paths: list[list[str]]
    confidence: float; reason: str

class Ranker(Protocol):
    def rank(self, scenario: Scenario) -> list[IncidentRanking]: ...
```

---

## Current position

**All 13 tasks of `context/07_NEXT_PHASE_PLAN.md`'s ordered task list are DONE (2026-08-20).
Gates 0, 1, 1a, 2a all PASSED. Gate 4 result: MIXED — read the nuance below before citing it.**

Read `context/07_NEXT_PHASE_PLAN.md` for the full history of how this was diagnosed and
planned; it is no longer the forward-looking authority now that its task list is complete —
this section, `context/01_DECISION_LOG.md` (ADR-014 through ADR-019), and the results/ files
listed below are now authoritative for current state. What comes next (paper-writing,
optional RE2-SS/RE2-TT cross-system expansion, the human validation study in
`03_RESEARCH_DESIGN.md` §3.4) has no execution plan yet and needs one before proceeding.

### What the pipeline now does, end to end

1. **Journey-level attribution** (ADR-014/015) — `build_journey_impairment.py` (6-case pilot,
   kept as the historical Gate 1a/2a artifact) and `run_full_re2ob_pipeline.py` (full 90-case
   corpus, resumable, `blast_journey_lib.py` shared between them so they can't drift). Journey
   type keyed on root span's direct-children operation signature, never serviceName — see
   `JOURNEY_TYPING_RULE.md`.
2. **Full RE2-OB corpus downloaded, distilled, raw traces deleted** (ADR-004 discipline): 90/90
   cases processed, 0 hard failures, 1 soft exclusion (`re2ob_checkoutservice_cpu_2`,
   short fault window, already known). `journey_impairment_full.csv`, `excluded_cases.csv`.
   5 target services confirmed by direct HF enumeration (not assumed):
   checkoutservice, currencyservice, emailservice, productcatalogservice,
   recommendationservice — x 6 fault types (cpu/delay/disk/loss/mem/socket) x 3 reps = 90.
   Service graph (`service_graph.csv`, 7 nodes/9 edges) verified against a sample from all 5
   target services (`verify_service_graph.py`) — no new edges found, single-trace graph was
   already complete.
3. **Propagation prevalence audit** (`audit_propagation_prevalence.py`, ADR-018): **0/20
   testable edges show significant + practical propagation** from checkoutservice to any
   direct downstream service, both fault types, rigorously tested (Mann-Whitney + Holm +
   Cliff's-delta floor). Structural propagation is not load-bearing for this contribution.
4. **Train/test split frozen** (ADR-012): `config/splits/split_v1.yaml`, 20 train / 10 test
   (service, fault) combinations, every service and fault type represented in both.
5. **Incident-capability model** (`build_incident_capability_model.py`, ADR-016): `p(c|i)`
   (Beta-smoothed, BLAST's model input) and measured magnitude (ADR-017's ground truth basis)
   kept deliberately separate. **Full-corpus footprint finding:** 0/30 incident types cover
   all 9 capabilities (mean 5.93/9) — but footprints are now driven mostly by which SERVICE is
   targeted (near-identical across all 6 fault types within a service — e.g. currencyservice
   always touches the same 7/9 regardless of fault type), not by fault severity.
6. **Probabilistic weighted objective** (`run_probabilistic_blast.py`, ADR-016): submodularity
   regression check PASSES (0/200 violations). Full-pool greedy-vs-independent ties exactly at
   every K — expected and not meaningful on its own (structural footprint overlap across most
   of the 30 types), the real test is scenario-level (next).
7. **Ground-truth scenarios** (`build_ground_truth_scenarios.py`, ADR-017): 90 scenarios
   (30 each at k=3,5,10), TEST-split only, oracle order computed from measured magnitude,
   never from `F(S)` or a fitted model.
8. **Full evaluation** (`run_evaluation.py`, ADR-019): all 7 baselines (B1 random, B2 severity,
   B3 ITIL, B4 PageRank, B6 personalized PageRank, B7 gradient-boosted regressor — sklearn
   HistGradientBoostingRegressor substituting for unavailable LightGBM, labelled a
   reimplementation — B9 BLAST-independent), NDCG/Kendall's τ/MRR/CBL/AULC, paired Wilcoxon +
   Cliff's delta + Holm-Bonferroni across scenarios.

### Gate 4 result — read ADR-019 in full before citing this anywhere

**BLAST vs B9 (independent scoring, the central RQ3 comparison):**
- **NDCG@5: real win.** BLAST 0.954 vs B9 0.916, p_holm=4.4e-10, Cliff's delta=0.277 ("small",
  clears the practical-significance floor). Set-selection measurably improves ranking accuracy.
- **CBL (the plan's own "metric that actually matters"): statistically significant,
  practically negligible.** BLAST 1098 vs B9 1125, p_holm=0.00088, Cliff's delta=-0.023 (deep
  in "negligible" territory). n=90 gives the test power to detect a trivial effect — this is
  the exact large-N artifact this project's practical-effect floor exists to catch, and an
  early automated verdict missed it before being corrected.

**Separately, and just as important: the severity/ITIL strawman baselines (B2, B3) beat BLAST
on NDCG@5** (0.995, 0.999 vs 0.954). Root cause verified directly: Spearman ρ=0.939 between
GT_loss and raw unweighted technical magnitude — because capability footprints are structurally
service-determined (see #5 above) rather than fault-determined, the business overlay's
weighting has little left to differentiate once technical severity is known.

**Verdict: MIXED, not a clean PASS or the plan's anticipated clean TIE.** Full reasoning,
including why this is coherent with the propagation-prevalence finding and what it implies for
the paper's framing (lead with ranking accuracy, not CBL; report the severity-correlation
finding as a real result about this benchmark's limits) is in **ADR-019** — read it before
writing anything paper-facing about this result.

### Artifacts

`journey_impairment_full.csv`, `journey_signature_catalog_full.csv`, `excluded_cases.csv`,
`incident_capability_probabilities.csv`, `incident_capability_magnitude.csv`,
`case_capability_magnitude.csv`, `incident_type_capability_footprint.csv`,
`ground_truth_scenarios.json`, `evaluation_per_scenario.csv`, `evaluation_aggregate.csv`,
`evaluation_statistics.csv`, `results/tables/evaluation_summary.tex`.
6-case pilot artifacts (`journey_impairment.csv`, `incident_capability_matrix_v2.csv`, etc.)
kept as-is, not overwritten — they document Gate 1a/2a's diagnostic history.

**Not done / no execution plan yet:** the human validation study (`03_RESEARCH_DESIGN.md`
§3.4, needs IRB/participant recruitment — cannot be executed autonomously), cross-system
expansion to RE2-SS/RE2-TT (ADR-019 suggests this could widen the CBL gap and is worth
pursuing next), the synthetic-topology heterogeneity-sweep study ADR-019 recommends, and the
actual paper draft (`03_RESEARCH_DESIGN.md` §10 outline).

**ADRs written this session:** 014-020 — all in `context/01_DECISION_LOG.md`.

### Heterogeneity sweep (2026-08-20) — the pre-committed pivot was tested, and did NOT confirm

Followed up on ADR-019's hypothesis with `run_heterogeneity_sweep.py`: synthetic topologies
sweeping capability-footprint heterogeneity from 0 (identical footprints, matching the real
corpus) to 1 (fully disjoint), 600 paired BLAST-vs-B9 scenario comparisons per level. **Result:
B9 (independent scoring) beats BLAST on CBL at every heterogeneity level tested, including
full heterogeneity — the predicted crossover does not appear.** A follow-up diagnostic ruled
out an objective-formula mismatch as the cause (a greedy variant matched to CBL's own
composition rule performed even worse). Working hypothesis, not yet proven: CBL under uniform
repair cost is a weighted-completion-time scheduling problem, for which standalone-value
sorting (B9) is a strong heuristic — a different problem than the coverage-maximization greedy
provably solves well. **Full diagnosis, and what it means for the paper, in ADR-020 — read it
before making any CBL-related claim.** The submodularity guarantee itself is unaffected; what's
unproven is that maximizing it also minimizes realized CBL. Also caught and discarded before
being reported: NDCG@5 in this synthetic design is tautological by construction (ground truth
was set equal to the model's own input) and must not be cited.

**Net effect on the paper's headline claim:** lead with the ranking-quality result (NDCG@5 on
the REAL evaluation, ADR-019 — a genuine small effect, honestly labelled), not CBL. The CBL /
scheduling-theory question is now a well-posed open problem (`03_RESEARCH_DESIGN.md` §2.2's own
pre-registered fallback: "write the proof... and if it does not hold, say so and fall back to
reporting greedy as a heuristic") rather than an assumed win — worth a paragraph in Discussion,
not a claim in Results.

Update this section as the next phase gets planned.

---

## Gates — do not skip

A gate is a go/no-go with an explicit pivot. See `00_MASTER_PLAN.md` for full criteria.

| Gate | Phase | Passes if |
|---|---|---|
| G0 | 0 | Traces have parent-child structure + error status |
| G1 | 1 | Dataset fits on disk; parse time < ~48 machine-hours |
| **G2** | 2 | ≥80% of faults show measurable journey impairment consistent with annotated root cause |
| G3 | 3 | Graph matches known architecture; learned probabilities vary across edges |
| **G4** | 4 | **Ablation A4 (submodular vs independent) shows real benefit** |
| G5 | 5 | Beats B2/B3/B7 on NDCG@5 significantly, across ≥4 of 5 value models |
| G6 | 6 | Paper draft complete; one command reproduces every number |

**G2 and G4 are the ones that can kill the project.** G4 is deliberately early (week ~14) so a failed central claim leaves time to pivot to the RQ1+RQ2 contribution.

---

## Known temptations — resist these

Tanmay builds complete, polished full-stack systems. That instinct is an asset in engineering and a **liability in research**. Around the time the core works and looks "too simple," the pull toward these will be strong. Each was explicitly rejected:

| Temptation | Rejected by | Why |
|---|---|---|
| GNN/GAT as the core method | ADR-005 | Overfits on 12–64 node graphs with ~270 cases; not novel in 2026. It stays a *baseline*. |
| Reinforcement learning | ADR-006 | No environment, no reward signal, no data |
| Ten node types, 20 attributes | ADR-007 | Unpopulatable from available data — would require fabrication |
| React/FastAPI dashboard | ADR-008 | Weeks of work, zero research value. Streamlit, 4 views, built last |
| Log parsing | ADR-009 | Triples storage, no benefit; traces suffice |
| Building an anomaly detector or RCA module | ADR-001 | Saturated field; explicitly out of scope |
| Live Kubernetes + Chaos Mesh | ADR-003 | Hardware can't support it; weeks of yak-shaving, zero research output |

**Simple and rigorously validated is what publishes.** If you want to add something, write the ADR first — the act of justifying it usually kills it.

---

## Working style

- Be a research collaborator, not just a coding assistant. Challenge assumptions.
- If an idea is already solved in the literature, say so directly and propose something stronger.
- Prioritize publishable contributions over engineering complexity.
- When proposing an architecture or algorithm, state why it is novel, how it differs from prior work, and what experiment would validate it.
- Mark uncertain citations `[VERIFY]`. Never let an unverified citation into the paper.
- Negative results are acceptable and must be reported honestly — but always with a diagnosis of *why*.
