# 06 — Bootstrap Prompts for Claude Code

Paste-ready prompts for resuming work. Claude Code reads `CLAUDE.md` automatically from the repo root, so you usually don't need to re-explain the project — but the first prompt of a session should still point at `context/`.

---

## CURRENT PHASE — start here (post-pilot)

```
Read CLAUDE.md and context/07_NEXT_PHASE_PLAN.md.

We are post-pilot. The pilot returned BLAST - baseline = 0 at every K because
incident 1 covered 9/9 capabilities. 07 argues this is an ATTRIBUTION bug
(frontendservice maps to every capability), not just dataset homogeneity.

Start with Step 1: write diagnose_saturation.py. For each of the 6 pilot cases,
print which services were flagged impaired, which capabilities each maps to, and
which service contributed each capability to the union.

Do not assume the hypothesis is right — test it and report what the data says.
That is Gate 1a.
```

---

## Step 2 — the critical fix

```
Gate 1a passed. Implement Step 2 of context/07_NEXT_PHASE_PLAN.md:
build_journey_impairment.py.

Rebuild impairment at journey/operation level instead of service level:
  - group spans by traceID, find root spans (no parentSpanID)
  - journey type = root span operationName
  - split on inject_time.txt into baseline (~720s) vs fault (~720s) windows
  - classify each journey: failed (any error statusCode) / degraded (> baseline
    p99 for that journey type) / success
  - per journey type, test significance: Mann-Whitney U on durations + proportion
    test on failure rate, Holm-corrected across journey types
  - emit journey_impairment.csv with a CONTINUOUS impairment_magnitude, not just
    a boolean

Watch for the amplifier trap: if frontendservice emits a generic root span for
every request, journey types won't differentiate. Check this first and tell me
which situation we're in before building the full pipeline.
```

---

## Step 4 — Gate 2a, the cheap decisive check

```
Re-run the 6-case pilot with journey-level attribution. Everything else identical.

Report the capability footprint of each of the 6 incidents.

Gate 2a passes if footprints now DIFFER and no single incident covers 9/9.
If they still saturate, STOP. Do not expand the dataset — tell me and we re-plan.
```

---

## Step 3.5 — propagation prevalence audit

```
Write audit_propagation_prevalence.py per context/07_NEXT_PHASE_PLAN.md Step 3.5.

Across all available cases: what fraction of (fault, downstream-edge) pairs show
statistically significant downstream impairment? Break down by fault type.

The pilot hints CPU propagates (checkout->payment 2/3) but delay propagates to
nothing (0/3 on every edge). If low propagation generalises, the structural half
of BLAST's contribution needs reframing — so report the number honestly whatever
it is. This becomes ADR-018.
```

---

## Cold start (orienting a fresh session)

```
Read CLAUDE.md, context/07_NEXT_PHASE_PLAN.md, and context/README.md.

This is my final-year research project. The pilot is done; we're at the
start of the real experimental phase.

Give me a short summary of: (a) the core research claim, (b) what the pilot
established, (c) why the pilot's null result happened, and (d) the next
gate. Then stop and wait — don't start implementing.
```

---

# Historical prompts (phases already completed)

*Kept for reference. Gates 0 and 1 have passed — don't re-run these.*

## ~~Gate 0 — validate the ground-truth strategy~~ ✅ PASSED

```
We're at Gate 0 in context/00_MASTER_PLAN.md. This gate decides whether
the entire ground-truth strategy (ADR-002) is viable.

Task: help me download ONE RCAEval fault case from Online Boutique RE2
and inspect its trace format.

I need to confirm the traces contain:
  - parent-child span relationships (span_id + parent_span_id)
  - service name per span
  - operation/endpoint name per span
  - error status per span
  - duration per span

Write a small throwaway inspection script. Report what's actually in the
data — do NOT assume the format. If any of the five fields is missing,
say so plainly: that's a Gate 0 failure and we need to pivot to
metric-based impairment proxies.

Also measure the on-disk size of this single case so we can extrapolate
for Gate 1.
```

---

## Phase 0 — repo skeleton

```
Set up the repo skeleton per context/02_ARCHITECTURE.md §4.

- uv for env management, Python 3.11+, pinned lockfile
- src/blast/ package with empty module stubs matching M1-M10
- The three frozen dataclasses from CLAUDE.md in src/blast/types.py
- pytest + a trivial passing test
- .gitignore covering data/ and results/
- config/experiment.yaml stub

Don't implement logic yet — structure only. Then show me the tree.
```

---

## Phase 1 — ingest module

```
Implement M1 (blast.ingest) per context/02_ARCHITECTURE.md §3.

Fetch and verify RCAEval archives, normalise per-case directory layout,
emit a manifest with checksums. Keep it dumb — no scientific logic here.

Constraint reminder: 16GB RAM laptop, disk is the binding constraint.
```

---

## Phase 2 — the critical path

```
Implement M2 (blast.traces) per context/02_ARCHITECTURE.md §3.

This is the project's critical path and highest-risk module. Requirements:
  - Streaming (never load a full system's traces into memory)
  - One fault case at a time
  - Checkpoint after each case; crash-resumable
  - Delete raw traces immediately after distilling a case (ADR-004)
  - Output the frozen journeys.parquet schema

Journey = one root span + its full span tree.
Journey type = keyed by entry endpoint.
Outcome = success | failed (any error span) | degraded (> baseline p99).

Before writing code, restate the journey-summary schema back to me and
flag any field we should over-collect now — re-deriving a discarded
field means re-downloading (ADR-004 consequence).
```

---

## Phase 2 — Gate 2 validation

```
We're at Gate 2 — the most important gate in the project.

Using RCAEval's annotated root-cause service per fault case as an oracle:
for each distilled case, check whether the impaired journeys actually
touch the known faulty service.

Report:
  - % of cases where measured journey impairment is non-trivial
  - % where impaired services are consistent with the annotated root cause
  - the distribution of impact magnitude

Gate passes at >=80% on both. If fewer than ~50 cases show measurable
impact, that's the kill criterion — tell me straight rather than
massaging it.
```

---

## Phase 4 — Gate 4, the decisive experiment

```
Run ablation A4 from context/03_RESEARCH_DESIGN.md §7 on a preliminary
scenario set: greedy submodular ordering vs independent per-incident
scoring, on scenarios with overlapping blast radii.

This is Gate 4 and it tests ADR-011, the paper's central claim. Run it
now rather than at the end, per the master plan.

If submodular ordering does NOT beat independent scoring, say so
directly. The documented pivot is to fall back to the RQ1+RQ2
contribution (learned-transmission business graph model) and supersede
ADR-011. Don't soften a negative result.
```

---

## Adding an ADR

```
I want to <change>. Per rule 4 in CLAUDE.md, write the ADR first.

Use the template at the bottom of context/01_DECISION_LOG.md. Be honest
in "Alternatives rejected" — and if this change is actually scope creep
per the "Known temptations" table in CLAUDE.md, tell me that instead of
writing the ADR.
```

---

## Literature check-in (monthly)

```
Search arXiv and DBLP for work published since the last check on:
  - microservice incident prioritization
  - business impact AIOps
  - alert ranking with dependency graphs
  - blast radius estimation

Flag anything that overlaps ADR-011's framing (submodular / set-selection
for incident triage). Update context/04_LITERATURE_GAP.md with anything
relevant, keeping the [VERIFIED]/[VERIFY] tagging convention.
```

---

## Paper writing

```
Draft Section <N> of the paper per the outline in
context/03_RESEARCH_DESIGN.md §10.

Rules:
  - Every citation tagged [VERIFY] until confirmed on DBLP
  - Business values are relative units, never currency
  - No claim of reduced MTTR — CBL is a proxy and must be labelled one
  - Threats to validity from §8 stated plainly, not buried

Use the positioning statement in context/04_LITERATURE_GAP.md §4 for
related work.
```

---

## Reality check (use when something feels off)

```
Review the current state of the project against context/00_MASTER_PLAN.md.

Tell me honestly:
  - Which phase are we actually in vs. where the plan says we should be?
  - Has any scope crept in without an ADR? Check the "Known temptations"
    table in CLAUDE.md.
  - Is anything in the "never cut" list at risk?
  - What's the single biggest threat to finishing right now?

Be blunt. I'd rather hear it now than in week 22.
```
