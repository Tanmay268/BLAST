import pandas as pd
import numpy as np


# ======================================================
# BLAST — EFFECT THRESHOLD CALIBRATION
# ======================================================

INPUT_FILE = "impairment_detection_results.csv"

OUTPUT_FILE = "effect_threshold_calibration.csv"


# Candidate practical-effect thresholds
#
# These are NOT final thresholds.
# We test them empirically against the six known
# fault experiments.

MEDIAN_THRESHOLDS = [
    1.05,
    1.10,
    1.15,
    1.20,
    1.25,
    1.50,
    2.00,
]

P95_THRESHOLDS = [
    1.10,
    1.20,
    1.30,
    1.50,
    2.00,
    2.50,
    3.00,
]


# ======================================================
# LOAD DATA
# ======================================================

print("=" * 110)
print("BLAST — EFFECT THRESHOLD CALIBRATION")
print("=" * 110)

df = pd.read_csv(INPUT_FILE)

print(
    f"\nLoaded observations: {len(df)}"
)

print(
    f"Cases: {df['case'].nunique()}"
)

print(
    f"Services: {df['service'].nunique()}"
)


# ======================================================
# IDENTIFY ROOT SERVICE
# ======================================================

df["is_root"] = (
    df["service"] == "checkoutservice"
)


# ======================================================
# CALIBRATE MEDIAN LATENCY
# ======================================================

median_results = []


for threshold in MEDIAN_THRESHOLDS:

    df["median_effect"] = (
        df["median_latency_ratio_detector"]
        >= threshold
    )

    root = df[df["is_root"]]

    downstream = df[~df["is_root"]]

    # Root detection
    root_detected = (
        root["median_effect"].sum()
    )

    root_total = len(root)

    root_recall = (
        root_detected / root_total
        if root_total > 0
        else 0
    )

    # Downstream false positives
    downstream_fp = (
        downstream["median_effect"].sum()
    )

    downstream_total = len(
        downstream
    )

    downstream_fp_rate = (
        downstream_fp / downstream_total
        if downstream_total > 0
        else 0
    )

    # Overall
    total_positive = (
        df["median_effect"].sum()
    )

    median_results.append({

        "metric":
            "median_latency",

        "threshold":
            threshold,

        "root_detected":
            root_detected,

        "root_total":
            root_total,

        "root_recall":
            root_recall,

        "downstream_false_positives":
            downstream_fp,

        "downstream_total":
            downstream_total,

        "downstream_false_positive_rate":
            downstream_fp_rate,

        "total_positive":
            total_positive,
    })


median_results = pd.DataFrame(
    median_results
)


# ======================================================
# CALIBRATE P95 LATENCY
# ======================================================

p95_results = []


for threshold in P95_THRESHOLDS:

    df["p95_effect"] = (
        df["p95_latency_ratio_detector"]
        >= threshold
    )

    root = df[df["is_root"]]

    downstream = df[~df["is_root"]]

    root_detected = (
        root["p95_effect"].sum()
    )

    root_total = len(root)

    root_recall = (
        root_detected / root_total
        if root_total > 0
        else 0
    )

    downstream_fp = (
        downstream["p95_effect"].sum()
    )

    downstream_total = len(
        downstream
    )

    downstream_fp_rate = (
        downstream_fp / downstream_total
        if downstream_total > 0
        else 0
    )

    total_positive = (
        df["p95_effect"].sum()
    )

    p95_results.append({

        "metric":
            "p95_latency",

        "threshold":
            threshold,

        "root_detected":
            root_detected,

        "root_total":
            root_total,

        "root_recall":
            root_recall,

        "downstream_false_positives":
            downstream_fp,

        "downstream_total":
            downstream_total,

        "downstream_false_positive_rate":
            downstream_fp_rate,

        "total_positive":
            total_positive,
    })


p95_results = pd.DataFrame(
    p95_results
)


# ======================================================
# COMBINATION RULES
# ======================================================

combination_results = []


for median_threshold in MEDIAN_THRESHOLDS:

    for p95_threshold in P95_THRESHOLDS:

        median_positive = (
            df[
                "median_latency_ratio_detector"
            ]
            >= median_threshold
        )

        p95_positive = (
            df[
                "p95_latency_ratio_detector"
            ]
            >= p95_threshold
        )

        # ------------------------------------------------
        # Rule A:
        # median OR p95
        # ------------------------------------------------

        either = (
            median_positive |
            p95_positive
        )

        root = df["is_root"]

        root_detected = (
            either[root].sum()
        )

        root_total = root.sum()

        root_recall = (
            root_detected / root_total
            if root_total > 0
            else 0
        )

        downstream = ~root

        downstream_fp = (
            either[downstream].sum()
        )

        downstream_total = (
            downstream.sum()
        )

        downstream_fp_rate = (
            downstream_fp /
            downstream_total
            if downstream_total > 0
            else 0
        )

        combination_results.append({

            "rule":
                "median_OR_p95",

            "median_threshold":
                median_threshold,

            "p95_threshold":
                p95_threshold,

            "root_recall":
                root_recall,

            "downstream_false_positive_rate":
                downstream_fp_rate,

            "root_detected":
                root_detected,

            "root_total":
                root_total,

            "downstream_false_positives":
                downstream_fp,

            "downstream_total":
                downstream_total,
        })


combination_results = pd.DataFrame(
    combination_results
)


# ======================================================
# PRINT MEDIAN RESULTS
# ======================================================

pd.set_option(
    "display.max_columns",
    None
)

pd.set_option(
    "display.width",
    220
)

print("\n")
print("=" * 110)
print("MEDIAN LATENCY EFFECT THRESHOLDS")
print("=" * 110)

print(
    median_results.to_string(
        index=False,
        float_format=lambda x: f"{x:.4f}"
    )
)


# ======================================================
# PRINT P95 RESULTS
# ======================================================

print("\n")
print("=" * 110)
print("P95 LATENCY EFFECT THRESHOLDS")
print("=" * 110)

print(
    p95_results.to_string(
        index=False,
        float_format=lambda x: f"{x:.4f}"
    )
)


# ======================================================
# PRINT COMBINATION RESULTS
# ======================================================

print("\n")
print("=" * 110)
print("COMBINED MEDIAN OR P95 THRESHOLDS")
print("=" * 110)

print(
    combination_results.to_string(
        index=False,
        float_format=lambda x: f"{x:.4f}"
    )
)


# ======================================================
# FIND BEST CANDIDATES
# ======================================================

# Prefer:
# 1. 100% root recall
# 2. lowest downstream false positive rate

perfect = combination_results[
    combination_results["root_recall"] == 1.0
].copy()


print("\n")
print("=" * 110)
print("PERFECT ROOT-RECALL CANDIDATES")
print("=" * 110)

if len(perfect) == 0:

    print(
        "No threshold combination achieved "
        "100% root recall."
    )

else:

    perfect = perfect.sort_values(
        [
            "downstream_false_positive_rate",
            "median_threshold",
            "p95_threshold"
        ]
    )

    print(
        perfect.head(20).to_string(
            index=False,
            float_format=lambda x: f"{x:.4f}"
        )
    )


# ======================================================
# PER-CASE ROOT DETECTION
# ======================================================

print("\n")
print("=" * 110)
print("ROOT SERVICE EFFECT SIZES")
print("=" * 110)

root = df[
    df["is_root"]
].copy()

print(
    root[
        [
            "case",
            "fault_type",
            "median_latency_ratio_detector",
            "p95_latency_ratio_detector"
        ]
    ].to_string(
        index=False,
        float_format=lambda x: f"{x:.4f}"
    )
)


# ======================================================
# DOWNSTREAM EFFECT SIZES
# ======================================================

print("\n")
print("=" * 110)
print("LARGEST DOWNSTREAM EFFECT SIZES")
print("=" * 110)

downstream = df[
    ~df["is_root"]
].copy()

largest = downstream.sort_values(
    [
        "median_latency_ratio_detector",
        "p95_latency_ratio_detector"
    ],
    ascending=False
)

print(
    largest[
        [
            "case",
            "fault_type",
            "service",
            "median_latency_ratio_detector",
            "p95_latency_ratio_detector",
            "median_latency_robust_z",
            "p95_latency_robust_z"
        ]
    ]
    .head(20)
    .to_string(
        index=False,
        float_format=lambda x: f"{x:.4f}"
    )
)


# ======================================================
# SAVE ALL RESULTS
# ======================================================

all_results = pd.concat(
    [
        median_results,
        p95_results
    ],
    ignore_index=True
)

all_results.to_csv(
    OUTPUT_FILE,
    index=False
)

combination_results.to_csv(
    "effect_threshold_combinations.csv",
    index=False
)


# ======================================================
# FINAL
# ======================================================

print("\n")
print("=" * 110)
print("FILES SAVED")
print("=" * 110)

print(
    OUTPUT_FILE
)

print(
    "effect_threshold_combinations.csv"
)

print("\nCalibration complete.")