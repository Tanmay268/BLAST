import pandas as pd
import numpy as np
import yaml
from pathlib import Path


# ======================================================
# BLAST — RE-RUN 6-CASE PILOT WITH JOURNEY-LEVEL ATTRIBUTION
# ======================================================
#
# context/07_NEXT_PHASE_PLAN.md Step 4 -- GATE 2a.
#
# Same 6 cases, same greedy/baseline coverage machinery as
# run_blast_greedy.py. Only the attribution changed:
# incidents' capability sets now come from
# journey_impairment.csv (ADR-014/015) and
# business_overlay/online_boutique_v2.yaml, instead of the
# service-level business_capabilities.csv.
#
# Outputs are written to *_v2 filenames. The original
# service-level pilot artifacts (incident_capability_matrix.csv,
# blast_greedy_results.csv, blast_vs_baseline.csv, ...) are
# NOT overwritten -- they are the documented null-result
# baseline this re-run is compared against.
#
# GATE 2a:
#   PASS  -> capability footprints differ across incidents,
#            no incident covers 9/9. Proceed to Step 4 of the
#            plan (expand to full RE2-OB).
#   FAIL  -> footprints still saturate. Stop and re-plan; do
#            not expand the dataset.
# ======================================================

JOURNEY_FILE = "results/data/journey_impairment.csv"
OVERLAY_FILE = "business_overlay/online_boutique_v2.yaml"

OUTPUT_MATRIX = "results/data/incident_capability_matrix_v2.csv"
OUTPUT_OVERLAP = "results/data/incident_capability_overlap_v2.csv"
OUTPUT_GREEDY = "results/data/blast_greedy_results_v2.csv"
OUTPUT_BASELINE = "results/data/independent_ranking_results_v2.csv"
OUTPUT_COMPARISON = "results/data/blast_vs_baseline_v2.csv"
OUTPUT_TRAJECTORY = "results/data/baseline_coverage_trajectory_v2.csv"

K_VALUES = [1, 2, 3, 4, 5, 6]

DOMINANCE_THRESHOLD = 0.7  # same definition as diagnose_saturation.py


# ======================================================
# LOAD JOURNEY IMPAIRMENT + OVERLAY
# ======================================================

print("=" * 110)
print("BLAST — PILOT RE-RUN WITH JOURNEY-LEVEL ATTRIBUTION (GATE 2a)")
print("=" * 110)

journeys = pd.read_csv(JOURNEY_FILE)

with open(OVERLAY_FILE, "r") as f:
    overlay = yaml.safe_load(f)

print(f"\nJourney impairment rows: {len(journeys)}")
print(f"Overlay: {overlay['system']} v{overlay['version']} ({overlay['value_model']})")

capabilities = overlay["capabilities"]
capability_ids = [c["id"] for c in capabilities]
capability_display = {c["id"]: c["display"] for c in capabilities}
capability_weight = {c["id"]: c["value_per_min"] for c in capabilities}

# operation (methodName) -> list of capability ids it realises
operation_to_capabilities = {}
for c in capabilities:
    for op in c["realised_by"]:
        operation_to_capabilities.setdefault(op, []).append(c["id"])

print(f"Capabilities: {len(capability_ids)}")
print(f"Operations mapped: {len(operation_to_capabilities)}")


# ======================================================
# BUILD INCIDENT x CAPABILITY MATRIX
# ======================================================
#
# An incident (case) covers a capability if ANY of its
# IMPAIRED journey types has an operation in its signature
# that realises that capability.
# ======================================================

journeys["signature"] = journeys["signature"].fillna("")

rows = []

for case, group in journeys.groupby("case"):

    fault_type = group["fault_type"].iloc[0]

    impaired_journeys = group[group["impaired"]]

    covered = set()
    contributing_journeys = {c: [] for c in capability_ids}

    for _, row in impaired_journeys.iterrows():

        ops = [o for o in row["signature"].split("+") if o]

        for op in ops:
            for cap_id in operation_to_capabilities.get(op, []):
                covered.add(cap_id)
                contributing_journeys[cap_id].append(row["journey_type"])

    record = {"incident_id": case, "fault_type": fault_type}

    for cap_id in capability_ids:
        record[capability_display[cap_id]] = int(cap_id in covered)

    rows.append(record)

matrix = pd.DataFrame(rows)

print("\n")
print("=" * 110)
print("INCIDENT x CAPABILITY MATRIX (JOURNEY-LEVEL)")
print("=" * 110)

pd.set_option("display.max_columns", None)
pd.set_option("display.width", 200)

print(matrix.to_string(index=False))

matrix.to_csv(OUTPUT_MATRIX, index=False)


# ======================================================
# JACCARD OVERLAP (same diagnostic as build_capability_impacts.py)
# ======================================================

capability_display_cols = [capability_display[c] for c in capability_ids]

sets = {}
for _, row in matrix.iterrows():
    incident = row["incident_id"]
    sets[incident] = {c for c in capability_display_cols if row[c] == 1}

overlap_rows = []
ids = list(sets.keys())

for i in range(len(ids)):
    for j in range(i + 1, len(ids)):
        a, b = ids[i], ids[j]
        A, B = sets[a], sets[b]
        union = A | B
        intersection = A & B
        jaccard = len(intersection) / len(union) if union else 0.0

        overlap_rows.append({
            "incident_a": a,
            "incident_b": b,
            "intersection_size": len(intersection),
            "union_size": len(union),
            "jaccard_overlap": jaccard,
            "overlapping_capabilities": ";".join(sorted(intersection)),
        })

overlap = pd.DataFrame(overlap_rows)

print("\n")
print("=" * 110)
print("INCIDENT CAPABILITY OVERLAP (JOURNEY-LEVEL)")
print("=" * 110)

print(
    overlap.sort_values("jaccard_overlap", ascending=False).to_string(index=False)
)

overlap.to_csv(OUTPUT_OVERLAP, index=False)


# ======================================================
# GATE 2a VERDICT
# ======================================================

universe_size = len(capability_ids)
coverage_counts = matrix[capability_display_cols].sum(axis=1)

n_saturated = int((coverage_counts == universe_size).sum())
mean_coverage_fraction = (coverage_counts / universe_size).mean()
mean_jaccard = overlap["jaccard_overlap"].mean() if len(overlap) else np.nan
max_jaccard = overlap["jaccard_overlap"].max() if len(overlap) else np.nan

print("\n")
print("=" * 110)
print("GATE 2a — DIFFERENTIATION CHECK")
print("=" * 110)

print(f"\nIncidents covering {universe_size}/{universe_size} capabilities: {n_saturated}/{len(matrix)}")
print(f"Mean coverage fraction: {mean_coverage_fraction:.1%}")
print(f"Mean pairwise Jaccard overlap: {mean_jaccard:.3f}")
print(f"Max pairwise Jaccard overlap: {max_jaccard:.3f}")

if n_saturated == 0:
    gate_2a = "PASS"
    print(f"\nVERDICT: {gate_2a}")
    print("No incident covers the full capability universe. Footprints differ.")
else:
    gate_2a = "FAIL"
    print(f"\nVERDICT: {gate_2a}")
    print(f"{n_saturated} incident(s) still cover the full capability universe.")

print(f"\nGate 2a result: {gate_2a}")


# ======================================================
# GREEDY BLAST VS INDEPENDENT BASELINE
# (same coverage@K machinery as run_blast_greedy.py --
#  internal sanity check only, per 07_NEXT_PHASE_PLAN.md
#  §1.3: coverage@K is BLAST's own objective, headline
#  metrics come from Step 5's ground truth.)
# ======================================================

weights = {capability_display[c]: capability_weight[c] for c in capability_ids}

incident_sets = {
    row["incident_id"]: {c for c in capability_display_cols if row[c] == 1}
    for _, row in matrix.iterrows()
}

all_incidents = list(incident_sets.keys())


def coverage_value(selected):
    covered = set()
    for incident in selected:
        covered.update(incident_sets[incident])
    return sum(weights[c] for c in covered)


def marginal_gain(incident, selected):
    return coverage_value(selected + [incident]) - coverage_value(selected)


print("\n")
print("=" * 110)
print("BLAST GREEDY SELECTION (JOURNEY-LEVEL, WEIGHTED)")
print("=" * 110)

selected = []
greedy_rows = []

for step in range(1, len(all_incidents) + 1):

    remaining = [i for i in all_incidents if i not in selected]
    if not remaining:
        break

    candidates = [
        {
            "incident": incident,
            "marginal_gain": marginal_gain(incident, selected),
            "standalone_coverage": coverage_value([incident]),
        }
        for incident in remaining
    ]

    candidate_df = pd.DataFrame(candidates).sort_values(
        ["marginal_gain", "standalone_coverage", "incident"],
        ascending=[False, False, True],
    )

    winner = candidate_df.iloc[0]
    selected.append(winner["incident"])

    covered = set()
    for incident in selected:
        covered.update(incident_sets[incident])

    greedy_rows.append({
        "selection_step": step,
        "selected_incident": winner["incident"],
        "fault_type": matrix.loc[
            matrix["incident_id"] == winner["incident"], "fault_type"
        ].iloc[0],
        "marginal_gain": winner["marginal_gain"],
        "standalone_coverage": winner["standalone_coverage"],
        "cumulative_coverage": coverage_value(selected),
        "unique_capabilities_covered": len(covered),
        "total_capabilities": universe_size,
        "coverage_fraction": len(covered) / universe_size,
    })

greedy_results = pd.DataFrame(greedy_rows)

print(
    greedy_results.to_string(
        index=False, float_format=lambda x: f"{x:.4f}"
    )
)


# ------------------------------------------------------
# Independent baseline
# ------------------------------------------------------

baseline_rows = [
    {
        "incident_id": incident,
        "fault_type": matrix.loc[
            matrix["incident_id"] == incident, "fault_type"
        ].iloc[0],
        "independent_score": sum(weights[c] for c in incident_sets[incident]),
        "capabilities_covered": len(incident_sets[incident]),
    }
    for incident in all_incidents
]

baseline = pd.DataFrame(baseline_rows).sort_values(
    ["independent_score", "incident_id"], ascending=[False, True]
).reset_index(drop=True)

baseline["rank"] = baseline.index + 1

baseline_order = baseline["incident_id"].tolist()

baseline_trajectory_rows = []
baseline_selected = []

for step, incident in enumerate(baseline_order, start=1):
    baseline_selected.append(incident)
    covered = set()
    for item in baseline_selected:
        covered.update(incident_sets[item])

    baseline_trajectory_rows.append({
        "selection_step": step,
        "selected_incident": incident,
        "cumulative_coverage": coverage_value(baseline_selected),
        "unique_capabilities_covered": len(covered),
        "coverage_fraction": len(covered) / universe_size,
    })

baseline_trajectory = pd.DataFrame(baseline_trajectory_rows)


# ------------------------------------------------------
# Comparison at each K
# ------------------------------------------------------

comparison_rows = []

for k in K_VALUES:
    if k > len(all_incidents):
        continue

    blast_selected = greedy_results.head(k)["selected_incident"].tolist()
    baseline_selected_k = baseline_order[:k]

    blast_coverage = coverage_value(blast_selected)
    baseline_coverage = coverage_value(baseline_selected_k)

    blast_unique = len(set().union(*[incident_sets[i] for i in blast_selected]))
    baseline_unique = len(set().union(*[incident_sets[i] for i in baseline_selected_k]))

    comparison_rows.append({
        "K": k,
        "BLAST_coverage": blast_coverage,
        "baseline_coverage": baseline_coverage,
        "BLAST_unique_capabilities": blast_unique,
        "baseline_unique_capabilities": baseline_unique,
        "BLAST_coverage_fraction": blast_unique / universe_size,
        "baseline_coverage_fraction": baseline_unique / universe_size,
        "BLAST_gain_over_baseline": blast_coverage - baseline_coverage,
    })

comparison = pd.DataFrame(comparison_rows)

print("\n")
print("=" * 110)
print("BLAST VS INDEPENDENT BASELINE (JOURNEY-LEVEL, WEIGHTED)")
print("=" * 110)

print(comparison.to_string(index=False, float_format=lambda x: f"{x:.4f}"))


# ======================================================
# SAVE
# ======================================================

greedy_results.to_csv(OUTPUT_GREEDY, index=False)
baseline.to_csv(OUTPUT_BASELINE, index=False)
comparison.to_csv(OUTPUT_COMPARISON, index=False)
baseline_trajectory.to_csv(OUTPUT_TRAJECTORY, index=False)

print("\n")
print("=" * 110)
print("FILES SAVED")
print("=" * 110)

for f in [OUTPUT_MATRIX, OUTPUT_OVERLAP, OUTPUT_GREEDY, OUTPUT_BASELINE,
          OUTPUT_COMPARISON, OUTPUT_TRAJECTORY]:
    print(f)

print(f"\nGate 2a result: {gate_2a}")
print("\nPilot re-run complete.")
