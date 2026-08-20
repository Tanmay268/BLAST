import pandas as pd
import numpy as np
import networkx as nx
from pathlib import Path


# ======================================================
# BLAST — PROPAGATION OBSERVATIONS
# ======================================================

IMPAIRMENT_FILE = "results/data/impairment_detection_results.csv"
GRAPH_FILE = "results/data/service_graph.csv"

OUTPUT_FILE = "results/data/propagation_observations.csv"


# ======================================================
# CANDIDATE IMPAIRMENT RULE
# ======================================================
#
# This is the calibrated candidate rule from the
# previous experiment:
#
#   median latency ratio >= 1.10
#       OR
#   P95 latency ratio >= 1.30
#
# IMPORTANT:
# This is still a calibration rule, not final
# ground truth. We are using it to construct
# propagation observations for the current experiment.


MEDIAN_THRESHOLD = 1.10
P95_THRESHOLD = 1.30


# ======================================================
# LOAD DATA
# ======================================================

print("=" * 110)
print("BLAST — PROPAGATION OBSERVATION CONSTRUCTION")
print("=" * 110)

print("\nLoading impairment data...")

impairment = pd.read_csv(
    IMPAIRMENT_FILE
)

print(
    f"Impairment observations: "
    f"{len(impairment)}"
)

print("\nLoading service graph...")

graph_df = pd.read_csv(
    GRAPH_FILE
)

print(
    f"Graph edges: "
    f"{len(graph_df)}"
)


# ======================================================
# INSPECT GRAPH COLUMNS
# ======================================================

print("\nGraph columns:")
print(
    list(graph_df.columns)
)


# ======================================================
# NORMALIZE GRAPH COLUMN NAMES
# ======================================================

# The graph created earlier should contain:
#
# source
# target
# calls
#
# If the script used service/source naming differently,
# automatically detect the appropriate columns.

source_candidates = [
    "source",
    "caller",
    "from",
    "source_service"
]

target_candidates = [
    "target",
    "callee",
    "to",
    "target_service"
]

call_candidates = [
    "calls",
    "count",
    "weight"
]


def find_column(
    candidates,
    columns
):

    for candidate in candidates:

        if candidate in columns:
            return candidate

    return None


source_col = find_column(
    source_candidates,
    graph_df.columns
)

target_col = find_column(
    target_candidates,
    graph_df.columns
)

call_col = find_column(
    call_candidates,
    graph_df.columns
)


if source_col is None or target_col is None:

    raise ValueError(
        "Could not identify source/target "
        "columns in service_graph.csv.\n"
        f"Available columns: "
        f"{list(graph_df.columns)}"
    )


# ======================================================
# PREPARE GRAPH
# ======================================================

graph_df = graph_df.rename(
    columns={
        source_col: "source",
        target_col: "target"
    }
)

if call_col is not None:

    graph_df = graph_df.rename(
        columns={
            call_col: "calls"
        }
    )

else:

    graph_df["calls"] = 1


# ------------------------------------------------------
# Create directed graph
# ------------------------------------------------------

G = nx.DiGraph()

for _, row in graph_df.iterrows():

    source = row["source"]
    target = row["target"]

    calls = row["calls"]

    G.add_edge(
        source,
        target,
        calls=calls
    )


print("\n")
print("=" * 110)
print("SERVICE GRAPH")
print("=" * 110)

print(
    f"Services: {G.number_of_nodes()}"
)

print(
    f"Edges: {G.number_of_edges()}"
)


# ======================================================
# CURRENT FAULT CASES
# ======================================================

cases = (
    impairment[
        [
            "case",
            "fault_type"
        ]
    ]
    .drop_duplicates()
)


print("\nCases:")
print(
    cases.to_string(
        index=False
    )
)


# ======================================================
# DETERMINE IMPAIRMENT USING CALIBRATED RULE
# ======================================================

impairment["latency_impaired"] = (
    impairment[
        "median_latency_ratio_detector"
    ]
    >= MEDIAN_THRESHOLD
)

impairment["tail_impaired"] = (
    impairment[
        "p95_latency_ratio_detector"
    ]
    >= P95_THRESHOLD
)

impairment["candidate_impaired"] = (
    impairment["latency_impaired"]
    |
    impairment["tail_impaired"]
)


# ======================================================
# CREATE LOOKUP
# ======================================================

impairment_lookup = {}

for _, row in impairment.iterrows():

    key = (
        row["case"],
        row["service"]
    )

    impairment_lookup[key] = {
        "impaired":
            bool(row["candidate_impaired"]),

        "median_ratio":
            row[
                "median_latency_ratio_detector"
            ],

        "p95_ratio":
            row[
                "p95_latency_ratio_detector"
            ],

        "impairment_score":
            max(
                (
                    row[
                        "median_latency_ratio_detector"
                    ] - 1
                ) / 0.10,

                (
                    row[
                        "p95_latency_ratio_detector"
                    ] - 1
                ) / 0.30,

                0
            )
    }


# ======================================================
# DETERMINE FAULT ROOT
# ======================================================
#
# Current experiment contains only
# checkoutservice faults.
#
# Therefore checkoutservice is the root for
# these cases.
#
# Later, this MUST be replaced by actual fault
# metadata when expanding to other RCAEval cases.


ROOT_SERVICE = "checkoutservice"


# ======================================================
# BUILD PROPAGATION OBSERVATIONS
# ======================================================

observations = []


for _, case_row in cases.iterrows():

    case = case_row["case"]

    fault_type = case_row[
        "fault_type"
    ]

    # --------------------------------------------------
    # Find all graph descendants
    # --------------------------------------------------

    if ROOT_SERVICE not in G:

        print(
            f"WARNING: {ROOT_SERVICE} "
            f"not found in graph."
        )

        continue

    descendants = nx.descendants(
        G,
        ROOT_SERVICE
    )

    # --------------------------------------------------
    # Direct and indirect paths
    # --------------------------------------------------

    for target in descendants:

        # ----------------------------------------------
        # Shortest graph distance
        # ----------------------------------------------

        try:

            distance = nx.shortest_path_length(
                G,
                ROOT_SERVICE,
                target
            )

        except nx.NetworkXNoPath:

            continue

        # ----------------------------------------------
        # Direct edge?
        # ----------------------------------------------

        direct_edge = G.has_edge(
            ROOT_SERVICE,
            target
        )

        # ----------------------------------------------
        # Number of paths
        # ----------------------------------------------

        try:

            path_count = sum(
                1
                for _ in nx.all_simple_paths(
                    G,
                    ROOT_SERVICE,
                    target
                )
            )

        except nx.NetworkXNoPath:

            path_count = 0

        # ----------------------------------------------
        # Service impairment
        # ----------------------------------------------

        result = impairment_lookup.get(
            (
                case,
                target
            )
        )

        if result is None:

            continue

        # ----------------------------------------------
        # Root impairment
        # ----------------------------------------------

        root_result = impairment_lookup.get(
            (
                case,
                ROOT_SERVICE
            )
        )

        if root_result is None:

            continue

        # ----------------------------------------------
        # Edge information
        # ----------------------------------------------

        if direct_edge:

            edge_calls = G[
                ROOT_SERVICE
            ][target]["calls"]

        else:

            edge_calls = np.nan

        # ----------------------------------------------
        # Store observation
        # ----------------------------------------------

        observations.append({

            "case":
                case,

            "fault_type":
                fault_type,

            "source":
                ROOT_SERVICE,

            "target":
                target,

            "graph_distance":
                distance,

            "direct_edge":
                direct_edge,

            "path_count":
                path_count,

            "edge_calls":
                edge_calls,

            "source_impaired":
                root_result[
                    "impaired"
                ],

            "target_impaired":
                result[
                    "impaired"
                ],

            "target_median_ratio":
                result[
                    "median_ratio"
                ],

            "target_p95_ratio":
                result[
                    "p95_ratio"
                ],

            "target_impairment_score":
                result[
                    "impairment_score"
                ],
        })


# ======================================================
# CONVERT TO DATAFRAME
# ======================================================

observations = pd.DataFrame(
    observations
)


if observations.empty:

    raise RuntimeError(
        "No propagation observations "
        "were generated."
    )


# ======================================================
# SAVE OBSERVATIONS
# ======================================================

observations.to_csv(
    OUTPUT_FILE,
    index=False
)


# ======================================================
# DISPLAY
# ======================================================

pd.set_option(
    "display.max_columns",
    None
)

pd.set_option(
    "display.width",
    260
)

print("\n")
print("=" * 110)
print("PROPAGATION OBSERVATIONS")
print("=" * 110)

print(
    observations.to_string(
        index=False,
        float_format=lambda x: f"{x:.4f}"
    )
)


# ======================================================
# SUMMARY BY TARGET
# ======================================================

print("\n")
print("=" * 110)
print("TARGET IMPAIRMENT ACROSS CASES")
print("=" * 110)

target_summary = (
    observations
    .groupby(
        [
            "fault_type",
            "target"
        ]
    )
    .agg(
        cases=(
            "case",
            "nunique"
        ),

        impaired_cases=(
            "target_impaired",
            "sum"
        ),

        mean_impairment=(
            "target_impairment_score",
            "mean"
        ),

        mean_median_ratio=(
            "target_median_ratio",
            "mean"
        ),

        mean_p95_ratio=(
            "target_p95_ratio",
            "mean"
        )
    )
    .reset_index()
)

target_summary[
    "empirical_probability"
] = (
    target_summary[
        "impaired_cases"
    ]
    /
    target_summary[
        "cases"
    ]
)


print(
    target_summary.to_string(
        index=False,
        float_format=lambda x: f"{x:.4f}"
    )
)


# ======================================================
# EMPIRICAL PROPAGATION PROBABILITIES
# ======================================================

print("\n")
print("=" * 110)
print("EMPIRICAL PROPAGATION PROBABILITIES")
print("=" * 110)

probability_table = (
    observations
    .groupby(
        [
            "fault_type",
            "source",
            "target"
        ]
    )
    .agg(
        observations=(
            "target_impaired",
            "count"
        ),

        propagated=(
            "target_impaired",
            "sum"
        )
    )
    .reset_index()
)

probability_table[
    "empirical_probability"
] = (
    probability_table[
        "propagated"
    ]
    /
    probability_table[
        "observations"
    ]
)


print(
    probability_table.to_string(
        index=False,
        float_format=lambda x: f"{x:.4f}"
    )
)


# ======================================================
# DIRECT VS INDIRECT
# ======================================================

print("\n")
print("=" * 110)
print("DIRECT VS INDIRECT PROPAGATION")
print("=" * 110)

direct_summary = (
    observations
    .groupby(
        [
            "fault_type",
            "direct_edge"
        ]
    )["target_impaired"]
    .agg(
        [
            "count",
            "sum",
            "mean"
        ]
    )
)

print(
    direct_summary.to_string(
        float_format=lambda x: f"{x:.4f}"
    )
)


# ======================================================
# DISTANCE EFFECT
# ======================================================

print("\n")
print("=" * 110)
print("PROPAGATION BY GRAPH DISTANCE")
print("=" * 110)

distance_summary = (
    observations
    .groupby(
        [
            "fault_type",
            "graph_distance"
        ]
    )["target_impaired"]
    .agg(
        [
            "count",
            "sum",
            "mean"
        ]
    )
)

print(
    distance_summary.to_string(
        float_format=lambda x: f"{x:.4f}"
    )
)


# ======================================================
# FINAL
# ======================================================

print("\n")
print("=" * 110)
print("FILES SAVED")
print("=" * 110)

print(
    f"Propagation observations: "
    f"{OUTPUT_FILE}"
)

print("\nPropagation observation construction complete.")