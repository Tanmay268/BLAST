# 03 — Research Design & Evaluation Protocol

**Project:** BLAST — Business-Loss Aware Structural Triage
**Status:** Authoritative. Changes here require an ADR in `01_DECISION_LOG.md`.
**Last updated:** 2026-08-17

---

## 0. Read this first

This document exists because of one fact:

> **Your evaluation metrics (NDCG, MRR, MAP, Precision@K) require a ranked ground truth of incident priority. No public microservice dataset contains one.**

Every other design decision is downstream of how we manufacture that ground truth credibly. If a reviewer does not believe your ground truth, nothing else in the paper matters. Section 3 is therefore the longest and most important section here.

---

## 1. Refined research questions

Your document listed five RQs. Five is too many for one paper and RQ4 ("reduce incident response time") is **not answerable** without a longitudinal deployment in a real organisation, which you do not have. Cut to four, restated as falsifiable claims.

| ID | Research question | Falsifiable hypothesis | Primary metric |
|---|---|---|---|
| **RQ1** | Does propagation over a business-dependency graph rank incidents better than severity-based and feature-based methods? | BLAST achieves higher NDCG@k than static-severity, ITIL-matrix, and AlertRank-style baselines | NDCG@5, NDCG@10, Kendall's τ |
| **RQ2** | Do *learned* edge transmission probabilities beat *topological* importance? | BLAST with learned edge weights beats BLAST with uniform weights and beats PageRank/betweenness centrality baselines | NDCG@k, ablation delta |
| **RQ3** | Does set-level (submodular) selection beat independent per-incident scoring when incidents have overlapping blast radii? | On multi-incident scenarios, submodular ordering achieves lower cumulative business loss than greedy independent scoring | Cumulative Business Loss (CBL), Area Under Loss Curve |
| **RQ4** | Are BLAST's rankings and explanations acceptable to practising engineers? | Engineers agree with BLAST's ordering more often than with a severity baseline, and rate its explanations as more useful | Human agreement rate, Likert usefulness, Kendall's τ vs expert consensus |

**Deliberately dropped:** "Which graph representation best captures business impact?" (your RQ3) — this is an open-ended exploration, not a question with an answer; it becomes an *ablation over graph variants* inside RQ2 instead. And "can graph learning reduce incident response time?" — unanswerable without deployment; reframed as the CBL simulation metric in RQ3, which is an honest proxy and must be labelled as one.

---

## 2. The formal problem

**Given:**
- A heterogeneous business-dependency graph `G = (V, E)`.
- A set of concurrent incident candidates `I = {i₁ … iₙ}`, each anchored at a service node.
- A business value model `B` assigning value rates to business capability nodes.
- A repair-capacity model (default: one engineer, one incident at a time).

**Produce:** an ordering `π` over `I` minimising expected cumulative business loss until all incidents are resolved.

This framing — **ordering under a repair budget**, not scoring — is what makes the submodular result apply, and it is the framing that distinguishes the paper. Write it in the paper exactly this way.

### 2.1 Graph model

`G` is heterogeneous with **four node types** (cut down from the ten in your project document — see ADR-007):

| Node type | Source | Example |
|---|---|---|
| `Service` | Reconstructed from traces | `checkoutservice` |
| `Endpoint` | Trace span operation names | `POST /cart/checkout` |
| `Datastore` | Trace spans to DB/cache/queue | `carts-db`, `redis-cart` |
| `Capability` | **Business overlay** (declared, see §3.3) | `Complete Purchase`, `Browse Catalogue` |

Edge types: `calls` (service→service, from traces), `reads/writes` (service→datastore), `realises` (endpoint→capability), `exposes` (service→endpoint).

Each edge `(u,v)` carries a **failure transmission probability** `p(u,v) ∈ [0,1]`: the probability that, conditioned on `u` being degraded, `v` becomes degraded. This is the learned quantity and the heart of RQ2.

### 2.2 Impact model

Adopt the **Independent Cascade** model from Kempe–Kleinberg–Tardos (KDD 2003). An incident at service `s` activates `s`; each newly-activated node `u` attempts to activate each out-neighbour `v` once, succeeding with probability `p(u,v)`. Capability nodes reached are *impaired*.

Expected business loss of an incident set `S`:

```
L(S) = E[ Σ_{c ∈ Capabilities} value(c) · 1{c reachable from S} ]
```

**Key property:** `L(S)` is monotone and submodular in `S` — this follows directly from KKT's Theorem 2.2 (expected influence spread under IC is submodular), with capability value weights preserving submodularity since a non-negative weighted sum of submodular functions is submodular.

> ✅ **Why this matters for the paper.** It gives you a *theorem*, not just an empirical result. Greedy ordering achieves a (1−1/e) approximation of the optimal loss-reduction schedule. A theoretical guarantee in an applied AIOps paper is disproportionately valuable at review — it is the difference between "engineering report" and "research contribution."
>
> ⚠️ **You must actually prove this for your specific objective**, not merely cite KKT. The ordering-under-repair-budget objective is not literally influence maximization; it is closer to a *min-sum-of-weighted-completion-times* scheduling problem with submodular value. **Write the proof in week 8–10, and if it does not hold, say so and fall back to reporting greedy as a heuristic.** Do not claim a guarantee you have not derived. This is the single highest-risk technical claim in the project.

### 2.3 Ranking

Greedy: repeatedly select the incident whose repair yields the largest marginal recovery of expected business value per unit repair cost.

```
next = argmax_{i ∈ remaining}  [ L(remaining) − L(remaining \ {i}) ] / cost(i)
```

Note this is *marginal loss reduction*, which naturally handles the overlap case in G3: once checkout is restored by fixing A, incident B's marginal value drops.

---

## 3. Ground truth — the critical section

### 3.1 The constraint we're working under

You have a laptop, 16 GB RAM, no GPU, no Kubernetes cluster. The original "run the app, inject faults, measure revenue loss" plan is therefore **not available as a live experiment**. Here is the resolution, and it is actually methodologically *stronger* than the original plan.

### 3.2 Trace-driven measured ground truth (primary)

**Insight:** RCAEval already ran the experiment you wanted to run. It injected 735 real faults into three real microservice systems and **released the distributed traces**. A distributed trace is a record of an actual end-to-end request through the system. So:

> The business impact of a fault is **directly measurable, offline, from the released traces** — by counting how many end-to-end user journeys failed or degraded during the fault window, compared to the fault-free baseline window.

This is not simulation of the failure. The failure is real and was really measured. Only the *monetary valuation* is overlaid. That is a defensible and honest position.

**Procedure (per fault case):**

1. **Baseline window.** Take the pre-injection normal period. Extract all root spans; group into journey types by entry endpoint (e.g. `POST /checkout`, `GET /products`).
2. **Fault window.** Same extraction during injection.
3. **Journey outcome classification.** For each journey instance, classify as `success`, `failed` (error span in the trace), or `degraded` (latency above the baseline p99).
4. **Measured impact vector.** For each journey type `j`: `Δfail(j)`, `Δdegraded(j)`, `Δthroughput(j)`.
5. **Business valuation.** Apply the business value model `B` (§3.3) to convert the impact vector into a scalar ground-truth loss.
6. **Ground-truth ranking.** Within a synthesised multi-incident scenario, rank the constituent incidents by their measured loss.

**Scenario synthesis.** RCAEval faults are injected one at a time; you need *concurrent* incident sets. Construct scenarios by sampling k incidents (k ∈ {3,5,10}) from the fault-case pool for the same system and composing their measured impact vectors.

> ⚠️ **Composition is an assumption and reviewers will probe it.** Combining two independently-measured faults assumes their effects compose (we will use a max/union rule on impaired journeys, not a sum). This is a **threat to validity — state it explicitly in the paper** (§8, TV-2). Mitigate by (a) using union semantics which is conservative, (b) validating on the small subset of RCAEval cases with multiple simultaneous faults if any exist, (c) reporting results separately for single- and multi-incident settings.

### 3.3 The business value model — handle with care

There is no revenue data in any public dataset. You must declare a value model. **The failure mode is inventing numbers and pretending they're real.** Do this instead:

1. **Declare it as an explicit, versioned input artifact** — a YAML file, not code. `business_overlay/online_boutique.yaml`.
2. **Ground it in the application's own semantics.** Online Boutique is an e-commerce demo: `Complete Purchase` > `Add to Cart` > `Browse Catalogue` > `View Ads` is defensible from the app's design, not invented.
3. **Run a sensitivity analysis.** Define 3–5 alternative value models (revenue-weighted, user-volume-weighted, uniform, SLA-weighted, adversarial/inverted). **Report BLAST's results under all of them.** If your ranking advantage survives value-model perturbation, the result is robust and reviewers relax. If it collapses under uniform weighting, you have learned something important and must report it.
4. **Validate against humans** (§3.4). If engineers independently produce a value ordering close to yours, that is external validation of the overlay.

> ✅ This turns your biggest weakness into a contribution: *"we provide the first business-overlay specification and sensitivity methodology for impact-aware incident evaluation."* Release the overlay files as an artifact.

### 3.4 Human validation study (secondary ground truth)

**Purpose:** validate the value model, answer RQ4, and provide human-anchored ground truth on a subset.

- **Participants:** 10–20. Recruit from: your university's alumni in SRE/DevOps roles, LinkedIn outreach to SREs, r/devops and r/sre (with mod permission), DevOps Discord/Slack communities. Target ≥2 years production on-call experience. Aim for 15; 10 is the floor for reporting.
- **Instrument:** a web form presenting 10–15 scenarios. Each scenario = a system diagram + 5 concurrent incidents with realistic descriptions (service, symptom, error rate, latency, affected endpoints). Task: rank the 5 by "fix first."
- **Also collect:** (a) agreement with BLAST's ordering vs baseline ordering, blind and order-randomised; (b) 5-point Likert on explanation usefulness; (c) free-text on disagreements — this is gold for the discussion section.
- **Analysis:** inter-rater agreement (Kendall's W), expert-consensus ranking as ground truth, τ between each method and consensus.
- **Ethics:** check whether your institution requires IRB/ethics review for human-subject surveys. **Do this in week 1 — approval can take 4–8 weeks and will silently block you.** Anonymous, no personal data, informed consent statement at the top.

### 3.5 What we explicitly do NOT claim

- We do not claim to measure real revenue. We measure *journey impairment* and apply a declared valuation.
- We do not claim the composed multi-incident scenarios occurred in reality.
- We do not claim reduced MTTR in production. We report a simulated cumulative-loss proxy.

Stating these plainly *before* a reviewer does is a strength, not a weakness.

---

## 4. Datasets

| Dataset | Role | Notes |
|---|---|---|
| **RCAEval RE2** (Online Boutique 12 svc, Sock Shop 15 svc, Train Ticket 64 svc) | **Primary.** 270 cases, 6 fault types, multi-source incl. traces | Traces are what we need. Verify trace availability per system before committing. |
| **RCAEval RE3** | Secondary — code-level faults (90 cases) | Tests generalisation beyond resource faults. |
| **RCAEval RE1** | Not used | Metric-only; no traces → no journey extraction possible. |
| Train Ticket (64 services) | **Scale evaluation** | Use to show the method scales; may be too large to process fully on 16 GB — subset if needed. |

> ⚠️ **Storage risk.** RCAEval reports 4.5–76.7 million traces and 1.7–26.9 million log lines per system. Uncompressed this may substantially exceed a laptop disk. **Week 2 gate: download Online Boutique RE2 only, measure actual disk footprint, then decide.** Plan to (a) work per-fault-case in a streaming fashion, (b) extract a compact journey summary per case and discard raw traces, (c) never hold a full system's traces in RAM.

**Do not touch logs.** Journey extraction needs traces only. Logs triple your storage for no benefit under the current design. (ADR-009)

---

## 5. Baselines

Baselines must be *fair* and *reproducible*. A weak baseline set is a rejection reason.

| # | Baseline | Why included | Implementation |
|---|---|---|---|
| B1 | **Random** | Sanity floor | Trivial |
| B2 | **Static severity** | What most tools do; your paper's straw man — but a *real* one | Map fault magnitude → SEV1-4 |
| B3 | **ITIL priority matrix** | What industry actually does | Impact × Urgency 3×3 matrix, standard ITIL definitions |
| B4 | **PageRank centrality** | Tests "is topology enough?" — directly probes RQ2 | networkx |
| B5 | **Betweenness centrality** | Alternative topological importance | networkx |
| B6 | **Personalized PageRank from incident nodes** | Strongest topological competitor | networkx |
| B7 | **AlertRank-style feature classifier** | Your closest published competitor | Re-implement its *approach* (gradient-boosted classifier over local incident features) — **label it a "reimplementation in the spirit of" since you can't get their proprietary data.** Be honest about this in the paper. |
| B8 | **GNN/GAT regression** | Tests "is a learned black box enough?" | 2-layer GAT predicting per-incident loss, CPU-trainable at this graph size |
| B9 | **BLAST-independent** (ablation-as-baseline) | Isolates the submodular contribution — **the most important comparison in the paper** | Our model, scoring incidents independently |

> 🚩 **On TrioXpert and ART** (named as baselines in your project doc): only include them if you verify they exist, are peer-reviewed, have released code, and actually perform *prioritization*. If they only do localization, comparing against them is a category error and a reviewer will say so. Most likely outcome: you cite them as related work and do not compare. That is fine and correct.

---

## 6. Metrics

**Ranking quality (primary):**
- NDCG@{1,3,5,10} — main headline metric, handles graded relevance
- Kendall's τ and Spearman's ρ against full ground-truth order
- MRR — for "was the truly-worst incident ranked first?"
- Precision@k / Top-k accuracy

**Decision quality (the metric that actually matters):**
- **Cumulative Business Loss (CBL)** — simulate sequential repair under the ordering, integrate loss over time until all resolved. Lower is better. This is your most compelling result because it speaks the practitioner's language.
- **Area Under the Loss Curve (AULC)**, normalised against the oracle ordering and the random ordering.

**Efficiency:**
- End-to-end ranking latency (must be well under a minute to be operationally credible)
- Graph construction time; peak memory
- Scaling curve across 12 → 15 → 64 service systems

**Human (RQ4):**
- Kendall's W (inter-rater agreement); τ vs expert consensus; Likert explanation usefulness

**Statistics — do not skip this:**
- Report mean ± std over ≥30 scenario samples per configuration
- Significance: Wilcoxon signed-rank (paired, non-parametric — appropriate here)
- Effect size: Cliff's delta
- Correct for multiple comparisons (Holm–Bonferroni)
- Fix and record random seeds; Monte Carlo cascade sampling must be seeded

---

## 7. Ablation study

| Ablation | Removes | Tests |
|---|---|---|
| A1 `−business-overlay` | Capability nodes; loss = services impaired | Does business semantics matter? (RQ1) |
| A2 `−learned-p` | Learned edge probs → uniform p=0.5 | Does learning transmission matter? (RQ2) |
| A3 `−propagation` | Blast radius → 1-hop neighbours only | Does multi-hop reasoning matter? |
| A4 `−submodular` | Greedy set selection → independent scoring | **Does set-level reasoning matter? (RQ3) — headline ablation** |
| A5 `−edge-types` | Heterogeneous → homogeneous graph | Does node/edge typing matter? |
| A6 value-model sweep | 5 alternative business overlays | Robustness (§3.3) |
| A7 `p` estimation method | MLE vs Bayesian smoothing vs regression | Sensitivity of the core learned quantity |

A4 is the one reviewers will look for. Make sure it is clean and the effect is real. **If A4 shows no benefit, the central claim of the paper is dead** — run A4 as early as possible (see the Phase 4 gate in the master plan) rather than at the end.

---

## 8. Threats to validity (draft the paper section now, not later)

**Construct validity**
- **TV-1 — The business value model is declared, not observed.** Mitigation: sensitivity analysis over 5 models; human validation; released as an artifact for scrutiny.
- **TV-2 — Multi-incident scenarios are composed from independently-injected faults.** Mitigation: conservative union semantics; separate reporting for single-incident cases; explicit statement.
- **TV-3 — "Journey degradation" is a proxy for business harm.** Mitigation: state it; it is the closest observable.

**Internal validity**
- **TV-4 — Transmission probabilities are learned from the same fault corpus used for evaluation.** Mitigation: **strict train/test split by fault case, stratified by service and fault type. Never let a test fault's traces inform its own edge probabilities.** This is a leak reviewers actively hunt for. Design the split in week 6, before any modelling.
- **TV-5 — Baseline reimplementation (B7) may be weaker than the original.** Mitigation: tune it as carefully as your own method; report hyperparameter search; label it a reimplementation.

**External validity**
- **TV-6 — Three benchmark systems, all demo applications.** Mitigation: 12/15/64-service range; discuss limits candidly; do not claim production generality.
- **TV-7 — Fault injection ≠ real production failures.** Mitigation: acknowledge; note RCAEval is the field's accepted benchmark.
- **TV-8 — Small human study (n≈15).** Mitigation: report as supporting evidence, not proof; report agreement statistics honestly including disagreements.

**Conclusion validity**
- **TV-9 — Multiple comparisons across many configurations.** Mitigation: Holm–Bonferroni; pre-register which comparison is the primary one (it is RQ1's NDCG@5).

---

## 9. Reproducibility commitments

- Public GitHub repo, permissive licence, DOI via Zenodo
- Pinned dependencies (`uv` or `pip-tools` lockfile)
- All seeds fixed and logged; one command reproduces every table and figure
- Business overlay YAMLs released
- Human study instrument and anonymised responses released
- Aim for an **artifact-evaluation badge** — cheap to obtain and disproportionately improves reception

---

## 10. Paper outline (target ~10–12 pages, double column)

1. Introduction — the "which first?" problem, motivating example with two same-severity incidents of wildly different impact
2. Background & Related Work — the four clusters from `04_LITERATURE_GAP.md`
3. Problem Formulation — §2 here; the ordering-under-repair-budget framing
4. The BLAST Framework — graph construction, transmission learning, submodular ranking, explanation
5. Theoretical Analysis — submodularity and the approximation guarantee (**if it survives §2.2's warning**)
6. Evaluation Setup — datasets, ground truth methodology (this will be a *long* subsection and that is correct)
7. Results — RQ1–RQ4
8. Discussion — when it fails, what engineers disagreed with
9. Threats to Validity — §8
10. Conclusion

**Write Sections 3, 4, and 6 during implementation, not after.** Writing the formalism forces you to find holes in the design while they are still cheap to fix.
