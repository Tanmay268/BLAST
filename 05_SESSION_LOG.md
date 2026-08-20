# 05 — Origin & Session Log

**Purpose:** how this plan was derived, what the user decided, and what was verified vs. assumed. Read this to understand *why* the other documents say what they say.

**Session date:** 2026-08-17
**Participants:** Tanmay (owner) · Claude (Cowork session)

---

## 1. Starting point

Tanmay uploaded `PROJECT_CONTEXT.pdf` (14 pages, preserved at `context/source/`) describing a final-year Software Engineering research project:

> *Business-Impact Aware Incident Prioritization for Microservice Systems using Dependency Graph Intelligence*

Stated goals: publish a paper, build a working prototype, demonstrate novelty over existing AIOps, solve a real DevOps/SRE problem. The brief proposed a wide surface area — GNNs, GATs, GraphSAGE, graph transformers, reinforcement learning, learning-to-rank, ten node types, ~20 node attributes, five research questions, and a full dashboard.

The request: a complete step-by-step structured plan, with every decision documented, written with an eventual research paper in mind. Explicitly: **ask questions before writing a single line of code.**

---

## 2. The problem identified before planning began

> **Every metric in the brief (NDCG, MRR, MAP, Precision@K) requires a ranked ground truth of incident priority. No public microservice dataset contains one.**

RCAEval — the field's standard benchmark — provides annotated *root causes*, not *priorities*. Without solving this, the system is unevaluable and the paper is not publishable. This became the central design constraint and is addressed in `03_RESEARCH_DESIGN.md` §3 and ADR-002.

---

## 3. Decisions the user made

Four questions were asked. Answers:

| Question | Answer | Consequence |
|---|---|---|
| **Ground truth strategy** | Measured simulation + small human study | ADR-002; drives Phase 2 and Phase 6 |
| **Compute available** | **Local machine only — 16 GB RAM, no GPU.** No Kubernetes cluster, no cloud credits | ADR-003, ADR-004; forced the offline-batch redesign |
| **Timeline / venue** | Flexible — university deadline is what matters | 26-week plan with a documented compressed variant |
| **Scope** | Cut to a defensible core; document what was cut and why | ADR-005 through ADR-010; the whole decision-log approach |

### 3.1 The conflict this created, and how it was resolved

The user chose *measured* ground truth but has **no cluster** — so the originally-framed plan (run the app, inject faults, measure revenue loss live) was unavailable.

**Resolution — and it is methodologically stronger than the original:**

> RCAEval's authors already ran that experiment. They injected 735 real faults into three real microservice systems and **released the distributed traces**. A distributed trace is a record of an actual end-to-end user request. So business impact is **directly measurable, offline, on a laptop** — by counting how many end-to-end journeys failed or degraded during each real fault window versus the fault-free baseline.

The failure is real and was really measured. Only the *monetary valuation* is overlaid, and that overlay is declared, versioned, released as an artifact, and stress-tested across five value models. This cleanly separates *what was observed* from *what was assumed*.

---

## 4. What was verified in-session vs. assumed

### Verified
- **RCAEval** exists and is the field's benchmark (FSE'26 / WWW'25 / ASE'24). Contains Online Boutique (12 services), Sock Shop (15), Train Ticket (64). 735 failure cases, 11 fault types, split RE1 (375, metric-only), RE2 (270, multi-source), RE3 (90, code-level faults). Releases metrics, logs, and traces. Provides annotated root-cause service and indicator. Trace volumes 4.5–76.7M per system; logs 1.7–26.9M lines. **Total size in GB is not stated in the paper** — this is why Gate 1 exists.
- **AlertRank** (ISSRE 2020) exists — the closest prior work on prioritization.
- **Surveys** confirming prioritization is a recognised, under-served research problem: JNCA 2024 (vol. 224, 103842) and ACM Computing Surveys 2024 on SOC alert prioritisation.
- **Kempe, Kleinberg & Tardos** (KDD 2003) — independent cascade, submodularity, greedy (1−1/e). The theoretical backbone.
- **Novelty check: clean.** Searches for submodular / influence-maximization approaches to incident triage returned only the generic theory papers and practitioner ITSM content. Nobody has applied this framing to microservice incident prioritization.

### NOT verified — must be checked in week 1
- **TrioXpert** and **ART** — named as baselines in the original brief. Could not confirm either as peer-reviewed, code-released *prioritization* systems. If they only do localization, comparing against them is a category error. **Gate 0 task.**
- Venue/year for Eadro, DiagFusion, MicroRank, Groot, Sage, Nezha, Chain-of-Event, Nemhauser et al. — all marked `[VERIFY]` in `04_LITERATURE_GAP.md`. Confirm on DBLP before any enters the paper.
- Whether RCAEval traces contain the parent-child span structure the method requires. **This is Gate 0 and everything depends on it.**

---

## 5. The reframing (the single most important thing in this document)

The brief proposed a **weighted-sum priority score** over seven factors with learned weights. Assessment: this is essentially AlertRank plus graph features — an incremental delta, difficult to publish.

**Replaced with (ADR-011):**

> Incident prioritization is a **set-selection** problem, not a scoring problem. If incidents A and B both take down checkout, fixing either restores it — so loss({A,B}) ≠ loss(A) + loss(B). **Every existing method double-counts overlapping blast radii.** Framed as expected business-capability coverage under an independent-cascade propagation model, the objective is monotone submodular, and greedy ordering admits a (1−1/e) approximation guarantee.

Three reasons this is stronger: it is genuinely unaddressed; it borrows mature, citable theory rather than inventing mathematics; and it yields a *theorem*, which materially separates a research contribution from an engineering report.

**Standing caveat.** The (1−1/e) guarantee applies cleanly to influence maximization. BLAST's objective is an *ordering under a repair budget*, which is closer to min-sum weighted completion time with submodular value — **not literally the same problem.** The proof must be derived (Phase 5, task 5.9). If it fails, report greedy as a well-motivated heuristic and lean on ablation A4. **Do not claim an unproven theorem.**

---

## 6. Where the plan deliberately contradicts the brief

| Brief proposed | Plan decided | ADR |
|---|---|---|
| GNN/GAT/graph transformer as the novel core | Interpretable probabilistic propagation as core; GAT demoted to **baseline B8** | ADR-005 |
| Reinforcement learning | Excluded entirely | ADR-006 |
| 10 node types, ~20 attributes | 4 node types, 4 edge types | ADR-007 |
| 5 RQs incl. "reduce incident response time" | 4 RQs; response time → Cumulative Business Loss proxy | ADR-010 |
| TrioXpert / ART as baselines | Conditional on week-1 verification | §4 above |
| Weighted-sum priority score | Submodular set selection | ADR-011 |

None of the brief's ten **deliverables** were dropped — see `00_MASTER_PLAN.md` §3.

---

## 7. Reasoning available for reuse

Useful framings established here, worth reusing in the paper:

- **"Topological importance is not failure importance."** PageRank-style centrality assumes failure flows equally along every edge. Real systems have retries, timeouts, circuit breakers, cache fallbacks, async queues — **some edges transmit failure, some absorb it.** This motivates learning per-edge transmission probability and is the core of RQ2.
- **The value model is a contribution, not just a weakness.** Framing the business overlay as a released, versioned, sensitivity-tested artifact converts the project's biggest vulnerability into *"the first business-overlay specification and sensitivity methodology for impact-aware incident evaluation."*
- **Gate placement is a risk-management tool.** Ablation A4 runs at week ~14, not week ~22, specifically so that a failed central claim leaves time to pivot to the RQ1+RQ2 contribution.
- **State limitations before a reviewer does.** The threats-to-validity section (`03_RESEARCH_DESIGN.md` §8) was drafted at planning time, not after results.

---

## 8. Open questions for the supervisor

1. Is ADR-011 (submodular set-selection framing) the right bet? This is the decision the whole paper rests on.
2. Does the institution require ethics/IRB approval for an anonymous practitioner survey? (4–8 week lead time.)
3. Target venue — affects rigor level and how aggressively to compress the plan.
4. Is a single-author submission expected, or co-authored with the supervisor?
5. Is the trace-derived + declared-overlay ground truth (ADR-002) acceptable to them, or do they expect live measurement?
