# 07 — Next Phase Plan (Post-Pilot)

**Status:** Authoritative for the next ~4 weeks. Supersedes the Phase 2–4 task ordering in `00_MASTER_PLAN.md`.
**Written:** 2026-08-17, after reviewing the pilot progress note.
**Position:** Gates 0 and 1 **passed**. Gate 2 partially met. Gate 4 attempted and returned a **null result** that is diagnostic, not fatal.

---

## 0. The headline correction

Your progress note ranks the next tasks as:

1. Expand the fault dataset ← *you marked this "the most important next task"*
2. Improve capability attribution
3. Expand propagation observations

**Flip 1 and 2.** Fix attribution first. Here is why, and it is the most important thing in this document.

### The saturation is an attribution bug, not a diversity problem

Your pilot showed Incident 1 covering **9/9 capabilities**, so every subsequent incident had Δ = 0. You diagnosed this as "the six incidents are too homogeneous." That is half right. The other half:

> A `checkoutservice` CPU fault should **not** impair *Advertisement Retrieval* or *Product Recommendations*. Those capabilities are served by `adservice` and `recommendationservice`, which sit on a completely different branch of the call graph. The fact that they lit up means the attribution rule is wrong.

The mechanism is almost certainly this: your attribution is **service-level**. A checkout fault slows `frontendservice` (because the frontend waits on checkout). `frontendservice` calls *everything*, so it maps to *every* capability. Once the frontend is flagged impaired, all 9 capabilities light up regardless of what actually broke.

**`frontendservice` is a universal amplifier.** Every incident that touches it covers the entire capability universe.

Two pieces of evidence in your own note support this:

- Your service graph has **7 services**, but Online Boutique has ~11. Missing: `cartservice`, `shippingservice`, `adservice`. Yet operations `GetCart`, `AddItem`, `EmptyCart`, `GetAds`, `GetQuote`, `ShipOrder` **do** appear in your traces. That means those spans are recorded under the **caller's** `serviceName` — so the Cart, Shipping, and Advertisement capabilities are already being attributed to `frontendservice`/`checkoutservice`. They can never be isolated at service granularity.
- Your `incident_capability_overlap.csv` found pairs with **J(A,B) = 1.0** — identical capability sets. That is the signature of a saturating attribution rule, not of genuinely identical incidents.

### Why this ordering matters practically

If you expand to 90 cases **before** fixing attribution, you get 90 incidents that each cover 9/9 capabilities. `F(S)` saturates at K=1 every single time, BLAST ties the baseline on all 90, and you will have spent a week of compute to reproduce the null result at larger N. Fix the denominator first.

---

## 1. Three more findings you should know before planning

### 1.1 RE2-OB is smaller than you think — 90 cases, but only **5 target services**

Verified this session: RE2-OB = **6 fault types × 5 services × 3 repetitions = 90 cases**. Naming convention `{benchmark}_{service}_{fault}_{instance}`, each case containing `traces.csv`, `metrics.json`, `logs.csv`, `inject_time.txt`.

Consequences:

- Your ceiling is **30 distinct (service, fault) incident types**, not 90 independent incidents. The 3 repetitions are for reliability, not diversity.
- Your progress note lists 7 target services to expand across. **At most 5 exist.** Enumerate the actual directory names before planning around a service list.
- 30 distinct incident types is *enough* for a first result, but it is thin for the propagation model. Cross-system expansion (RE2-SS Sock Shop, RE2-TT Train Ticket) is how you get both more data and an external-validity claim.

### 1.2 Your propagation data may be telling you propagation is rare — and that is a risk to the contribution

Look at your own numbers:

```
CPU    checkout → payment        2/3 = 0.667
Delay  checkout → payment        0/3 = 0
Both   checkout → currency       0/3 = 0
Both   checkout → productcatalog 0/3 = 0
```

Three of four edges show **zero** propagation, and the delay fault propagates to nothing. This is physically sensible: a latency fault injected *into* checkout makes checkout slow while its downstream calls remain normal. Downstream services are genuinely unaffected.

But if that pattern holds across the full 90 cases, then:

> Learned edge transmission probabilities are mostly ≈ 0, the graph contributes almost nothing, and RQ2 ("do learned transmission probabilities beat topological importance?") answers itself in a way that weakens the structural half of your contribution.

**Do not discover this in week 4.** Add an explicit **propagation prevalence audit** (Step 3.5 below) that measures, across all cases, what fraction of (fault, edge) pairs show any downstream impairment. Then you know which of these you are writing:

- *High prevalence* → the full BLAST story holds.
- *Low prevalence* → the contribution rests on the **business-capability set-selection** half, and multi-hop propagation gets demoted to a secondary component. Still publishable — but you reframe deliberately in week 4 rather than being cornered in week 20.

This is a genuinely interesting finding either way: *"in the field's standard benchmark, injected faults are substantially more self-contained than propagation-based RCA methods assume."* Note that the recent literature is already circling this — see the fault-propagation-aware benchmark critique (arXiv 2510.04711) and the "oversimplified benchmarks" empirical study. You may be able to cite company on this point.

### 1.3 You are currently evaluating BLAST with BLAST's own objective function

`blast_vs_baseline.csv` compares greedy vs independent on **capability coverage@K**. But coverage@K *is* `F(S)` — the function greedy explicitly maximizes. Greedy is provably ≥ independent on it. So:

- When BLAST wins, the result is near-tautological and a reviewer will say so.
- When it ties (as now), it only tells you the objective is degenerate.

Keep coverage@K as an **internal sanity check**. The paper's headline metrics must be computed against **ground truth derived independently of the model** — measured journey impairment, per ADR-002. You have not built that yet. Step 5 does.

---

## 2. What the pilot actually earned you

Stated plainly, because it is a lot and the null result shouldn't overshadow it:

| Established | Evidence |
|---|---|
| Trace data supports the method | 405,229 spans, 24,812 traces, 9 bad parent refs out of 405k, no cross-trace corruption |
| Faults are measurably real | checkout delay → 51× median latency increase |
| Faults are repeatable | 3 reps: median ratios 50.972 / 50.992 / 51.088, **σ = 0.062** — this is an unusually clean reliability result, put it in the paper |
| Thresholds are calibrated, not arbitrary | baseline variability → threshold → detection |
| Data anomalies are caught, not silently absorbed | CPU case 2 truncated at 38.56 s vs ~720 s |
| Bugs are caught before contaminating results | the P > 1 dedup bug |
| Greedy machinery is correct | submodularity check: 6 checks, 0 violations |

And methodologically, the discipline in §44 of your note ("do not modify BLAST until it beats the baseline") is the single most valuable thing in the document. Keep that.

---

## 3. The plan

Four weeks to a real Gate 4 answer. Each step has a concrete deliverable and a gate.

### STEP 1 — Diagnose the saturation empirically *(half day)*

Do not act on my hypothesis. Test it.

**Script:** `diagnose_saturation.py`

For each of the 6 pilot cases, print:
- which services were flagged `impaired = True`, with their impairment scores
- for each impaired service, which capabilities it maps to
- the resulting union, and which service contributed each capability

**What you're looking for:** is `frontendservice` flagged impaired in all/most cases, and does it alone account for most of the 9 capabilities?

**Gate 1a.**
- *Confirmed (frontend amplifies)* → proceed to Step 2, attribution rework.
- *Refuted (capability sets genuinely differ per service but still union to 9)* → the problem is the capability model being too coarse (9 capabilities over 7 services is nearly 1:1). Then Step 2 changes shape: you need finer capabilities, not finer attribution. Come back and re-plan.

---

### STEP 2 — Rebuild attribution at operation/journey level *(3–4 days)* ← the critical fix

This returns to what ADR-002 originally specified. The pilot substituted *service-level latency impairment* for *journey-level outcome measurement*. That substitution is the root of the saturation.

**Why journeys fix it structurally:** a journey is an end-to-end request with an entry operation. `PlaceOrder` journeys degrading tells you *Order Placement* is impaired — directly, with no service→capability guessing step. A checkout fault degrades `PlaceOrder` and `Charge` journeys but leaves `GetAds` and `ListRecommendations` journeys untouched. Capability footprints differentiate **by construction**.

**Script:** `build_journey_impairment.py`

Per case:

1. **Extract journeys.** Group spans by `traceID`; identify the root span (`parentSpanID` null/missing — you have 24,810 of these). Journey type = root span's `operationName` (fall back to `serviceName::operationName` if operation names collide across services).
2. **Split windows** on `inject_time.txt`: baseline (~720 s before) vs fault (~720 s after). Flag short windows — CPU case 2 has only 38.56 s and must be excluded or down-weighted.
3. **Classify each journey instance:**
   - `failed` — any span in the trace carries a non-OK `statusCode`
   - `degraded` — total root-span duration > baseline p99 **for that journey type**
   - `success` — otherwise
4. **Per journey type, compute** `n_total`, `n_failed`, `n_degraded`, p50/p95/p99, throughput, for each window.
5. **Test significance per journey type**, do not use a bare ratio. Mann–Whitney U on the duration distributions plus a proportion test on failure rate. Use the baseline-variability work you already did to set effect thresholds. Correct across journey types (Holm).
6. **Emit** `journey_impairment.csv`: `case, fault_type, target_service, journey_type, n_baseline, n_fault, fail_rate_delta, degraded_rate_delta, p95_ratio, p_value, effect_size, impaired (bool), impairment_magnitude (continuous)`

**Then rewrite the overlay as operation→capability**, which your note already sketched (§20). Keep it declarative YAML, versioned, per ADR-002 and the sensitivity requirement:

```yaml
version: 2
system: online-boutique
value_model: revenue_weighted
capabilities:
  - id: order_placement
    display: "Order Placement"
    value_per_min: 100.0        # relative units, never currency
    realised_by: [PlaceOrder]
  - id: payment_processing
    value_per_min: 100.0
    realised_by: [Charge]
  - id: product_browsing
    value_per_min: 20.0
    realised_by: [GetProduct, ListProducts]
  - id: advertisement_retrieval
    value_per_min: 5.0
    realised_by: [GetAds]
  # ... 9 total
```

**Critical detail — the amplifier problem returns if you're careless.** If `frontendservice` emits a root span for every user request, then *every* journey type is a frontend journey and you're back where you started. Mitigation: key journey type on the **operation**, never the service; and if the frontend wraps everything in one generic root operation (e.g. `HTTP GET`), fall back to the **deepest distinguishing operation** in the trace — the RPC method that identifies what the request was actually doing. Step 1's diagnostic output will tell you which situation you're in. Decide this explicitly and write it up; it is a methodological choice a reviewer will ask about.

**Deliverable:** `journey_impairment.csv`, `business_overlay/online_boutique_v2.yaml`, a short note on the journey-typing rule and why.

---

### STEP 3 — Re-run the 6-case pilot with the new attribution *(half day)*

Same 6 cases. Same everything else. Only attribution changed.

**Gate 2a — the differentiation gate.**

| Outcome | Meaning | Action |
|---|---|---|
| Capability footprints now **differ** across the 6 incidents, no incident covers 9/9 | Attribution was the bug. Fixed. | Proceed to Step 4 |
| Footprints still saturate | Deeper problem — likely the frontend root-span issue above, or the capability model is too coarse for 5 target services | **Stop and re-plan.** Do not expand the dataset. |

Cheap gate, huge information. This is why it comes before the 90-case download.

---

### STEP 3.5 — Propagation prevalence audit *(half day, run alongside Step 3)*

**Script:** `audit_propagation_prevalence.py`

Across every case you have: what fraction of (fault, downstream-edge) pairs show **any** statistically significant downstream impairment? Break down by fault type — your pilot suggests CPU propagates and delay does not, and that distinction is itself a finding.

**Record the answer in the decision log regardless of what it is.** It determines whether the propagation half of the contribution is load-bearing or secondary, and you want that decided on evidence in week 2, not vibes in week 20.

---

### STEP 4 — Expand to the full RE2-OB corpus *(3–4 days)*

Now the expansion is worth doing.

1. **Enumerate first.** List actual case directories. Confirm the 5 target services and 6 fault types. Do not plan against an assumed service list.
2. **Batch pipeline:** download → distill journeys → **delete raw traces** → checkpoint per case, crash-resumable (ADR-004). You already have `download_delay_repetitions.py` to generalise.
3. **Track exclusions explicitly.** CPU case 2 is truncated; there will be others. Emit `excluded_cases.csv` with reasons. This becomes a threats-to-validity paragraph and it is much better to have it as data than as memory.
4. **Freeze the train/test split** (ADR-012) — stratified by service and fault type, **before** any probability fitting. Split at the (service, fault) level, not the case level, or repetitions of the same incident leak across the boundary.

**Gate 3a:** ≥60 usable cases spanning ≥4 distinct services and ≥3 fault types, with capability footprints that vary across incidents.

---

### STEP 5 — Probabilistic weighted objective + independent ground truth *(3–4 days)*

Two separate things. Keeping them separate is what makes the evaluation honest.

**5a. The model's objective** — replace binary coverage with the probabilistic form from your §38:

```
F(S) = Σ_c  w_c · P(c impaired | S)
```

where `P(c impaired | S) = 1 − Π_{i∈S} (1 − p(c | i))` under independent activation, and `p(c | i)` comes from your Beta posterior across repetitions.

Two notes:
- **Submodularity survives.** This is weighted probabilistic coverage under independent activation — the standard KKT setting. Your empirical check should still show 0 violations; keep running it as a regression test.
- **Weights `w_c` must stop being all-1.** Uniform weights are a large part of why everything ties. Use overlay v2's `value_per_min`, and run the ≥5-model sensitivity sweep (`03_RESEARCH_DESIGN.md` A6) — including a uniform model as one of the five, so you can *show* what uniform weighting does rather than accidentally living in it.

**5b. Ground truth** — computed from measured journey impairment, **never from `F(S)`**:

```
GT_loss(i) = Σ_c  w_c · measured_impairment_magnitude(c | i)
```

using the continuous magnitude from Step 2, not the binary flag. Then:

- **Scenario synthesis:** sample k ∈ {3, 5, 10} incidents from *distinct* (service, fault) combinations. Union semantics for composition (TV-2). Generate ≥30 scenarios per k for statistical power.
- **Ground-truth ordering:** rank by `GT_loss` under sequential repair — the incident whose repair recovers the most unrecovered business value first. This must be computed with a plain, model-free rule so it is defensible as an oracle.

---

### STEP 6 — The real Gate 4 experiment *(3–4 days)*

**Metrics** (from `03_RESEARCH_DESIGN.md` §6):

- **Primary:** Cumulative Business Loss and Area Under the Loss Curve, normalised against oracle and random orderings
- **Secondary:** NDCG@{1,3,5}, Kendall's τ vs ground-truth order, MRR
- **Sanity check only:** coverage@K (label it as such in the paper)

**Baselines** (implement in this order — cheap to expensive):
B1 random · B2 severity (impairment magnitude, no graph) · B4 PageRank · B6 personalized PageRank from incident nodes · **B9 BLAST-independent** ← the ablation-as-baseline that isolates set selection · B3 ITIL matrix · B7 AlertRank-style classifier

**Statistics:** ≥30 scenarios per configuration, Wilcoxon signed-rank, Cliff's delta, Holm–Bonferroni. Seeds fixed and logged.

**Gate 4 — the real one.**

| Outcome | Read | Action |
|---|---|---|
| BLAST beats B9 on CBL/AULC, significant, survives ≥4 of 5 value models | Central claim supported | Proceed: multi-hop, ablations, cross-system, paper |
| BLAST ≈ B9 | Set-selection adds nothing **on this benchmark** | Execute the pivot below. Do not tune to win. |
| BLAST worse | Bug, or the objective is misaligned with ground truth | Debug before interpreting |

---

## 4. The pivot, pre-committed

Write this down now so the decision is made while you're calm.

If Gate 4 ties **after** attribution is fixed and the dataset is expanded, the honest finding is:

> On RCAEval's injected-fault benchmark, incidents exhibit sufficiently overlapping business-capability footprints that set-selection provides no measurable advantage over independent scoring. We characterise the conditions — capability-footprint heterogeneity and propagation prevalence — under which the submodular formulation would and would not pay off.

That reframes the paper as **an empirical study with a negative result plus a characterisation**, which is publishable at workshops and in empirical-SE venues, and is far stronger than a tuned positive result. Pair it with:

- The **propagation prevalence** finding from Step 3.5 — a real contribution about benchmark realism, with existing literature to cite alongside.
- A **synthetic-topology study**: generate graphs with controlled capability-footprint overlap and show *where* the crossover lies — at what heterogeneity level does submodular selection start winning? This turns "it didn't work" into "here is exactly when it works," which is a genuine contribution and cheap to run since it needs no new data.

Then supersede ADR-011 and update the positioning statement.

---

## 5. Ordered task list

| # | Task | Days | Gate |
|---|---|---|---|
| 1 | `diagnose_saturation.py` — test the frontend-amplifier hypothesis | 0.5 | **1a** |
| 2 | `build_journey_impairment.py` — journey extraction, outcome classification, significance testing | 3–4 | — |
| 3 | `business_overlay/online_boutique_v2.yaml` — operation→capability, non-uniform weights | 0.5 | — |
| 4 | Re-run 6-case pilot with new attribution | 0.5 | **2a** ← cheap, decisive |
| 5 | `audit_propagation_prevalence.py` | 0.5 | record in ADR |
| 6 | Enumerate RE2-OB cases; confirm actual services/faults | 0.5 | — |
| 7 | Batch download + distill, resumable, `excluded_cases.csv` | 3 | **3a** |
| 8 | Freeze train/test split at (service, fault) level | 0.5 | — |
| 9 | Probabilistic weighted `F(S)`; re-run submodularity check | 2 | — |
| 10 | Ground-truth loss + scenario synthesis (≥30 per k) | 2 | — |
| 11 | Baselines B1, B2, B4, B6, B9 | 2 | — |
| 12 | Evaluation harness: CBL/AULC, NDCG, τ, stats, LaTeX output | 2 | — |
| 13 | **Gate 4 decision** | 0.5 | **4** |

**≈ 18–20 working days.** Tasks 1–4 are ~5 days and answer the most important open question, so front-load them.

---

## 6. Do not do these

Carrying forward your own §44, plus additions from this review:

- ❌ Expand the dataset before Gate 2a passes — 90 saturated incidents are worth no more than 6
- ❌ Evaluate on coverage@K as a headline metric — it is BLAST's own objective
- ❌ Keep `w_c = 1` — uniform weights are part of why everything ties
- ❌ Tune BLAST until it beats the baseline
- ❌ Invent revenue numbers, or write `$` anywhere
- ❌ Treat 3 repetitions as statistically strong
- ❌ Add GNNs or RL (ADR-005, ADR-006)
- ❌ Build the dashboard yet (ADR-008)
- ❌ Split train/test at case level — repetitions leak

---

## 7. ADRs to write this week

| Proposed | Subject |
|---|---|
| **ADR-014** | Journey/operation-level impairment attribution supersedes service-level (supersedes the pilot's implicit choice; restores ADR-002 as designed) |
| **ADR-015** | Journey-typing rule — keyed on operation, with the deepest-distinguishing-operation fallback, and why |
| **ADR-016** | Probabilistic weighted objective replaces binary coverage; submodularity preserved under independent activation |
| **ADR-017** | Evaluation uses ground truth derived independently of `F(S)`; coverage@K demoted to sanity check |
| **ADR-018** | Propagation prevalence finding and its consequence for the contribution's framing *(write after Step 3.5)* |
| **ADR-019** | RE2-OB scope: 90 cases, 5 target services, 30 distinct incident types; cross-system expansion decision |

---

## Sources

- [RCAEval GitHub — dataset structure](https://github.com/phamquiluan/RCAEval)
- [RCAEval paper](https://arxiv.org/html/2412.17015v5)
- [RCAEval on Zenodo](https://zenodo.org/records/14590730)
- [Rethinking the Evaluation of Microservice RCA with a Fault Propagation-Aware Benchmark](https://arxiv.org/html/2510.04711v2)
- [An Empirical Study of SOTA RCA Models: From Oversimplified Benchmarks to Realistic Failures](https://www.researchgate.net/publication/396250746_An_Empirical_Study_of_SOTA_RCA_Models_From_Oversimplified_Benchmarks_to_Realistic_Failures)
