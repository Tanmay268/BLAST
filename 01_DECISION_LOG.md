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
