# 00 — Master Plan

**Project:** BLAST — Business-Loss Aware Structural Triage for Microservice Incidents
**Owner:** Tanmay · Final-year B.Tech CS, VIT Vellore
**Last updated:** 2026-08-17

---

## The one-paragraph version

Existing microservice AIOps tells you *what broke and where*. It does not tell you *what to fix first*. BLAST takes incident candidates from upstream detectors and ranks them by predicted business consequence, by propagating failure over a heterogeneous business-dependency graph with **learned per-edge transmission probabilities**, and selecting a repair order via **greedy submodular coverage of business capabilities** — which correctly handles the fact that concurrent incidents have *overlapping* blast radii, something every existing method gets wrong. Evaluated on RCAEval's trace-bearing fault corpus (RE2: 270 cases, RE3: 90 cases, out of 735 total across three systems), against nine baselines, with ground truth measured from released distributed traces and validated by a study of practising SREs.

---

## How to use this document

Six phases, each with **deliverables** and a **gate**. A gate is a go/no-go checkpoint with an explicit kill or pivot criterion. Do not start a phase before passing the previous gate. The gates exist so that if the project is going to fail, it fails in week 6 rather than week 22.

Phase durations assume ~15–20 focused hours/week alongside coursework. Your timeline is set by the university deadline, so treat the week numbers as *relative sequence and proportion*, and compress or stretch uniformly. Section 8 gives a compressed variant.

---

## Phase 0 — Foundations *(Weeks 1–2)*

**Goal:** remove the three unknowns that could invalidate the whole plan, before investing in anything.

| # | Task |
|---|---|
| 0.1 | Read Tier-1 papers (`04_LITERATURE_GAP.md` §5). Start a BibTeX file and a one-paragraph note per paper. |
| 0.2 | **Verify TrioXpert and ART exist, are peer-reviewed, have public code, and do prioritization.** If not, drop them as baselines and record it. |
| 0.3 | **Check institutional ethics/IRB requirements for the human study.** Start the application immediately if needed — approval can take 4–8 weeks and will silently block Phase 6. |
| 0.4 | Set up repo, `uv` environment, pytest, CI, `docs/` from this set. |
| 0.5 | Download **one** RCAEval fault case. Inspect trace format by hand. Confirm spans carry parent IDs, service names, operation names, error status, and duration. |
| 0.6 | Show these documents to your supervisor. Get sign-off on the ADR-011 direction specifically. |

**Deliverables:** repo skeleton · BibTeX with 10+ entries · ethics application submitted (if required) · one-page written confirmation that traces support journey reconstruction.

> ### 🚦 GATE 0
> **Pass if:** RCAEval traces contain parent-child span structure with error status and duration.
> **If FAIL:** the trace-driven ground truth (ADR-002) is dead. **Pivot:** metric-based impairment proxies — weaker, must be flagged as a major threat. Escalate to your supervisor immediately; do not proceed quietly.

---

## Phase 1 — Data acquisition & feasibility *(Weeks 3–4)*

| # | Task |
|---|---|
| 1.1 | Download RCAEval RE2 for **Online Boutique only**. Measure actual disk footprint. |
| 1.2 | Extrapolate storage for Sock Shop and Train Ticket. Decide which systems are in scope. |
| 1.3 | Build `blast.ingest` — fetch, verify, normalise per-case layout, emit manifest. |
| 1.4 | Prototype trace parsing on 5 cases. Time it. Extrapolate to the full corpus. |
| 1.5 | **Freeze the journey-summary schema** (ADR-004 consequence — getting this wrong costs days later). Over-collect fields. |

**Deliverables:** ingest module · measured storage/time budget · frozen schema doc.

> ### 🚦 GATE 1
> **Pass if:** (a) at least Online Boutique fits on disk with the streaming/delete strategy, and (b) full-corpus parse time is under ~48 machine-hours.
> **If FAIL on storage:** reduce to a stratified subsample of fault cases (target ≥100, stratified by service and fault type) and document the sampling as a limitation.
> **If FAIL on time:** parallelise across cores, or subsample. Do not proceed to Phase 2 hoping it gets faster.

---

## Phase 2 — Trace distillation & ground truth *(Weeks 5–8)* ⚠️ **critical path**

This is the highest-risk, highest-effort phase. Everything downstream is blocked on it. Protect this time.

| # | Task |
|---|---|
| 2.1 | Implement `blast.traces`: streaming, per-case, checkpointed, crash-resumable. |
| 2.2 | Journey reconstruction: root span → span tree → journey type by entry endpoint. |
| 2.3 | Outcome classification: `success` / `failed` (error span) / `degraded` (> baseline p99). |
| 2.4 | Baseline-vs-fault window comparison → measured impact vector per case. |
| 2.5 | **Sanity-check against known root causes.** For each case, does the *known* faulty service actually appear in the impaired journeys? If not, your parsing is wrong. **This is your correctness oracle — use it heavily.** |
| 2.6 | Write `business_overlay/online_boutique.yaml` v1, grounded in the app's actual e-commerce semantics. |
| 2.7 | Apply valuation → ground-truth loss per fault case. |
| 2.8 | Build scenario synthesis (sample k incidents, union semantics for composition). |
| 2.9 | **Freeze `config/splits/` train/test manifest** (ADR-012), stratified, before any modelling. |

**Deliverables:** distilled journeys for all in-scope cases · ground-truth loss table · overlay v1 · scenario generator · frozen split manifest.

> ### 🚦 GATE 2 — the most important gate in the project
> **Pass if:** in ≥80% of fault cases, the measured journey impairment is non-trivial (the fault visibly affected user journeys) **and** the impaired services are consistent with RCAEval's annotated root cause.
> **If FAIL:** either parsing is broken (debug it — most likely) or many injected faults had no user-visible effect (real finding: report the distribution, restrict evaluation to cases with measurable impact, and *say so*).
> **Kill criterion:** if fewer than ~50 cases show measurable journey impact, there is not enough signal for a ranking study. Escalate to your supervisor and consider pivoting to a synthetic-topology study.

---

## Phase 3 — Graph construction & transmission learning *(Weeks 9–11)*

| # | Task |
|---|---|
| 3.1 | `blast.graph`: build topology from baseline traces (services, endpoints, datastores, call edges). |
| 3.2 | `blast.overlay`: pydantic-validated loader; attach capability nodes and `realises` edges. |
| 3.3 | Visual inspection — does the graph match Online Boutique's documented architecture? Another free correctness oracle. |
| 3.4 | `blast.transmission` estimator 1: MLE with Laplace smoothing, **training split only**. |
| 3.5 | Estimator 2: Bayesian Beta-Binomial with uncertainty. |
| 3.6 | Estimator 3: feature-based logistic regression (generalises to unseen edges — the deployability story). |
| 3.7 | Analyse learned probabilities. **Do they make engineering sense?** Cache and async edges should transmit less; synchronous critical-path edges more. If the numbers are nonsense, the estimator or the data is wrong. |

**Deliverables:** BDG for each in-scope system · three fitted transmission estimators · a figure of learned probabilities (this will be a good paper figure).

> ### 🚦 GATE 3
> **Pass if:** the graph matches known architecture, and learned probabilities show meaningful variance across edges (not all collapsing to the prior).
> **If FAIL (all probabilities ≈ prior):** data is too sparse. Fall back to the feature-based estimator as primary, and report sparsity honestly as a limitation — it is a legitimate finding about how much incident history impact-estimation requires.

---

## Phase 4 — Impact engine & ranker *(Weeks 12–14)*

| # | Task |
|---|---|
| 4.1 | `blast.impact`: Monte Carlo independent cascade; tune R for variance stability. |
| 4.2 | Reverse-reachable-set optimisation for fast repeated `L(S)` queries. |
| 4.3 | Propagation path extraction (this is the explanation — get it early, RQ4 depends on it). |
| 4.4 | `blast.rank`: greedy marginal-gain ordering with CELF lazy evaluation. |
| 4.5 | Explanation templating: "Fix X first — it impairs *Complete Purchase* via `checkout → payment`, 78% confidence." |
| 4.6 | **Run ablation A4 NOW, early:** submodular vs independent scoring, on a preliminary scenario set. |

**Deliverables:** working end-to-end ranker · explanations · **preliminary A4 result**.

> ### 🚦 GATE 4 — the go/no-go on the central claim
> **Pass if:** A4 shows submodular ordering measurably beating independent scoring on scenarios with overlapping blast radii.
> **If FAIL:** ADR-011's core claim is empirically dead. **Pivot now, in week 14, with time to recover:** the contribution becomes the learned-transmission business graph model (RQ1 + RQ2 only), still publishable at a lower tier. Update ADR-011 to Superseded and rewrite the positioning statement.
>
> This gate is placed deliberately early. Discovering this in week 22 would be unrecoverable.

---

## Phase 5 — Baselines, theory & evaluation *(Weeks 15–19)*

| # | Task |
|---|---|
| 5.1 | Implement baselines B1–B6 (random, severity, ITIL, PageRank, betweenness, PPR). Fast. |
| 5.2 | B7 — AlertRank-style gradient-boosted classifier. Tune it as hard as your own method (fairness). |
| 5.3 | B8 — 2-layer GAT regressor, CPU. |
| 5.4 | B9 — BLAST-independent (ablation-as-baseline). |
| 5.5 | `blast.eval`: scenario sampling, all metrics, Wilcoxon + Cliff's delta + Holm–Bonferroni, LaTeX/figure emission. **One command reproduces every number.** |
| 5.6 | Full ablation suite A1–A7. |
| 5.7 | Value-model sensitivity sweep (≥5 overlays incl. uniform and adversarial). |
| 5.8 | Scaling evaluation across 12 → 15 → 64 service systems. |
| 5.9 | **Write the submodularity proof for your specific objective** (ADR-011 consequence). If it fails, downgrade to "well-motivated heuristic" and say so. |
| 5.10 | Noise-robustness experiment (ADR-001 consequence): degrade incident inputs, show graceful decay. |

**Deliverables:** complete results tables and figures · ablation study · sensitivity analysis · theory section (or documented negative result).

> ### 🚦 GATE 5
> **Pass if:** BLAST beats B2/B3/B7 on NDCG@5 with statistical significance, and the advantage survives at least 4 of 5 value models.
> **If FAIL:** diagnose before writing. Common causes: overlay too coarse, transmission probabilities too sparse, scenarios too easy (if random does well, your scenarios lack discriminative power — regenerate harder ones). A negative result honestly reported is still a valid final-year project; it is not a valid paper without a diagnosis of *why*.

---

## Phase 6 — Human study, dashboard & paper *(Weeks 20–26)*

| # | Task |
|---|---|
| 6.1 | Build the study instrument: 10–15 scenarios, randomised order, blind method labels. |
| 6.2 | Recruit 10–20 SREs/DevOps engineers (alumni network, LinkedIn, r/devops, r/sre, DevOps communities). |
| 6.3 | Run study; analyse Kendall's W, τ vs consensus, Likert usefulness, free-text disagreements. |
| 6.4 | `blast.dashboard` — Streamlit, 4 views, thin (ADR-008). |
| 6.5 | Write the paper. Sections 3/4/6 should already exist from earlier phases. |
| 6.6 | Prepare the artifact: pinned deps, `reproduce_paper.sh`, Zenodo DOI, overlay YAMLs, study instrument. |
| 6.7 | Internal review: supervisor, then two peers unfamiliar with the project. |
| 6.8 | Viva/demo preparation. |

**Deliverables:** human study results · dashboard · complete paper draft · reproducible artifact.

> ### 🚦 GATE 6
> **Pass if:** paper draft complete, one command reproduces every number, supervisor approves for submission.

---

## 2. Risk register

| ID | Risk | Likelihood | Impact | Mitigation | Gate |
|---|---|---|---|---|---|
| R1 | Traces lack structure for journey reconstruction | Low | **Fatal** | Verify in week 1 on one case | G0 |
| R2 | Dataset exceeds disk | **High** | High | Stream + delete + subsample | G1 |
| R3 | Trace parsing takes far longer than planned | **High** | High | Prototype and extrapolate in week 4; parallelise | G1 |
| R4 | Many faults have no user-visible impact | Medium | High | Report distribution; restrict to measurable cases | G2 |
| R5 | Transmission data too sparse; probabilities collapse to prior | **Medium-High** | Medium | Feature-based estimator as fallback | G3 |
| R6 | Submodular advantage doesn't materialise | Medium | High | **A4 run early at G4**; pivot to RQ1+RQ2 contribution | G4 |
| R7 | Submodularity proof fails for the actual objective | Medium | Medium | Report greedy as heuristic; lean on empirical A4 | G5 |
| R8 | Ethics approval delays human study | Medium | Medium | **Apply in week 1** | G0 |
| R9 | Can't recruit enough SREs | Medium | Low | n=10 floor; report as supporting evidence | — |
| R10 | Competing paper published first | Low | Medium | Monthly arXiv alerts; sharpen differentiator | — |
| R11 | Scope creep back toward the original 10-node-type design | **High** | High | ADRs are the defence; every addition needs a new ADR | — |
| R12 | TrioXpert/ART turn out not to be usable baselines | **High** | Low | Verify week 1; cite as related work instead | G0 |

**R11 deserves emphasis.** You build complete, polished systems — that instinct is an asset in engineering and a liability in research. The temptation to add the other six node types, the React dashboard, the RL module, will be strong around week 15 when the core is working and looks "too simple." **Simple and rigorously validated is what publishes.** If you want to add something, write an ADR first; the act of justifying it usually kills it.

---

## 3. Deliverable checklist (maps to your project brief)

| Brief deliverable | Where it lands | Status |
|---|---|---|
| Research paper | Phase 6 | Planned |
| System architecture | `02_ARCHITECTURE.md` | ✅ Done |
| Dependency graph construction module | `blast.graph`, Phase 3 | Planned |
| Business impact analyzer | `blast.impact`, Phase 4 | Planned |
| Priority optimization algorithm | `blast.rank`, Phase 4 | Planned |
| Dashboard | `blast.dashboard`, Phase 6 | Planned |
| Experimental evaluation | Phase 5 | Planned |
| Ablation study | Phase 5, A1–A7 | Planned |
| Baseline comparison | Phase 5, B1–B9 | Planned |
| Open-source implementation | Phase 6 artifact | Planned |

All ten brief deliverables are covered. Nothing you asked for has been dropped — items removed from *scope* (RL, GNN-as-core, ten node types) are documented as rejected alternatives with reasons, which is itself a deliverable for your report.

---

## 4. Weekly discipline

- **Monday:** pick the week's tasks from the current phase; write them down.
- **Throughout:** any non-obvious choice → new ADR. Do not batch these; you will forget the reasoning.
- **Friday:** 30 minutes updating `04_LITERATURE_GAP.md` with anything new you read.
- **End of phase:** write the gate assessment in this file before moving on. Even one paragraph.
- **Monthly:** supervisor update using the phase deliverables as the agenda.

---

## 5. What "done" looks like

A tight, honest paper making one sharp claim — that incident prioritization is a set-selection problem over business capabilities under stochastic failure propagation, and that treating it as such measurably outperforms severity-based, rule-based, topological, and feature-based prioritization. Backed by nine baselines, seven ablations, a sensitivity analysis, a human study, a reproducible artifact, and a candid threats-to-validity section.

That is a better outcome than a system implementing every idea in the original brief and validating none of them.

---

## 6. Immediate next actions (this week)

1. **Verify TrioXpert and ART.** Search DBLP and GitHub. 30 minutes. Blocks baseline selection.
2. **Check ethics/IRB requirements.** Email your department. 15 minutes to send. Blocks Phase 6, 4–8 week lead time.
3. **Download one RCAEval fault case and open the traces.** 1–2 hours. This is GATE 0 and it either validates or kills the entire ground-truth strategy.
4. **Read the AlertRank paper end to end.** 2 hours. It is your closest competitor; you need to know it cold.
5. **Send these documents to your supervisor**, flagging ADR-011 as the decision you want their opinion on.

Do #3 first. Everything else is contingent on it.

---

## 7. Compressed variant (if the deadline is tight)

If you have ~17–18 weeks rather than ~26, cut in this order — and only in this order (the cuts below total ~8.5 weeks; going below ~16 weeks means cutting into the "never cut" list, which is not worth doing — better to negotiate the deadline):

1. Drop Train Ticket and Sock Shop; **Online Boutique only**. (−3 weeks)
2. Drop the human study; RQ4 becomes future work. (−3 weeks) *— do this only if ethics approval is the blocker; the study is high value per hour.*
3. Drop baselines B5, B8; keep B1, B2, B3, B4, B6, B7, B9. (−1 week)
4. Drop ablations A3, A5, A7; **keep A1, A2, A4, A6.** (−1 week)
5. Dashboard reduced to 2 views. (−0.5 weeks)

**Never cut:** Gate 2 (ground truth validity), ablation A4 (the central claim), the value-model sensitivity sweep A6 (your defence against the biggest reviewer attack), or the statistical testing. Cutting any of those removes the reason the work is publishable.
