import pandas as pd
import numpy as np


# ============================================================
# BLAST — GREEDY BUSINESS-IMPACT-AWARE INCIDENT TRIAGE
# ============================================================

INPUT_FILE = "results/data/incident_capability_matrix.csv"

OUTPUT_FILE = "results/data/blast_greedy_results.csv"
BASELINE_FILE = "results/data/independent_ranking_results.csv"


# ============================================================
# CONFIGURATION
# ============================================================

# Number of incidents to select.
#
# We use several K values so that we can examine how quickly
# BLAST accumulates unique business capability coverage.

K_VALUES = [1, 2, 3, 4, 5, 6]


# ============================================================
# CAPABILITY WEIGHTS
# ============================================================
#
# IMPORTANT:
#
# We currently do NOT have real revenue / financial-loss
# values in RCAEval.
#
# Therefore the primary experiment uses uniform weights:
#
#     w(c) = 1
#
# Later, we can perform sensitivity analysis using alternative
# declared business-weight schemes.
# ============================================================

DEFAULT_WEIGHT = 1.0


# ============================================================
# LOAD DATA
# ============================================================

print("=" * 110)
print("BLAST — GREEDY BUSINESS-IMPACT-AWARE INCIDENT TRIAGE")
print("=" * 110)

print("\nLoading incident-capability matrix...")

df = pd.read_csv(
    INPUT_FILE
)

print(
    f"Rows: {len(df)}"
)


# ============================================================
# IDENTIFY COLUMNS
# ============================================================

metadata_columns = [
    "incident_id",
    "fault_type"
]

capability_columns = [
    c
    for c in df.columns
    if c not in metadata_columns
]


if len(capability_columns) == 0:

    raise ValueError(
        "No business capability columns found."
    )


print(
    f"Incidents: {len(df)}"
)

print(
    f"Business capabilities: "
    f"{len(capability_columns)}"
)

print(
    "\nCapabilities:"
)

for capability in capability_columns:

    print(
        f"  - {capability}"
    )


# ============================================================
# NORMALIZE MATRIX
# ============================================================

for capability in capability_columns:

    df[capability] = (
        pd.to_numeric(
            df[capability],
            errors="coerce"
        )
        .fillna(0)
        .astype(int)
    )


# ============================================================
# CAPABILITY WEIGHTS
# ============================================================

weights = {
    capability: DEFAULT_WEIGHT
    for capability in capability_columns
}


# ============================================================
# INCIDENT CAPABILITY SETS
# ============================================================

incident_sets = {}

for _, row in df.iterrows():

    incident = row[
        "incident_id"
    ]

    affected = {
        capability
        for capability in capability_columns
        if row[capability] == 1
    }

    incident_sets[
        incident
    ] = affected


# ============================================================
# OBJECTIVE FUNCTION
# ============================================================
#
# F(S) = weighted number of UNIQUE capabilities covered
#        by selected incidents S.
#
# This is a classic coverage objective.
#
# Because adding an already-covered capability provides
# zero additional value, the objective has diminishing
# returns.
# ============================================================

def coverage_value(
    selected_incidents
):

    covered = set()

    for incident in selected_incidents:

        covered.update(
            incident_sets[
                incident
            ]
        )

    value = sum(
        weights[c]
        for c in covered
    )

    return value


# ============================================================
# MARGINAL GAIN
# ============================================================

def marginal_gain(
    incident,
    selected
):

    current_value = (
        coverage_value(
            selected
        )
    )

    new_value = (
        coverage_value(
            selected + [incident]
        )
    )

    return (
        new_value -
        current_value
    )


# ============================================================
# GREEDY BLAST
# ============================================================
#
# At each step:
#
#     choose incident with maximum marginal coverage.
#
# This explicitly avoids repeatedly selecting incidents
# whose business impact is already covered.
# ============================================================

print("\n")
print("=" * 110)
print("BLAST GREEDY SELECTION")
print("=" * 110)

all_incidents = list(
    incident_sets.keys()
)

selected = []

greedy_rows = []


for step in range(
    1,
    len(all_incidents) + 1
):

    remaining = [
        incident
        for incident in all_incidents
        if incident not in selected
    ]

    if not remaining:
        break

    # --------------------------------------------------------
    # Calculate marginal gain for every remaining incident
    # --------------------------------------------------------

    candidates = []

    for incident in remaining:

        gain = marginal_gain(
            incident,
            selected
        )

        candidates.append({

            "incident":
                incident,

            "marginal_gain":
                gain,

            "standalone_coverage":
                coverage_value(
                    [incident]
                )
        })

    candidate_df = pd.DataFrame(
        candidates
    )

    # --------------------------------------------------------
    # Select maximum marginal gain
    # --------------------------------------------------------

    candidate_df = candidate_df.sort_values(
        [
            "marginal_gain",
            "standalone_coverage",
            "incident"
        ],
        ascending=[
            False,
            False,
            True
        ]
    )

    winner = candidate_df.iloc[0]

    selected_incident = (
        winner["incident"]
    )

    selected.append(
        selected_incident
    )

    # --------------------------------------------------------
    # Coverage after selection
    # --------------------------------------------------------

    covered = set()

    for incident in selected:

        covered.update(
            incident_sets[
                incident
            ]
        )

    total_value = (
        coverage_value(
            selected
        )
    )

    greedy_rows.append({

        "selection_step":
            step,

        "selected_incident":
            selected_incident,

        "fault_type":
            df.loc[
                df["incident_id"]
                == selected_incident,
                "fault_type"
            ].iloc[0],

        "marginal_gain":
            winner["marginal_gain"],

        "standalone_coverage":
            winner[
                "standalone_coverage"
            ],

        "cumulative_coverage":
            total_value,

        "unique_capabilities_covered":
            len(covered),

        "total_capabilities":
            len(capability_columns),

        "coverage_fraction":
            (
                len(covered)
                /
                len(capability_columns)
            )
    })


greedy_results = pd.DataFrame(
    greedy_rows
)


# ============================================================
# DISPLAY GREEDY SELECTION
# ============================================================

print(
    greedy_results.to_string(
        index=False,
        float_format=lambda x: f"{x:.4f}"
    )
)


# ============================================================
# SHOW COVERAGE AFTER EACH STEP
# ============================================================

print("\n")
print("=" * 110)
print("BLAST COVERAGE TRAJECTORY")
print("=" * 110)

for _, row in greedy_results.iterrows():

    step = int(
        row["selection_step"]
    )

    incident = row[
        "selected_incident"
    ]

    selected_so_far = (
        selected[:step]
    )

    covered = set()

    for item in selected_so_far:

        covered.update(
            incident_sets[item]
        )

    print(
        f"\nStep {step}: {incident}"
    )

    print(
        f"Marginal gain: "
        f"{row['marginal_gain']:.4f}"
    )

    print(
        f"Coverage: "
        f"{len(covered)}/"
        f"{len(capability_columns)}"
    )

    for capability in sorted(
        covered
    ):

        print(
            f"  ✓ {capability}"
        )


# ============================================================
# INDEPENDENT INCIDENT SCORING BASELINE
# ============================================================
#
# Baseline:
#
#     Score(i) = standalone business capability coverage.
#
# This treats every incident independently and therefore
# does not account for overlap with already-selected
# incidents.
# ============================================================

print("\n")
print("=" * 110)
print("INDEPENDENT INCIDENT RANKING BASELINE")
print("=" * 110)

baseline_rows = []

for incident in all_incidents:

    capabilities = (
        incident_sets[
            incident
        ]
    )

    score = sum(
        weights[c]
        for c in capabilities
    )

    baseline_rows.append({

        "incident_id":
            incident,

        "fault_type":
            df.loc[
                df["incident_id"]
                == incident,
                "fault_type"
            ].iloc[0],

        "independent_score":
            score,

        "capabilities_covered":
            len(capabilities)
    })


baseline = pd.DataFrame(
    baseline_rows
)

baseline = baseline.sort_values(
    [
        "independent_score",
        "incident_id"
    ],
    ascending=[
        False,
        True
    ]
).reset_index(
    drop=True
)

baseline[
    "rank"
] = (
    baseline.index + 1
)


print(
    baseline.to_string(
        index=False,
        float_format=lambda x: f"{x:.4f}"
    )
)


# ============================================================
# BASELINE COVERAGE TRAJECTORY
# ============================================================

print("\n")
print("=" * 110)
print("INDEPENDENT RANKING COVERAGE TRAJECTORY")
print("=" * 110)

baseline_order = (
    baseline[
        "incident_id"
    ].tolist()
)

baseline_selected = []

baseline_rows_trajectory = []


for step, incident in enumerate(
    baseline_order,
    start=1
):

    baseline_selected.append(
        incident
    )

    covered = set()

    for item in baseline_selected:

        covered.update(
            incident_sets[item]
        )

    baseline_rows_trajectory.append({

        "selection_step":
            step,

        "selected_incident":
            incident,

        "standalone_score":
            baseline.loc[
                baseline["incident_id"]
                == incident,
                "independent_score"
            ].iloc[0],

        "cumulative_coverage":
            coverage_value(
                baseline_selected
            ),

        "unique_capabilities_covered":
            len(covered),

        "coverage_fraction":
            (
                len(covered)
                /
                len(capability_columns)
            )
    })


baseline_trajectory = pd.DataFrame(
    baseline_rows_trajectory
)


print(
    baseline_trajectory.to_string(
        index=False,
        float_format=lambda x: f"{x:.4f}"
    )
)


# ============================================================
# DIRECT BLAST VS BASELINE COMPARISON
# ============================================================

print("\n")
print("=" * 110)
print("BLAST VS INDEPENDENT RANKING")
print("=" * 110)

comparison_rows = []


for k in K_VALUES:

    if k > len(all_incidents):
        continue

    blast_selected = (
        greedy_results
        .head(k)
        [
            "selected_incident"
        ]
        .tolist()
    )

    baseline_selected_k = (
        baseline_order[:k]
    )

    blast_coverage = (
        coverage_value(
            blast_selected
        )
    )

    baseline_coverage = (
        coverage_value(
            baseline_selected_k
        )
    )

    blast_unique = len(
        set().union(
            *[
                incident_sets[i]
                for i in blast_selected
            ]
        )
    )

    baseline_unique = len(
        set().union(
            *[
                incident_sets[i]
                for i in baseline_selected_k
            ]
        )
    )

    comparison_rows.append({

        "K":
            k,

        "BLAST_coverage":
            blast_coverage,

        "baseline_coverage":
            baseline_coverage,

        "BLAST_unique_capabilities":
            blast_unique,

        "baseline_unique_capabilities":
            baseline_unique,

        "BLAST_coverage_fraction":
            blast_unique
            /
            len(capability_columns),

        "baseline_coverage_fraction":
            baseline_unique
            /
            len(capability_columns),

        "BLAST_gain_over_baseline":
            blast_coverage
            -
            baseline_coverage
    })


comparison = pd.DataFrame(
    comparison_rows
)


print(
    comparison.to_string(
        index=False,
        float_format=lambda x: f"{x:.4f}"
    )
)


# ============================================================
# REDUNDANCY / MARGINAL GAIN ANALYSIS
# ============================================================

print("\n")
print("=" * 110)
print("MARGINAL GAIN ANALYSIS")
print("=" * 110)

print(
    greedy_results[
        [
            "selection_step",
            "selected_incident",
            "marginal_gain",
            "cumulative_coverage"
        ]
    ].to_string(
        index=False,
        float_format=lambda x: f"{x:.4f}"
    )
)


# ============================================================
# SUBMODULARITY SANITY CHECK
# ============================================================
#
# For a coverage function:
#
#     F(A ∪ {x}) - F(A)
#       >=
#     F(B ∪ {x}) - F(B)
#
# whenever A ⊆ B.
#
# We perform a simple random sanity check over nested
# selected sets.
# ============================================================

print("\n")
print("=" * 110)
print("SUBMODULARITY SANITY CHECK")
print("=" * 110)

violations = 0
checks = 0

for i in range(
    len(all_incidents)
):

    x = all_incidents[i]

    A = all_incidents[
        :i
    ]

    B = all_incidents[
        :i + 1
    ]

    if x in B:
        B_without_x = [
            item
            for item in B
            if item != x
        ]
    else:
        B_without_x = B

    gain_A = marginal_gain(
        x,
        A
    )

    gain_B = marginal_gain(
        x,
        B_without_x
    )

    checks += 1

    if gain_A + 1e-9 < gain_B:

        violations += 1

        print(
            "Violation:",
            x,
            gain_A,
            gain_B
        )


print(
    f"Checks: {checks}"
)

print(
    f"Violations: {violations}"
)

if violations == 0:

    print(
        "✓ No submodularity violations detected."
    )

else:

    print(
        "⚠ Submodularity violations detected."
    )


# ============================================================
# SAVE RESULTS
# ============================================================

greedy_results.to_csv(
    OUTPUT_FILE,
    index=False
)

baseline.to_csv(
    BASELINE_FILE,
    index=False
)

comparison.to_csv(
    "results/data/blast_vs_baseline.csv",
    index=False
)

baseline_trajectory.to_csv(
    "results/data/baseline_coverage_trajectory.csv",
    index=False
)


# ============================================================
# FINAL SUMMARY
# ============================================================

print("\n")
print("=" * 110)
print("BLAST EXPERIMENT COMPLETE")
print("=" * 110)

print(
    f"Total incidents: "
    f"{len(all_incidents)}"
)

print(
    f"Total capabilities: "
    f"{len(capability_columns)}"
)

print(
    "\nBLAST selected order:"
)

for i, incident in enumerate(
    selected,
    start=1
):

    print(
        f"  {i}. {incident}"
    )


print("\nFiles saved:")

print(
    f"  {OUTPUT_FILE}"
)

print(
    f"  {BASELINE_FILE}"
)

print(
    "  blast_vs_baseline.csv"
)

print(
    "  baseline_coverage_trajectory.csv"
)

print(
    "\nBLAST greedy selection complete."
)