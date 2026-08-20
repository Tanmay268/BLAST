# BLAST — Context Folder

**Final-year research project · Tanmay · VIT Vellore**
Generated 2026-08-17. This folder is the complete context for the project. `../CLAUDE.md` points here.

> **Problem.** Microservice AIOps tells you *what broke and where*. It does not tell you *what to fix first*.
> **Contribution.** Frame incident prioritization as **greedy submodular coverage of business capabilities under stochastic failure propagation**, over a business-dependency graph with **learned per-edge failure-transmission probabilities**.
> **Why it's novel.** Every existing method scores incidents independently, and therefore double-counts overlapping blast radii. Prioritization is a *set-selection* problem, not a scoring problem.

---

## Contents

| File | What it's for | Read when |
|---|---|---|
| **[07_NEXT_PHASE_PLAN.md](07_NEXT_PHASE_PLAN.md)** | **Post-pilot plan — authoritative for the next ~4 weeks.** Diagnoses the pilot null result, corrects the task order, sets Gates 1a/2a/3a/4 | **Start here now.** Supersedes the Phase 2-4 ordering in the master plan. |
| **[00_MASTER_PLAN.md](00_MASTER_PLAN.md)** | Six phases, gates, risk register | Overall arc. Re-read at every phase boundary. |
| **[03_RESEARCH_DESIGN.md](03_RESEARCH_DESIGN.md)** | RQs, formal model, **ground truth methodology**, baselines, metrics, ablations, threats to validity | Before any implementation. §3 is the most important section in the whole set. |
| **[02_ARCHITECTURE.md](02_ARCHITECTURE.md)** | Pipeline, 10 modules, interfaces, repo layout, resource budget | Before writing code. |
| **[01_DECISION_LOG.md](01_DECISION_LOG.md)** | 13 ADRs — every decision, its rationale, what was rejected and why | When you wonder "why did we do it this way?" or want to change something. |
| **[04_LITERATURE_GAP.md](04_LITERATURE_GAP.md)** | Related-work map, the gap, paste-ready positioning statement, reading list | Week 1, and monthly thereafter. |
| **[05_SESSION_LOG.md](05_SESSION_LOG.md)** | How this plan was derived; stated constraints; what was verified vs assumed; open questions for the supervisor | To understand *why* the other docs say what they say. |
| **[06_BOOTSTRAP_PROMPTS.md](06_BOOTSTRAP_PROMPTS.md)** | Paste-ready prompts for Claude Code sessions | Every time you start a session. |
| **[source/PROJECT_CONTEXT.pdf](source/PROJECT_CONTEXT.pdf)** | The original 14-page project brief | Reference. |

Also: **[../CLAUDE.md](../CLAUDE.md)** — repo-root instructions Claude Code loads automatically. Hard rules, tech stack, frozen interfaces, current position, and the "known temptations" list.

---

## Status — post-pilot (2026-08-17)

**Gate 0 PASSED** — traces validated: 405,229 spans, 24,812 traces, 9 bad parent refs, no cross-trace corruption.
**Gate 1 PASSED** — data pipeline works end to end; faults measurable (checkout delay = 51x median latency) and repeatable (sigma = 0.062 over 3 reps).
**Gate 4 attempted → diagnostic null result.** BLAST - baseline = 0 at every K, because incident 1 covered 9/9 capabilities.

**Diagnosis:** this is an **attribution bug**, not merely dataset homogeneity. Service-level
attribution routes every incident through `frontendservice`, which maps to all 9 capabilities.
The fix is journey/operation-level attribution — which is what ADR-002 originally specified.
Full analysis and the corrected plan: **[07_NEXT_PHASE_PLAN.md](07_NEXT_PHASE_PLAN.md)**.

**Verified dataset ceiling:** RE2-OB = 6 fault types x 5 services x 3 reps = 90 cases, i.e. only
**30 distinct (service, fault) incident types**.

## The three things most likely to kill this project

1. ~~Ground truth viability~~ → **resolved at Gate 0**, but the *independent* ground-truth
   computation (measured journey loss, not `F(S)`) still has to be built. See 07 Step 5.
2. **Attribution saturation.** Currently blocking the central experiment. See 07 Steps 1-3.
3. **Propagation may be rare.** Pilot hints delay faults propagate to nothing. If that
   generalises, the structural half of the contribution needs reframing — decided on evidence
   at 07 Step 3.5, not in week 20.

---

## Four places this plan deliberately contradicts the original brief

Each has an ADR with full reasoning. Summarised so the disagreements are visible up front:

| Brief proposed | Plan says | ADR |
|---|---|---|
| GNN / GAT / graph transformer as the novel core | **Interpretable probabilistic propagation as the core; GAT demoted to a baseline.** A GNN on a 12-node graph with ~270 cases overfits and isn't novel in 2026. If BLAST beats the GAT, that's a *result*. | ADR-005 |
| Reinforcement learning for weight tuning | **Excluded.** No environment, no reward signal, no data. High risk, low payoff. | ADR-006 |
| 10 node types, ~20 node attributes | **4 node types.** You can only include what data can populate — teams, MTTR, recovery cost and revenue aren't in any available dataset. Including them means inventing values. | ADR-007 |
| 5 RQs including "reduce incident response time" | **4 RQs.** Response-time reduction needs a longitudinal production deployment. Claiming it from simulation is an overclaim reviewers punish. | ADR-010 |

Nothing from the brief's *deliverables* list was dropped — see `00_MASTER_PLAN.md` §3.

---

## Do these things this week

Full detail in **[07_NEXT_PHASE_PLAN.md](07_NEXT_PHASE_PLAN.md)** §5. In order — the first four are cheap and decisive:

1. `diagnose_saturation.py` — test the frontend-amplifier hypothesis empirically. **Gate 1a.**
2. `build_journey_impairment.py` — rebuild attribution at journey/operation level. The critical fix.
3. `business_overlay/online_boutique_v2.yaml` — operation→capability, **non-uniform** weights.
4. Re-run the 6-case pilot. **Gate 2a** — do footprints now differ? If they still saturate, stop and re-plan.
5. `audit_propagation_prevalence.py` — how often do faults propagate at all?

Still outstanding from Phase 0, unrelated to the above:

- Verify **TrioXpert** and **ART** exist as citable, code-released prioritization systems.
- **Ethics/IRB** enquiry for the human study — 4–8 week lead time, silently blocks Phase 6.
- Read **AlertRank (ISSRE 2020)** end to end.

Do #1 first. Do **not** expand the dataset before Gate 2a passes.

---

## Using this with Claude Code

```bash
cd "D:\Downloads\PROJECTS\Project 1"
claude
```

`CLAUDE.md` loads automatically. Then paste the cold-start prompt from `06_BOOTSTRAP_PROMPTS.md`.
