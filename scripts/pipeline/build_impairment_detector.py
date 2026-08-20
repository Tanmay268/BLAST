import pandas as pd
import numpy as np
from pathlib import Path


# ======================================================
# BLAST — BASELINE-NORMALIZED IMPAIRMENT DETECTOR
# ======================================================

BASELINE_FILE = "results/data/baseline_windows_30s.csv"
IMPAIRMENT_FILE = "results/data/impairment_dataset_30s.csv"

OUTPUT_FILE = "results/data/impairment_detection_results.csv"


# ======================================================
# CONFIGURATION
# ======================================================

# Minimum number of baseline observations required
MIN_BASELINE_WINDOWS = 10

# Robust threshold:
# median + THRESHOLD * MAD
#
# MAD is converted to a robust sigma estimate:
#
# robust_sigma = 1.4826 * MAD
#
# We use 3 robust sigma as the initial candidate.
ROBUST_Z_THRESHOLD = 3.0

# Small epsilon prevents division by zero
EPSILON = 1e-9


# ======================================================
# LOAD DATA
# ======================================================

print("=" * 100)
print("BLAST — IMPAIRMENT DETECTOR")
print("=" * 100)

print("\nLoading baseline data...")

baseline = pd.read_csv(
    BASELINE_FILE
)

print(
    f"Baseline rows: {len(baseline)}"
)

print("\nLoading fault data...")

fault = pd.read_csv(
    IMPAIRMENT_FILE
)

print(
    f"Fault rows: {len(fault)}"
)


# ======================================================
# METRIC DEFINITIONS
# ======================================================

# Baseline metrics
BASELINE_METRICS = [
    "median_latency",
    "p95_latency",
    "error_rate",
]

# Corresponding post-fault metrics
FAULT_METRICS = {
    "median_latency":
        "post_median_latency",

    "p95_latency":
        "post_p95_latency",

    "error_rate":
        "post_error_rate",
}


# ======================================================
# ROBUST BASELINE STATISTICS
# ======================================================

print("\nCalculating robust baseline statistics...")

baseline_stats = []


for (fault_type, service), group in baseline.groupby(
    ["fault_type", "service"]
):

    if len(group) < MIN_BASELINE_WINDOWS:
        continue

    row = {
        "fault_type": fault_type,
        "service": service,
        "baseline_windows": len(group),
    }

    for metric in BASELINE_METRICS:

        values = (
            pd.to_numeric(
                group[metric],
                errors="coerce"
            )
            .dropna()
        )

        if len(values) < MIN_BASELINE_WINDOWS:
            continue

        median = values.median()

        mad = np.median(
            np.abs(
                values - median
            )
        )

        # Robust estimate of standard deviation
        robust_sigma = (
            1.4826 * mad
        )

        row[
            f"{metric}_baseline_median"
        ] = median

        row[
            f"{metric}_baseline_mad"
        ] = mad

        row[
            f"{metric}_robust_sigma"
        ] = robust_sigma

    baseline_stats.append(row)


baseline_stats = pd.DataFrame(
    baseline_stats
)


# ======================================================
# DISPLAY BASELINE STATISTICS
# ======================================================

print("\n")
print("=" * 100)
print("ROBUST BASELINE STATISTICS")
print("=" * 100)

print(
    baseline_stats.to_string(
        index=False,
        float_format=lambda x: f"{x:.6f}"
    )
)


# ======================================================
# MERGE BASELINE WITH FAULT OBSERVATIONS
# ======================================================

data = fault.merge(
    baseline_stats,
    on=[
        "fault_type",
        "service"
    ],
    how="left"
)


# ======================================================
# CALCULATE ROBUST Z-SCORES
# ======================================================

print("\nCalculating baseline-normalized scores...")


for metric in BASELINE_METRICS:

    fault_column = FAULT_METRICS[metric]

    baseline_median_column = (
        f"{metric}_baseline_median"
    )

    sigma_column = (
        f"{metric}_robust_sigma"
    )

    score_column = (
        f"{metric}_robust_z"
    )

    baseline_median = (
        data[baseline_median_column]
    )

    robust_sigma = (
        data[sigma_column]
    )

    observed = (
        data[fault_column]
    )

    # --------------------------------------------------
    # Robust z-score
    #
    # Positive = degradation
    # Negative = improvement
    # --------------------------------------------------

    data[score_column] = np.where(
        robust_sigma > EPSILON,

        (
            observed -
            baseline_median
        ) / robust_sigma,

        0.0
    )


# ======================================================
# CALCULATE SIMPLE RATIOS
# ======================================================

data["median_latency_ratio_detector"] = (
    data["post_median_latency"] /
    data["pre_median_latency"]
)

data["p95_latency_ratio_detector"] = (
    data["post_p95_latency"] /
    data["pre_p95_latency"]
)


# ======================================================
# INDIVIDUAL SIGNAL FLAGS
# ======================================================

# ------------------------------------------------------
# Latency median
# ------------------------------------------------------

data["median_latency_impaired"] = (
    data["median_latency_robust_z"]
    >= ROBUST_Z_THRESHOLD
)


# ------------------------------------------------------
# P95 latency
# ------------------------------------------------------

data["p95_latency_impaired"] = (
    data["p95_latency_robust_z"]
    >= ROBUST_Z_THRESHOLD
)


# ------------------------------------------------------
# Error rate
#
# Baseline error rate is zero everywhere in the
# currently observed dataset.
#
# Therefore ANY positive post-fault error rate
# is treated as an error signal.
# ------------------------------------------------------

data["error_impaired"] = (
    data["post_error_rate"] > 0
)


# ======================================================
# COMBINED IMPAIRMENT SCORE
# ======================================================

# We do NOT use a single arbitrary latency threshold.
#
# Instead:
#
#   median latency signal
#   +
#   p95 latency signal
#   +
#   error signal
#
# A service is initially considered impaired if:
#
#   1. median latency exceeds robust baseline
#      OR
#
#   2. P95 exceeds robust baseline
#      OR
#
#   3. errors appear
#
# This is an intentionally sensitive candidate detector.
#
# We will evaluate and refine this rule later.


data["impaired"] = (
    data["median_latency_impaired"]
    |
    data["p95_latency_impaired"]
    |
    data["error_impaired"]
)


# ======================================================
# IMPAIRMENT SCORE
# ======================================================

# Continuous score for later ranking.
#
# We use the largest positive standardized degradation
# among the latency signals.
#
# Error presence adds a separate strong signal.

data["impairment_score"] = (
    data[
        [
            "median_latency_robust_z",
            "p95_latency_robust_z"
        ]
    ]
    .clip(lower=0)
    .max(axis=1)
)

# Add error signal
data.loc[
    data["error_impaired"],
    "impairment_score"
] += ROBUST_Z_THRESHOLD


# ======================================================
# SIGNAL COUNT
# ======================================================

data["impaired_signal_count"] = (
    data["median_latency_impaired"].astype(int)
    +
    data["p95_latency_impaired"].astype(int)
    +
    data["error_impaired"].astype(int)
)


# ======================================================
# SAVE RESULTS
# ======================================================

data.to_csv(
    OUTPUT_FILE,
    index=False
)


# ======================================================
# DISPLAY DETECTION RESULTS
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
print("=" * 100)
print("IMPAIRMENT DETECTION RESULTS")
print("=" * 100)

display_columns = [
    "case",
    "fault_type",
    "service",

    "median_latency_ratio_detector",
    "p95_latency_ratio_detector",

    "median_latency_robust_z",
    "p95_latency_robust_z",

    "post_error_rate",

    "median_latency_impaired",
    "p95_latency_impaired",
    "error_impaired",

    "impaired_signal_count",
    "impairment_score",
    "impaired",
]

print(
    data[
        display_columns
    ].to_string(
        index=False,
        float_format=lambda x: f"{x:.4f}"
    )
)


# ======================================================
# ROOT SERVICE RESULTS
# ======================================================

print("\n")
print("=" * 100)
print("CHECKOUTSERVICE — ROOT FAULT DETECTION")
print("=" * 100)

root = data[
    data["service"] == "checkoutservice"
]

print(
    root[
        display_columns
    ].to_string(
        index=False,
        float_format=lambda x: f"{x:.4f}"
    )
)


# ======================================================
# IMPAIRED SERVICES BY CASE
# ======================================================

print("\n")
print("=" * 100)
print("DETECTED IMPAIRED SERVICES")
print("=" * 100)

for case, group in data.groupby("case"):

    impaired = group[
        group["impaired"]
    ].copy()

    print(
        f"\n{case}"
    )

    if len(impaired) == 0:

        print(
            "  No services detected as impaired."
        )

        continue

    impaired = impaired.sort_values(
        "impairment_score",
        ascending=False
    )

    for _, row in impaired.iterrows():

        print(
            f"  {row['service']:<28}"
            f" score={row['impairment_score']:.3f}"
            f" signals={int(row['impaired_signal_count'])}"
        )


# ======================================================
# FAULT-TYPE SUMMARY
# ======================================================

print("\n")
print("=" * 100)
print("FAULT-TYPE IMPAIRMENT SUMMARY")
print("=" * 100)

summary = (
    data
    .groupby(
        ["fault_type", "service"]
    )
    .agg(
        cases=("case", "nunique"),
        impaired_cases=("impaired", "sum"),
        mean_score=("impairment_score", "mean"),
        max_score=("impairment_score", "max"),
        mean_median_z=(
            "median_latency_robust_z",
            "mean"
        ),
        mean_p95_z=(
            "p95_latency_robust_z",
            "mean"
        )
    )
    .reset_index()
)

print(
    summary.to_string(
        index=False,
        float_format=lambda x: f"{x:.4f}"
    )
)


# ======================================================
# FINAL
# ======================================================

print("\n")
print("=" * 100)
print("RESULT SAVED")
print("=" * 100)

print(
    f"File: {OUTPUT_FILE}"
)

print(
    "\nImpairment detection complete."
)