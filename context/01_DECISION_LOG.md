# 01 — Decision Log (Architecture Decision Records)

**Project:** BLAST — Business-Loss Aware Structural Triage
**Convention:** Every non-obvious decision gets an ADR. Never delete one — supersede it. When you write the paper, this file *is* your methodology justification.

**Status values:** `Accepted` · `Superseded by ADR-nnn` · `Proposed` · `Deprecated`

---

## ADR-001 — Scope the contribution to prioritization, downstream of detection and diagnosis

**Status:** Accepted · 2026-08-17

**Context.** Microservice AIOps research is saturated in anomaly detection and root-cause localization. Marginal improvements there are near-unpublishable at reputable venues.

**Decision.** BLAST consumes incident candidates as input. It performs no detection, no classification, no root-cause localization. Upstream systems are treated as black boxes.

**Rationale.** The under-served question is genuinely *"which incident first?"*. Restricting scope makes the contribution legible and the project finishable.

**Alternatives rejected.**
- *End-to-end system (detect → diagnose → prioritize)*: dilutes novelty across saturated areas; triples the work; reviewers evaluate you against specialists in each area and you lose every comparison.
- *Improve root-cause localization*: crowded; requires beating strong recent baselines with a laptop.

**Consequences.** You must be explicit that incident *quality* is an input assumption. Add a robustness experiment: inject noise into incident inputs (false positives, wrong service attribution) and show ranking degrades gracefully. Reviewers ask "what if the detector is wrong?" — have the answer ready.

**Revisit if:** a reviewer demands end-to-end evaluation. Response is the noise-robustness experiment, not scope expansion.

---

## ADR-002 — Ground truth from measured trace-derived journey impairment, plus a declared business overlay

**Status:** Accepted · 2026-08-17 · **Highest-stakes decision in the project**

**Context.** All ranking metrics require ground-truth priority labels. No public dataset has them. Real revenue data is unobtainable.

**Decision.** Two-layer ground truth:
1. **Measured layer** — extract, from RCAEval's released traces, how many end-to-end user journeys failed or degraded during each real injected fault vs. the fault-free baseline. This is *measurement of a real experiment*, computed offline.
2. **Valuation layer** — a declared, versioned, YAML business overlay maps journey types to relative business value. Validated by sensitivity analysis across ≥5 value models and by a human study.

**Rationale.** Cleanly separates *what was observed* (defensible, objective) from *what was assumed* (declared, tested for robustness). A reviewer can attack the valuation, and the sensitivity analysis is the pre-built answer. Critically, it requires no cluster — the experiment was already run by RCAEval's authors.

**Alternatives rejected.**
- *Live fault injection with revenue instrumentation*: the ideal, but requires a Kubernetes cluster you do not have. Also: RCAEval's data is already peer-reviewed and reusing it strengthens comparability.
- *Pure synthetic labels from a scoring formula*: circular — the model would learn to reproduce your own formula. Reviewers detect this instantly.
- *Expert annotation as sole ground truth*: doesn't scale past ~50 incidents; subjective; inter-annotator agreement becomes an attack surface.

**Consequences.** Trace parsing becomes the project's critical path and biggest engineering risk (Phase 2). The business overlay must be released as an artifact. Threats TV-1, TV-2, TV-3 must be written honestly.

**Revisit if:** trace data proves unusable for journey reconstruction (Phase 2 gate fails) — fallback is metric-based impairment proxies, which is weaker and must be flagged.

---

## ADR-003 — Offline batch processing over released datasets; no live cluster

**Status:** Accepted · 2026-08-17

**Context.** Hardware is a single laptop, 16 GB RAM, no GPU, no Kubernetes.

**Decision.** Every module is a pure file→file function. No streaming, no agents, no operator, no live deployment.

**Rationale.** Matches the hardware. Makes runs deterministic and reproducible. Reviewers care about the algorithm's validity, not whether it ran in a live cluster — and offline batch is *more* reproducible.

**Alternatives rejected.**
- *Local kind/minikube cluster with Chaos Mesh*: Online Boutique plus observability stack plus chaos tooling on 16 GB is fragile at best; weeks lost to infrastructure yak-shaving that produce zero research output.
- *Cloud cluster*: cost, and no credits confirmed.

**Consequences.** Cannot claim live production validation. State this in External Validity (TV-6/TV-7). If cloud credits appear later, a small live validation on 3–5 incidents becomes a strong optional addition.

---

## ADR-004 — Polars + Parquet for data, streaming trace processing, raw traces discarded after distillation

**Status:** Accepted · 2026-08-17

**Context.** RCAEval reports 4.5–76.7M traces per system. Pandas would exhaust 16 GB; raw storage may exceed available disk.

**Decision.** Stream traces with Polars; process exactly one fault case at a time; write a compact journey summary; **delete raw traces for that case immediately.** Checkpoint per case; make the pipeline crash-resumable.

**Rationale.** Disk, not RAM, is the binding constraint. Distilled summaries are ~1000× smaller than raw traces and are all downstream stages need.

**Alternatives rejected.**
- *Pandas + keep everything*: will fail, probably at 2am the week before a deadline.
- *A local database (Postgres/ClickHouse)*: operational overhead unjustified for a single-user batch pipeline.

**Consequences.** Re-deriving a discarded quantity means re-downloading. **Therefore: decide the journey summary schema carefully before mass processing, and over-collect fields rather than under-collect.** Getting this wrong costs days.

---

## ADR-005 — networkx as the core graph representation; graph deep learning only as a baseline

**Status:** Accepted · 2026-08-17

**Context.** The project brief proposes GNNs, GATs, GraphSAGE, and graph transformers as candidate contributions.

**Decision.** Core method uses networkx and explicit probabilistic propagation. PyTorch Geometric appears **only** in baseline B8 (a GAT regressor).

**Rationale — and this contradicts the project brief, deliberately.** Graphs here have 12–64 service nodes. A GNN on a 12-node graph with ~270 training cases will overfit, and "we applied a GAT to a graph" is not a 2026 contribution — it is a 2019 one. The defensible novelty is the *problem formulation* (submodular business-capability coverage) and the *learned transmission model*, both of which are interpretable and give explanations for free. Including a GAT as a **baseline** is strictly better than as the method: if BLAST beats it, that is a *result* — structure-aware probabilistic reasoning beating a black box on small-data graphs is exactly the kind of finding reviewers enjoy.

**Alternatives rejected.**
- *GAT as the core method*: high overfitting risk, no interpretability (undermining RQ4), and not novel.
- *Graph transformer*: severe over-engineering at this scale.

**Consequences.** Expect pushback from anyone who equates "deep learning" with "research contribution." The counter-argument is the ablation table: if the GAT baseline underperforms, you have empirical justification, and that is a stronger position than having used one.

**Revisit if:** you obtain a system with 500+ nodes and thousands of incidents. Then GNN capacity starts to pay for itself.

---

## ADR-006 — No reinforcement learning

**Status:** Accepted · 2026-08-17

**Context.** The brief lists RL among possible optimization techniques.

**Decision.** Excluded entirely.

**Rationale.** RL needs an environment and a reward signal. You have neither — there is no simulator of engineer behaviour and no reward from real repair outcomes. RL over an offline dataset of 270 cases would be uninterpretable, unstable, and unevaluable. High risk, low payoff, large time cost.

**Alternatives rejected.** *Offline RL / bandits for weight tuning*: same data-scarcity problem, plus it undermines the interpretability that RQ4 depends on.

**Consequences.** Listed as future work: "given a deployment producing repair outcomes, the weighting could be learned online via bandit feedback."

---

## ADR-007 — Four node types, not ten; four edge types, not eight

**Status:** Accepted · 2026-08-17

**Context.** The brief proposes ten node types (services, APIs, DBs, queues, caches, deployments, capabilities, features, teams, infra) and ~20 node attributes.

**Decision.** Node types: `Service`, `Endpoint`, `Datastore`, `Capability`. Edge types: `calls`, `reads/writes`, `exposes`, `realises`.

**Rationale.** **You can only include what you can populate from data.** RCAEval traces yield services, endpoints, datastores and call structure. Teams, deployment frequency, MTTR, recovery cost, revenue contribution and historical incident counts are *not present* — including them would mean inventing values, which is fabrication dressed as modelling. Four types are enough to express the core claim: failure propagates through services to the capabilities users care about.

**Alternatives rejected.**
- *Full ten-type schema with synthetic attributes*: unpopulatable; every synthetic attribute is an attack surface; complexity without information.
- *Homogeneous service graph only*: loses the business layer, which is the entire point.

**Consequences.** Ablation A5 tests whether heterogeneity earns its keep. Additional types are future work, contingent on richer data sources (CMDB, org charts, deployment logs).

---

## ADR-008 — Thin dashboard, built late

**Status:** Accepted · 2026-08-17

**Context.** The brief lists a dashboard as a deliverable; it is also needed for the viva demo.

**Decision.** Streamlit, ~4 views, built in the final phase, deliberately minimal.

**Rationale.** The dashboard contributes zero research novelty and is a notorious time sink. Its purposes are (a) one paper figure, (b) the demo. Both are satisfied by a thin implementation. Building it early risks the classic failure of a beautiful UI over an unvalidated algorithm.

**Alternatives rejected.** *Full React/FastAPI application*: weeks of work for no research value. Your existing full-stack skills make this tempting — resist it. Impressive engineering does not compensate for a weak evaluation.

**Consequences.** Do not let it slip earlier in the schedule. If time runs short, the dashboard is the **first** thing cut, before any evaluation work.

---

## ADR-009 — Traces only; logs excluded

**Status:** Accepted · 2026-08-17

**Context.** RCAEval releases metrics, logs, and traces (1.7–26.9M log lines per system).

**Decision.** Use traces for topology and journeys; metrics for incident severity features; **ignore logs entirely.**

**Rationale.** Logs would triple storage on a disk-constrained machine and serve no purpose in the current design — journey reconstruction and dependency topology both come from traces. Log parsing is also explicitly disclaimed as a contribution in your brief.

**Consequences.** Cannot use log-based features in baseline B7 (AlertRank uses textual alert features). Note this when describing the reimplementation — B7 is "in the spirit of," using available features.

---

## ADR-010 — Four research questions; RQ on response-time reduction dropped

**Status:** Accepted · 2026-08-17

**Context.** The brief lists five RQs, including "can graph learning reduce incident response time?"

**Decision.** Four RQs (see `03_RESEARCH_DESIGN.md` §1). Response-time reduction is replaced by the Cumulative Business Loss simulation metric, explicitly labelled a proxy.

**Rationale.** Response-time reduction requires a longitudinal study in a real organisation with a control group. Claiming it from simulation is overclaiming, and it is the kind of overclaim that draws a harsh review. The CBL proxy is honest and still compelling.

**Consequences.** Every mention of CBL in the paper must carry the proxy caveat. Real deployment is future work.

---

## ADR-011 — Submodular set-selection as the headline formulation

**Status:** Accepted · 2026-08-17 · **This is the paper's core claim**

**Context.** Needed one sharp, defensible novelty rather than several diffuse ones.

**Decision.** Frame prioritization as *ordering under a repair budget to minimise expected cumulative business loss*, where the loss function is expected capability coverage under an independent-cascade propagation model — hence monotone submodular, hence greedy admits an approximation guarantee.

**Rationale.** Three properties make this strong:
1. **It is genuinely unaddressed.** Search found no AIOps work framing prioritization as set selection. Every existing method scores incidents independently and therefore double-counts overlapping blast radii.
2. **It borrows mature theory** (Kempe–Kleinberg–Tardos KDD 2003; Nemhauser et al. 1978), so the mathematics is solid and citable rather than invented.
3. **It yields a theorem**, which materially raises a paper above "engineering report."

**Alternatives rejected.**
- *Weighted-sum priority score with learned weights*: this is what the brief originally proposed. It is essentially AlertRank plus graph features — an incremental delta, hard to publish.
- *Pure learning-to-rank*: needs far more labelled data than exists, and forfeits interpretability.

**Consequences — read this carefully.** The approximation guarantee applies cleanly to influence maximization; **your objective is an ordering/scheduling problem and is not literally the same.** You must derive the result for your objective. If it does not hold, report greedy as a well-motivated heuristic and lean on the empirical ablation (A4) instead. **Do not claim an unproven theorem.** Schedule the proof for Phase 5 and treat failure to prove it as a known, survivable outcome.

**Revisit if:** the proof fails *and* ablation A4 shows no empirical benefit from set-level selection. In that case the contribution reduces to the learned-transmission graph model (still publishable, at a lower tier) — and you will know this by end of Phase 4, with time to adapt.

---

## ADR-012 — Strict train/test split by fault case, defined before modelling

**Status:** Accepted · 2026-08-17

**Context.** Transmission probabilities are learned from fault cases; ground truth is derived from the same corpus.

**Decision.** An explicit split manifest in `config/splits/`, stratified by service and fault type, created and frozen **before** any modelling. Stage 3 reads only training cases; Stage 6 evaluates only on test cases. Enforced in code with an assertion, not by convention.

**Rationale.** Learning `p(u,v)` from a fault whose impact you then predict is a textbook leak. It is also easy to do accidentally and invisible in results — it just makes everything look great. Reviewers hunt for exactly this.

**Consequences.** Fewer training cases per edge, worsening the sparsity problem in M5. This is the correct trade: honest and weaker beats inflated and wrong.

---

## ADR-013 — Working name "BLAST"

**Status:** Proposed · 2026-08-17

**Decision.** **B**usiness-**L**oss **A**ware **S**tructural **T**riage. Placeholder.

**Rationale.** Memorable; the blast-radius connotation fits. Check for name collisions in software/security (BLAST is a well-known bioinformatics tool — this may be reason enough to rename before submission).

**Revisit:** before paper submission. Low stakes, easy to change; do not spend time on it now.

---

## ADR-014 — Journey/operation-level impairment attribution supersedes service-level

**Status:** Accepted · 2026-08-20

**Context.** The 6-case pilot's binary-coverage greedy BLAST tied its independent baseline at every K (Gate 4, null result). `diagnose_saturation.py` (Gate 1a, CONFIRMED) traced this to service-level capability attribution: `build_business_capabilities.py` maps an operation to a capability, then attributes that mapping via the CALLER's `serviceName`. In 5 of 6 pilot cases the fault target (`checkoutservice`) is also the caller for most of the checkout flow's downstream RPCs, so being flagged impaired (correctly — it's the fault target) pulled in capability mappings for calls it merely issues, not calls that were actually affected. Mean single-service dominance across the pilot was 94.2% of each incident's capability union.

**Decision.** Attribution moves from service-level latency impairment to journey-level outcome measurement, as ADR-002 originally specified. A journey (one trace, keyed on its root span) is classified `failed` / `degraded` / `success` per instance, and impairment is a property of the journey type — computed via Mann-Whitney U on duration distributions plus a two-proportion test on failure rate, Holm-corrected across journey types within a case. Implemented in `build_journey_impairment.py`. `build_business_capabilities.py` / `build_capability_impacts.py` (service-level) are superseded, not deleted.

**Rationale.** A journey is an end-to-end request; classifying its outcome directly tells us which business capability was affected, with no service→capability guessing step in between. Verified empirically: checkout faults now impair only the `Place Order` journey and the orphaned currency-conversion journey (see ADR-015), while `Home Page View`, `Cart View`, and `Add To Cart` are correctly left unimpaired across all 6 pilot cases — the differentiation the service-level rule could never produce.

**Alternatives rejected.**
- *Patch the service-level rule to exclude self-mappings*: doesn't fix the general case — any service that both serves and calls downstream operations still amplifies, it just moves which service does the amplifying (confirmed: `frontendservice` was the dominant service in 1/6 cases even under the current rule).
- *Finer capability model instead of attribution rework*: ruled out by Gate 1a itself — the diagnostic showed single-service dominance (an attribution failure mode), not diffuse near-total coverage from genuinely differing per-service sets (which would have implicated capability coarseness instead).

**Consequences.** Requires re-downloading raw `traces.parquet` per case (deleted after the pilot's distillation per ADR-004) to reconstruct per-trace journey structure; the 30-second-window service-level distillation (`impairment_dataset_30s.csv`) did not preserve `traceID`. The business overlay must be rebuilt as operation→capability (`business_overlay/online_boutique_v2.yaml`), superseding `business_capabilities.csv`.

**Revisit if:** Gate 2a (re-run pilot, do capability footprints now differ with no incident at 9/9?) fails after this fix — would indicate a deeper problem, likely that the capability model itself is too coarse relative to journey count.

---

## ADR-015 — Journey-typing rule: keyed on root direct-children operation signature, with orphan-root handling

**Status:** Accepted · 2026-08-20

**Context.** ADR-014 requires classifying each trace into a journey type. Online Boutique's `frontendservice` wraps 77% of root spans (19,119 / 24,810 in the pilot) in one generic root operation literally named `"frontend"` — keying journey type on root `operationName` directly would collapse nearly all journeys into one type, reproducing the saturation bug in a new form. `07_NEXT_PHASE_PLAN.md` anticipated this and proposed falling back to "the deepest distinguishing operation in the trace."

**Decision.** For `"frontend"`-rooted traces, journey type is keyed on the sorted, deduplicated set of `methodName` values among the root span's **direct children** (not a single "deepest" operation). For non-generic roots — specifically ~2,400 orphaned traces per case where `checkoutservice` issues `hipstershop.CurrencyService/Convert` as its own root span with no parent context (a broken trace-context-propagation artifact in the checkout flow) — journey type is the root's own operation, kept as a distinct type rather than merged into `Place Order`. Health-check and telemetry-export roots are dropped as infrastructure noise (verified: always single-span traces).

**Rationale.** Inspection of actual `"frontend"`-rooted traces showed the plan's proposed fallback doesn't apply: the frontend issues a fan-out of parallel backend calls per page (e.g. the home page calls `ListProducts` + `GetAds` + `GetCart` + `Convert` as siblings, not a chain), so there is no single deepest child to pick. The direct-children signature recovers exactly 5 real, stable Online Boutique request types (Product Detail View, Cart View, Add To Cart, Home Page View, Place Order — verified stable across a `delay` case and a `cpu` case), which is what "deepest distinguishing operation" was trying to achieve for a linear-chain assumption that doesn't hold for this application.

**Alternatives rejected.**
- *Merge the orphaned `Convert` traces into `Place Order`*: would assume, without verification, that every orphaned currency-conversion call belongs to a checkout request specifically (vs. e.g. a cart-page currency preview). Kept separate to avoid an unverified merge; it happens to correlate strongly with `Place Order` impairment in the results anyway, which is observable without assuming it.
- *Single "deepest operation" per the plan's literal wording*: does not exist for fan-out traces; would require an arbitrary tie-break rule with no principled justification.

**Consequences.** A composite page journey (e.g. Product Detail View touches `GetProduct`, `ListRecommendations`, `GetAds`, `GetCart`, `Convert`) genuinely realizes multiple capabilities in one request — this reflects real system composition, not an attribution error, but means an impaired composite journey still can't localize which single constituent call degraded. Documented as a threat-to-validity in `JOURNEY_TYPING_RULE.md` (see the `cpu_3` Product Detail View borderline case, Cliff's delta 0.152, likely a large-N statistical-significance artifact rather than a real effect).

**Revisit if:** cross-system expansion (RE2-SS, RE2-TT) introduces an application whose frontend does not use a generic root-wrapper pattern — the direct-children-signature rule may be unnecessary there (root operationName may already be distinguishing), and the rule should degrade gracefully rather than being force-applied.

---

## ADR-018 — Propagation prevalence finding: 0% in the 6-case pilot; structural propagation is not the primary contribution

**Status:** Accepted · 2026-08-20 · **Recorded per `07_NEXT_PHASE_PLAN.md` §1.2's explicit instruction: record the answer regardless of what it is, decide on evidence now rather than in week 20.**

**Context.** RQ2 asks whether *learned* edge transmission probabilities beat topological importance — this only matters if faults actually propagate across service-graph edges. `07_NEXT_PHASE_PLAN.md` §1.2 flagged early pilot numbers (crude ratio-threshold detector, no significance testing) showing 3 of 4 downstream edges at 0% propagation. Step 3.5 mandated a proper audit before this got discovered late.

**Decision/Finding.** `audit_propagation_prevalence.py` tested all 4 downstream edges from `checkoutservice` (→ `currencyservice`, `emailservice`, `paymentservice`, `productcatalogservice`) across all 6 pilot cases (both `cpu` and `delay` fault types), using the same rigor as journey-level testing: Mann-Whitney U on span duration + two-proportion test on error rate, Holm-corrected per case, gated on a Cliff's-delta practical-effect floor (0.147). **Result: 0/20 testable edges show significant + practical downstream propagation (0.0% prevalence), for both fault types, at the only graph distance tested (1-hop, direct edges).** Several edges had extremely small p-values (down to 1e-58) that were correctly screened out by the practical-effect gate — a textbook large-N statistical-significance artifact, not evidence of propagation.

**Rationale for why this is real, not a detector bug.** It is consistent with the journey-level finding (ADR-014): only `Place Order` and the orphaned `Currency Conversion` journey — both on `checkoutservice`'s own execution path — showed impairment; `Home Page View`, `Cart View`, `Add To Cart` did not. A CPU/delay fault injected directly into `checkoutservice` slows `checkoutservice`'s own processing around its outbound calls, but does not make the callees (`currencyservice`, `paymentservice`, etc.) themselves measurably slower — physically sensible for resource-contention and injected-delay fault types, which act on the target process, not on what it calls.

**Consequences.** Per the plan's pre-committed decision rule: *"Low prevalence → the contribution rests on the business-capability set-selection half; multi-hop propagation gets demoted to a secondary component."* The paper's framing should lead with RQ3 (submodular set-selection under overlapping blast radii) rather than RQ2 (learned transmission beating topology). RQ2 should still be reported, but honestly, as a negative/mixed finding with characterisation: *"in RCAEval's injected-fault benchmark, faults are substantially more self-contained than propagation-based RCA methods assume"* — citable alongside the fault-propagation-aware benchmark critique (arXiv 2510.04711) and the oversimplified-benchmarks empirical study already noted in `07_NEXT_PHASE_PLAN.md`.

**Threat to validity, explicit:** this finding currently rests on a single source service (`checkoutservice`, the only pilot fault target) and a single graph distance (1-hop — the service graph has no 2-hop paths from `checkoutservice`). It must be re-run via the same script (already source-agnostic, auto-discovers cases) once the RE2-OB expansion (Step 4/7, ADR-019) provides other target services, before being treated as a corpus-wide finding rather than a pilot-scale one.

**Revisit if:** the RE2-OB-scale re-run (after Step 7) shows materially different prevalence for other target services or fault types (e.g. `mem`, `disk`, `socket`, `loss`) — update this ADR's finding rather than superseding it, since the audit script itself does not change.

---

## ADR-016 — Probabilistic weighted objective; what "learned from train only" does and does not cover

**Status:** Accepted · 2026-08-20

**Context.** `07_NEXT_PHASE_PLAN.md` Step 5a replaces BLAST's binary coverage objective with `F(S) = Σ_c w_c · P(c impaired | S)`, `P(c impaired|S) = 1 − Π_{i∈S}(1 − p(c|i))` under independent activation, with `p(c|i)` from a Beta posterior across an incident type's repetitions. Hard rule #2 requires transmission probabilities to be learned from the training split only, enforced in code. It is not obvious, on first read, whether `p(c|i)` is the kind of "learned, must-not-leak" quantity that rule targets.

**Decision.** `p(c|i)` (and the parallel continuous `measured_impairment_magnitude(c|i)` used for ground truth) is estimated from incident type `i`'s **own** repetitions only, via `build_incident_capability_model.py`, and is computed for **every** incident type — train and test alike. This is direct measurement of a specific, already-observed incident type, not a model fit on some incident types and generalised to predict unseen ones. It is the same category of quantity as ground truth `GT_loss(i)` (ADR-002/07_NEXT_PHASE_PLAN.md §3.2), which is likewise computed per-incident from its own traces and explicitly must never come from a fitted model.

The train/test split (`config/splits/split_v1.yaml`, ADR-012) governs two different things instead:
1. **B7's classifier** (AlertRank-style, gradient-boosted over incident features) is fit on TRAIN incident types and evaluated on TEST — this is the one place in the pipeline where a model actually generalises across incident types, and where leakage is a live risk.
2. **Evaluation scenarios** (Step 10 synthesis, Step 12 harness) are composed exclusively from TEST-split incident types, so that whatever the pipeline *did* fit on train (B7, and the near-degenerate edge-transmission-probability table per ADR-018) is judged on genuinely held-out incidents.

**Rationale.** Conflating "any quantity computed with an empirical rate" with "must be train-only" would be over-application of the rule to the point of absurdity — it would forbid computing an incident's own measured ground truth from its own data, which is the entire premise of ADR-002's ground-truth methodology. The leakage risk the rule (and TV-4) actually targets is specific: fitting a predictive mapping from features to outcome on some incidents, then evaluating that same fit on those incidents.

**Consequences.** Submodularity is preserved under this formulation: weighted probabilistic coverage under independent activation is the standard KKT setting, and the existing empirical marginal-gain regression check (0 violations on the pilot) must continue to pass under the probabilistic `F(S)` — implemented as a regression test in `run_probabilistic_blast.py`, not a one-off.

**Revisit if:** the project later reintroduces genuinely learned edge-transmission probabilities `p(u,v)` at meaningful non-zero prevalence (ADR-018 currently found ~0%) — those, unlike `p(c|i)`, are exactly the KKT-style quantity hard rule #2 was written for, and must be fit on TRAIN only with an enforced assertion, per the original design.

---

## ADR-017 — Evaluation ground truth derived independently of F(S); coverage@K demoted to sanity check

**Status:** Accepted · 2026-08-20

**Context.** `07_NEXT_PHASE_PLAN.md` §1.3 flagged that evaluating BLAST against its own `F(S)` objective (as `blast_vs_baseline.csv` did in the pilot) is close to tautological — greedy is provably ≥ independent on the function it explicitly maximizes, so a "win" proves nothing and a "tie" only shows the objective is degenerate.

**Decision.** `build_ground_truth_scenarios.py` computes `GT_loss(i)` and the oracle sequential-repair order from **measured** `case_capability_magnitude.csv` (continuous journey-impairment magnitude, ADR-014) — never from `p(c|i)` or `F(S)`. The oracle order is a plain greedy union/max-coverage rule over these measured values (model-free, defensible as an oracle per `07_NEXT_PHASE_PLAN.md` §5b). `run_evaluation.py`'s headline metrics (NDCG@5, CBL/AULC) are graded against this independent ground truth; `run_probabilistic_blast.py`'s binary/probabilistic coverage@K checks are retained only as machinery regression tests (submodularity holds, 0 violations), never reported as an evaluation result.

**Rationale.** This is the only way a BLAST-vs-baseline comparison is falsifiable. It also makes B2 (severity) and B7 (classifier) legitimate competitors rather than strawmen defined in terms of BLAST's own objective.

**Consequences.** See ADR-019 for what this evaluation actually found once run.

---

## ADR-019 — Gate 4 result: MIXED. Real ranking advantage, negligible business-loss advantage — and why

**Status:** Accepted · 2026-08-20 · **The Gate 4 decision, recorded per `07_NEXT_PHASE_PLAN.md`'s requirement to decide on evidence, not vibes.**

**Context.** `run_evaluation.py` ran the full pipeline: 90 test-split-only scenarios (30 each at k=3,5,10, drawn from the 10 test incident types × 3 reps, ADR-016), all 7 baselines (B1/B2/B3/B4/B6/B7/B9), BLAST scored via its own model (`p(c|i)`, never ground truth), graded against ADR-017's independent ground truth, Holm-corrected paired Wilcoxon + Cliff's delta across scenarios.

**Finding 1 — BLAST vs B9 (the central RQ3 comparison, isolating set-selection).** Both metrics reach very small Holm-corrected p-values (n=90 gives real power), but they diverge on practical effect size:
- **NDCG@5:** BLAST 0.954 vs B9 0.916, Cliff's delta = **0.277** ("small" effect, clears the 0.147 floor). A real, if modest, ranking-quality advantage from set-selection.
- **CBL:** BLAST 1098 vs B9 1125, Cliff's delta = **-0.023** (deep in "negligible" territory, well below 0.147) despite p_holm = 0.00088. This is exactly the large-N statistical-significance-without-practical-significance artifact this project's own methodology (Cliff's-delta floor, used throughout — ADR-014/018) was built to catch, and it would have been inconsistent not to apply that same floor here. **Initial automated verdict logic missed this** (checked only p<0.05, no effect-size gate on the pass path) and was corrected before reporting.

**Verdict: neither a clean PASS nor the plan's anticipated clean TIE.** BLAST measurably orders incidents more accurately, but this does not translate into a practically meaningful reduction in simulated cumulative business loss on this benchmark, at these scenario sizes.

**Finding 2 — the straw-man baselines (B2 severity, B3 ITIL) beat BLAST on NDCG@5** (B2: 0.995, B3: 0.999, both significantly above BLAST's 0.954). Root cause, verified directly: **Spearman ρ = 0.939** between `GT_loss` (the business-weighted ground truth) and raw unweighted technical impairment magnitude (B2's entire signal) across all 90 usable cases. This is not a baseline-implementation bug — it is a direct consequence of `build_incident_capability_model.py`'s own footprint finding: **capability *sets* touched by an incident type are structurally determined by which journeys route through the target service** (near-identical within a service across all 6 fault types — e.g. `currencyservice` always touches the same 7/9 capabilities regardless of fault type), so **the business overlay's weighting has little left to differentiate once the technical severity is known.** Magnitude alone is nearly sufficient to reconstruct the weighted ground truth on this benchmark.

**Why this is coherent with the rest of the session's findings, not an isolated anomaly:**
- ADR-018 (propagation prevalence ≈ 0%): faults don't spread across services.
- This ADR: within a service, faults of different types touch nearly the same capability set, differing mainly in severity.
- Together: RCAEval's Online Boutique injected faults vary **how badly** a fixed, service-determined footprint is hit, far more than **what** gets hit. That is a property of this benchmark's fault model (resource/network faults injected into one service at a time), not of BLAST's method.

**Consequences for the paper's framing.** The central contribution should lead with the ranking-quality result (RQ1/RQ3 via NDCG@5, a real small effect, honestly labelled as such) rather than a CBL headline win, which the data does not support. The severity-baseline finding is itself a genuine, citable contribution about this benchmark's limits: *"technical severity alone reconstructs 88% of the variance in business-weighted ground truth on RCAEval's Online Boutique injected-fault benchmark, because fault type varies impact magnitude far more than impact footprint within a target service."* This is the same family of finding as ADR-018 (fault-propagation-aware benchmark critique, arXiv 2510.04711) and should be written up alongside it, not separately.

**This is not the plan's pre-committed pivot (§4)** — that pivot assumes a clean tie on the coverage objective. The actual result is more specific and more interesting: submodular set-selection *does* measurably improve ranking accuracy; it does not (on this benchmark) translate that into materially less simulated business loss, and the reason is traceable to a specific, falsifiable property of the fault-injection benchmark (footprint homogeneity within a target service) rather than a flaw in the method. Recommend reframing the paper's RQ3 claim from "beats independent scoring on CBL" to "beats independent scoring on ranking accuracy; CBL advantage is conditional on footprint heterogeneity, characterised here and predicted to be larger on benchmarks/systems with more diverse per-service capability footprints" — pairing naturally with a synthetic-topology heterogeneity-sweep study (already suggested in `07_NEXT_PHASE_PLAN.md` §4) to show where the CBL crossover would occur.

**Artifacts:** `evaluation_per_scenario.csv`, `evaluation_aggregate.csv`, `evaluation_statistics.csv`, `results/tables/evaluation_summary.tex`.

**Revisit if:** cross-system expansion (RE2-SS, RE2-TT — different applications, different call topologies) shows greater within-service footprint heterogeneity, which the mechanism above predicts would widen the CBL gap.

---

## ADR-020 — Heterogeneity sweep did NOT confirm the predicted crossover; a more fundamental finding about greedy-vs-CBL took its place

**Status:** Accepted · 2026-08-20 · **Executed as the pre-committed pivot's suggested follow-up (`07_NEXT_PHASE_PLAN.md` §4), after ADR-019. Reported honestly per the project's own standard for negative results.**

**Context.** ADR-019 hypothesized that BLAST's negligible CBL advantage over B9 was caused by RCAEval's near-zero within-service capability-footprint heterogeneity, and predicted the CBL advantage would emerge/widen as heterogeneity increases. `run_heterogeneity_sweep.py` tested this directly: a synthetic generative model (services own a shared-core + private-slice capability footprint, heterogeneity parameter h∈[0,1] controlling the private/core ratio; fault-type-driven severity per incident type, mirroring the real corpus's structure) swept across 11 heterogeneity levels, 20 repetitions each, 600 paired BLAST-vs-B9 scenario comparisons per level.

**Finding 1 (methodological flaw caught before being reported as a result): NDCG@5 in this synthetic design is tautological.** The simplification of setting ground truth equal to BLAST's own model input `p(c|i)` (no separate measurement-noise process, deliberately, to isolate the footprint-heterogeneity variable) makes B9's standalone-score ranking *identical by construction* to the ground-truth ranking — hence B9's NDCG@5 = 1.0 at every single heterogeneity level. This is an artifact of the simplification, not a finding, and NDCG results from this sweep must not be cited. (The real evaluation's NDCG@5 result, ADR-019, is unaffected — it used measured case-level magnitude as ground truth, genuinely distinct from the type-level model input.)

**Finding 2 (real, and it refutes the hypothesis): no heterogeneity level in [0,1] produced a practically significant CBL advantage for BLAST over B9.** B9 outperforms BLAST on CBL at *every* level tested, including h=1.0 (fully disjoint footprints). The gap does not trend toward favoring BLAST as heterogeneity increases.

**Diagnostic follow-up.** Before accepting this, checked whether an objective-composition mismatch explained it: BLAST's greedy maximizes the independent-cascade probabilistic objective `F(S)` (probabilistic OR across incidents, per the KKT-submodular formulation in `03_RESEARCH_DESIGN.md` §2.2), while CBL's ground-truth realization uses conservative max/union composition (TV-2). A second greedy variant was implemented that maximizes the *same* max/union objective CBL actually rewards, tested at h∈{0, 0.5, 1.0}. **This "consistent" greedy performed even worse than the independent-cascade version** — ruling out the mismatch as the explanation. The deficit is not about which coverage formula the greedy uses.

**Working hypothesis, not yet proven.** CBL under uniform repair cost (`03_RESEARCH_DESIGN.md` §2, "one engineer, one incident at a time" default) is structurally a weighted-completion-time scheduling problem. For such problems, sorting by standalone value (exactly B9's rule) is a well-known strong or optimal heuristic *unless* fixing one incident measurably changes the marginal value of fixing another before it does — i.e. unless there is enough overlap-driven interaction to reward reordering. Greedy marginal-gain selection is provably good at maximizing *coverage achieved by a fixed-size set* (the classical (1−1/e) guarantee), but that is a different problem from *sequencing a full repair schedule to minimize integrated loss*, and the two objectives were assumed synonymous without being separately verified. `03_RESEARCH_DESIGN.md` §2.2 itself flagged this exact risk in advance: *"the ordering-under-repair-budget objective is not literally influence maximization... write the proof in week 8-10, and if it does not hold, say so and fall back to reporting greedy as a heuristic."* This ADR is that fallback being triggered by evidence.

**Consequences.** The pre-committed pivot's synthetic-topology heterogeneity story is **not available as a paper claim** — it was tested in good faith and did not hold. This strengthens, rather than replaces, ADR-019's recommendation to lead the paper with the ranking-quality result (NDCG@5, on the real evaluation only) and demote CBL from a headline claim to an honestly-reported secondary result requiring further theoretical work before any generalization claim. The submodularity *guarantee* (Gate 3-adjacent regression checks, ADR-016) remains correct and unaffected — what's unproven is that maximizing that particular submodular function also minimizes realized CBL under sequential uniform-cost repair.

**Artifacts:** `heterogeneity_sweep_results.csv`, `results/figures/heterogeneity_sweep.png`.

**Revisit if:** (a) a non-uniform, incident-specific repair-cost model is introduced (the scheduling-theory literature suggests overlap-aware reordering matters more when costs vary — untested here); (b) the greedy objective is redefined to directly target expected marginal CBL reduction rather than expected coverage (a different, not-yet-implemented algorithm); (c) the promised proof in `03_RESEARCH_DESIGN.md` §2.2 is attempted and either succeeds (explains when/why greedy-coverage tracks CBL) or formally fails (confirms this ADR's finding is fundamental, not an implementation gap).

---

## ADR-021 — Cross-system replication on Train Ticket: the NDCG@5 advantage does NOT replicate, and the mechanism explains why

**Status:** Accepted · 2026-08-21 · **The cross-system expansion ADR-019 recommended, executed and reported honestly regardless of outcome.**

**Context.** ADR-019 found BLAST beats its independent-scoring ablation (B9) on NDCG@5 on Online Boutique (RE2-OB), robust across a 5-model value-weight sweep (this ADR's sibling finding), but with no practical CBL advantage. ADR-019/020 traced the weak CBL result to RCAEval's Online Boutique benchmark having capability footprints determined mostly by *which service* is targeted, not by fault type — meaning technical severity alone predicts business-weighted ground truth well (Spearman ρ=0.939 there), leaving little for business-aware, overlap-correcting set-selection to add. The obvious next question: is that a property of Online Boutique specifically, or of RCAEval's injected-fault methodology generally? Verified before building anything (not assumed): Sock Shop has zero cases with trace data at all (0/90) and is not viable; Train Ticket has traces for all 90 cases and is fully viable — different application entirely (27 services, train-ticket booking rather than e-commerce), same RCAEval fault-injection methodology.

**Finding.** Built the full parallel pipeline for Train Ticket (RE2-TT) — `business_overlay/train_ticket_v1.yaml` (10 capabilities grounded in observed operations), journey typing (generalised `blast_journey_lib.py` for a system with no generic frontend wrapper and, unexpectedly, no `methodName` on any root span — fixed before it could silently zero out every capability attribution), service graph (27 nodes, 55 edges), and the full evaluation harness importing every baseline function directly from the Online Boutique scripts (zero logic duplication, so both systems are evaluated with provably identical methodology). Result, on the same 90 held-out TEST scenarios:

- **NDCG@5: does NOT replicate — and inverts.** BLAST 0.906 vs B9 0.952, Cliff's δ = **-0.280** ("small-to-medium", clears the practical floor in the *opposite* direction from Online Boutique). B9 significantly and practically beats BLAST here, not the reverse.
- **CBL:** no significant difference either way (p_holm=0.345) — weaker signal than even Online Boutique's "significant but negligible" result.

**Diagnosis, checked directly rather than assumed.** The same mechanism as ADR-019, more pronounced: Spearman ρ=0.703 between measured GT_loss and raw technical magnitude (strong, if slightly weaker than Online Boutique's 0.939) — confirming severity alone substantially predicts business-weighted ground truth here too. But Train Ticket's capability *footprints* are more repetitive than Online Boutique's: only **11 distinct footprint patterns across 30 incident types**, with a single pattern (`Admin Configuration;Food Ordering;Order Management;Ticket Reservation;Trip Search`) covering **13/30 (43%) of all incident types**. When footprints are this homogeneous, there is very little genuine set-overlap for greedy marginal-gain reasoning to correctly exploit — and reordering away from a standalone-value ranking that already tracks ground truth well (via the technical-severity correlation) has more room to actively hurt than to help. This is consistent with, not contradictory to, ADR-019/020: the same structural property (footprint homogeneity, service-determined) that made Online Boutique's result weak makes Train Ticket's result actively negative, because Train Ticket's footprints are homogeneous to a *greater* degree.

**Consequences for the paper's framing.** This closes an open question ADR-019 left hanging ("is footprint homogeneity a property of Online Boutique or of the benchmark methodology?") with a real answer: **it looks like a property of RCAEval's injected-fault methodology across at least two different applications**, not an artifact of one demo app's specific design. The paper's central claim needs a more conditional framing than "submodular set-selection improves incident ranking" — the honest, falsifiable version is now: *"submodular set-selection improves ranking accuracy when incident capability footprints are heterogeneous enough for overlap-correction to matter; on RCAEval's two trace-viable benchmarks, footprints are dominated by which service is targeted rather than by fault type, and set-selection's advantage is inconsistent (positive-but-small on Online Boutique, negative on Train Ticket) as a direct, measured consequence."* This is a stronger, more scientifically honest paper than either system's result alone would support — the cross-system replication is what turns a single-benchmark quirk into a characterised, general finding.

**What this does NOT mean:** it does not mean BLAST's algorithm is wrong or the submodularity guarantee is void — greedy still provably (1-1/e)-approximates the coverage-maximization objective it was built to solve on both systems (0 violations, both benchmarks). What's shown, on two systems now, is that *coverage-maximization is not the same objective as matching true business-value priority* when footprints are this homogeneous — the same gap ADR-020 found for CBL specifically, now shown to affect ranking accuracy too when the homogeneity is severe enough (Train Ticket) rather than moderate (Online Boutique).

**Artifacts:** `results/data/re2tt_*` (full parallel output set), `business_overlay/train_ticket_v1.yaml`.

**Revisit if:** a third RCAEval-family system becomes trace-viable (only Online Boutique and Train Ticket currently are; Sock Shop is not), to test whether the homogeneity-severity/set-selection-advantage relationship implied by comparing these two systems (more homogeneous → more negative) holds as a real trend or is coincidental with n=2.

---

## Template for new ADRs

```markdown
## ADR-0nn — <decision in one line>
**Status:** Proposed | Accepted | Superseded by ADR-0mm · <date>
**Context.** What forced a choice?
**Decision.** What we're doing.
**Rationale.** Why this option.
**Alternatives rejected.** Each with the reason — this is the part reviewers and examiners value.
**Consequences.** What this costs us; what we now must do.
**Revisit if:** the condition that would reopen this.
```
