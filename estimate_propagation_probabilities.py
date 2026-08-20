import pandas as pd
import numpy as np


# ======================================================
# BLAST — PROPAGATION PROBABILITY ESTIMATION
# ======================================================

INPUT_FILE = "propagation_observations.csv"

OUTPUT_FILE = "propagation_probabilities.csv"


# ======================================================
# BETA PRIOR
# ======================================================
#
# We use a weak Beta(1,1) prior.
#
# This prevents:
#
#   0/3 -> exactly 0
#   3/3 -> exactly 1
#
# from becoming absolute probabilities when the
# current sample size is extremely small.
#
# Posterior:
#
#   Beta(alpha + k, beta + n-k)
#
# Posterior mean:
#
#   (alpha + k) / (alpha + beta + n)
#
# ======================================================

ALPHA = 1.0
BETA = 1.0


# ======================================================
# LOAD OBSERVATIONS
# ======================================================

print("=" * 110)
print("BLAST — PROPAGATION PROBABILITY ESTIMATION")
print("=" * 110)

print("\nLoading propagation observations...")

df = pd.read_csv(
    INPUT_FILE
)

print(
    f"Observations: {len(df)}"
)

print(
    f"Cases: {df['case'].nunique()}"
)

print(
    f"Fault types: "
    f"{df['fault_type'].nunique()}"
)


# ======================================================
# VALIDATE REQUIRED COLUMNS
# ======================================================

required_columns = [
    "fault_type",
    "source",
    "target",
    "target_impaired",
]

missing = [
    column
    for column in required_columns
    if column not in df.columns
]

if missing:

    raise ValueError(
        "Missing required columns: "
        + str(missing)
    )


# ======================================================
# CONVERT IMPAIRMENT TO BOOLEAN
# ======================================================

df["target_impaired"] = (
    df["target_impaired"]
    .astype(bool)
)


# ======================================================
# AGGREGATE OBSERVATIONS
# ======================================================

print("\nAggregating propagation observations...")


grouped = (
    df
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


# ======================================================
# RAW EMPIRICAL PROBABILITY
# ======================================================

grouped["raw_probability"] = (
    grouped["propagated"]
    /
    grouped["observations"]
)


# ======================================================
# BETA POSTERIOR
# ======================================================

grouped["posterior_alpha"] = (
    ALPHA +
    grouped["propagated"]
)

grouped["posterior_beta"] = (
    BETA +
    grouped["observations"]
    -
    grouped["propagated"]
)


# ======================================================
# SMOOTHED PROBABILITY
# ======================================================

grouped["smoothed_probability"] = (
    grouped["posterior_alpha"]
    /
    (
        grouped["posterior_alpha"]
        +
        grouped["posterior_beta"]
    )
)


# ======================================================
# POSTERIOR VARIANCE
# ======================================================

a = grouped[
    "posterior_alpha"
]

b = grouped[
    "posterior_beta"
]

grouped["posterior_variance"] = (
    a * b
    /
    (
        (a + b) ** 2
        *
        (a + b + 1)
    )
)


# ======================================================
# POSTERIOR STANDARD DEVIATION
# ======================================================

grouped["posterior_std"] = np.sqrt(
    grouped["posterior_variance"]
)


# ======================================================
# APPROXIMATE 95% INTERVAL
# ======================================================
#
# Normal approximation to the Beta posterior.
#
# With only three repetitions this interval is only
# approximate. It is reported for diagnostics.
#
# Later, when we have many more fault cases, we can
# replace this with exact Beta quantiles.
# ======================================================

Z = 1.96

grouped["ci_lower_approx"] = (
    grouped["smoothed_probability"]
    -
    Z *
    grouped["posterior_std"]
)

grouped["ci_upper_approx"] = (
    grouped["smoothed_probability"]
    +
    Z *
    grouped["posterior_std"]
)


# Keep probabilities inside [0,1]

grouped["ci_lower_approx"] = (
    grouped["ci_lower_approx"]
    .clip(0, 1)
)

grouped["ci_upper_approx"] = (
    grouped["ci_upper_approx"]
    .clip(0, 1)
)


# ======================================================
# CONFIDENCE / EVIDENCE CATEGORY
# ======================================================

def evidence_level(n):

    if n >= 30:
        return "strong"

    if n >= 10:
        return "moderate"

    if n >= 5:
        return "limited"

    return "very_limited"


grouped["evidence_level"] = (
    grouped["observations"]
    .apply(evidence_level)
)


# ======================================================
# SORT
# ======================================================

grouped = grouped.sort_values(
    [
        "fault_type",
        "source",
        "smoothed_probability"
    ],
    ascending=[
        True,
        True,
        False
    ]
)


# ======================================================
# SAVE
# ======================================================

grouped.to_csv(
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
print("PROPAGATION PROBABILITIES")
print("=" * 110)

display_columns = [
    "fault_type",
    "source",
    "target",
    "observations",
    "propagated",
    "raw_probability",
    "posterior_alpha",
    "posterior_beta",
    "smoothed_probability",
    "posterior_std",
    "ci_lower_approx",
    "ci_upper_approx",
    "evidence_level",
]

print(
    grouped[
        display_columns
    ].to_string(
        index=False,
        float_format=lambda x: f"{x:.4f}"
    )
)


# ======================================================
# FAULT-TYPE COMPARISON
# ======================================================

print("\n")
print("=" * 110)
print("FAULT-TYPE PROPAGATION COMPARISON")
print("=" * 110)

comparison = (
    grouped[
        [
            "fault_type",
            "source",
            "target",
            "raw_probability",
            "smoothed_probability"
        ]
    ]
    .pivot(
        index=[
            "source",
            "target"
        ],
        columns="fault_type",
        values="smoothed_probability"
    )
    .reset_index()
)


print(
    comparison.to_string(
        index=False,
        float_format=lambda x: f"{x:.4f}"
    )
)


# ======================================================
# PROBABILITY DIFFERENCE BETWEEN FAULT TYPES
# ======================================================

print("\n")
print("=" * 110)
print("FAULT-TYPE PROPAGATION DIFFERENCE")
print("=" * 110)


if set(
    ["cpu", "delay"]
).issubset(
    set(grouped["fault_type"])
):

    cpu = (
        grouped[
            grouped["fault_type"] == "cpu"
        ]
        [
            [
                "source",
                "target",
                "smoothed_probability"
            ]
        ]
        .rename(
            columns={
                "smoothed_probability":
                    "cpu_probability"
            }
        )
    )

    delay = (
        grouped[
            grouped["fault_type"] == "delay"
        ]
        [
            [
                "source",
                "target",
                "smoothed_probability"
            ]
        ]
        .rename(
            columns={
                "smoothed_probability":
                    "delay_probability"
            }
        )
    )

    difference = cpu.merge(
        delay,
        on=[
            "source",
            "target"
        ],
        how="outer"
    )

    difference[
        "cpu_minus_delay"
    ] = (
        difference[
            "cpu_probability"
        ]
        -
        difference[
            "delay_probability"
        ]
    )

    difference = difference.sort_values(
        "cpu_minus_delay",
        ascending=False
    )

    print(
        difference.to_string(
            index=False,
            float_format=lambda x: f"{x:.4f}"
        )
    )

else:

    print(
        "Both CPU and delay observations "
        "are required for this comparison."
    )


# ======================================================
# STRONGEST PROPAGATION EDGES
# ======================================================

print("\n")
print("=" * 110)
print("STRONGEST OBSERVED PROPAGATION EDGES")
print("=" * 110)

strongest = grouped.sort_values(
    "smoothed_probability",
    ascending=False
)

print(
    strongest[
        [
            "fault_type",
            "source",
            "target",
            "observations",
            "propagated",
            "raw_probability",
            "smoothed_probability",
            "ci_lower_approx",
            "ci_upper_approx"
        ]
    ]
    .head(20)
    .to_string(
        index=False,
        float_format=lambda x: f"{x:.4f}"
    )
)


# ======================================================
# ZERO-OBSERVATION RAW PROBABILITIES
# ======================================================

print("\n")
print("=" * 110)
print("EDGES WITH ZERO OBSERVED PROPAGATION")
print("=" * 110)

zero_edges = grouped[
    grouped["propagated"] == 0
]

if zero_edges.empty:

    print(
        "No zero-propagation observations."
    )

else:

    print(
        zero_edges[
            [
                "fault_type",
                "source",
                "target",
                "observations",
                "raw_probability",
                "smoothed_probability"
            ]
        ].to_string(
            index=False,
            float_format=lambda x: f"{x:.4f}"
        )
    )


# ======================================================
# FINAL
# ======================================================

print("\n")
print("=" * 110)
print("RESULT SAVED")
print("=" * 110)

print(
    f"File: {OUTPUT_FILE}"
)

print("\nPropagation probability estimation complete.")