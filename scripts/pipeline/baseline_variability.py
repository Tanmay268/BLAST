import pandas as pd
import numpy as np
from pathlib import Path


# ======================================================
# CONFIGURATION
# ======================================================

CASES = [
    "re2ob_checkoutservice_delay_1",
    "re2ob_checkoutservice_delay_2",
    "re2ob_checkoutservice_delay_3",
    "re2ob_checkoutservice_cpu_1",
    "re2ob_checkoutservice_cpu_2",
    "re2ob_checkoutservice_cpu_3",
]

BASE_DIR = Path("./data")

# Use only the pre-fault period
WINDOW_SECONDS = 30


# ======================================================
# ANALYZE NORMAL BASELINE FOR ONE CASE
# ======================================================

def analyze_case(case):

    case_dir = BASE_DIR / case

    trace_file = case_dir / "traces.parquet"
    inject_file = case_dir / "inject_time.txt"

    print(f"\nLoading {case}...")

    df = pd.read_parquet(trace_file)

    with open(inject_file, "r") as f:
        inject_time = int(f.read().strip())

    inject_ms = inject_time * 1000

    # --------------------------------------------------
    # Keep ONLY the pre-fault period
    # --------------------------------------------------

    df = df[
        df["startTimeMillis"] < inject_ms
    ].copy()

    if len(df) == 0:
        return None

    # --------------------------------------------------
    # Time relative to beginning of baseline
    # --------------------------------------------------

    min_time = df["startTimeMillis"].min()

    df["relative_seconds"] = (
        df["startTimeMillis"] - min_time
    ) / 1000

    # --------------------------------------------------
    # Create consecutive 30-second windows
    # --------------------------------------------------

    df["window"] = (
        df["relative_seconds"]
        // WINDOW_SECONDS
    ).astype(int)

    # --------------------------------------------------
    # Services
    # --------------------------------------------------

    services = sorted(
        df["serviceName"]
        .dropna()
        .unique()
    )

    results = []

    # --------------------------------------------------
    # Calculate metrics for every service/window
    # --------------------------------------------------

    for window_id in sorted(
        df["window"].unique()
    ):

        window_df = df[
            df["window"] == window_id
        ]

        for service in services:

            service_df = window_df[
                window_df["serviceName"] == service
            ]

            if len(service_df) == 0:
                continue

            # ------------------------------------------
            # Unique traces = request count
            # ------------------------------------------

            requests = (
                service_df["traceID"]
                .nunique()
            )

            # ------------------------------------------
            # Latency
            # ------------------------------------------

            median_latency = (
                service_df["duration"]
                .median()
            )

            p95_latency = (
                service_df["duration"]
                .quantile(0.95)
            )

            # ------------------------------------------
            # Error rate
            # ------------------------------------------

            error_rate = (
                service_df["statusCode"] != 0
            ).mean()

            results.append({

                "case": case,

                "fault_type":
                    (
                        "delay"
                        if "_delay_" in case
                        else "cpu"
                    ),

                "service":
                    service,

                "window_id":
                    window_id,

                "window_start_seconds":
                    window_id * WINDOW_SECONDS,

                "requests":
                    requests,

                "spans":
                    len(service_df),

                "median_latency":
                    median_latency,

                "p95_latency":
                    p95_latency,

                "error_rate":
                    error_rate,
            })

    return pd.DataFrame(results)


# ======================================================
# RUN ALL CASES
# ======================================================

all_results = []

for case in CASES:

    result = analyze_case(case)

    if result is not None:
        all_results.append(result)


if not all_results:

    raise RuntimeError(
        "No baseline data was generated."
    )


baseline = pd.concat(
    all_results,
    ignore_index=True
)


# ======================================================
# SAVE RAW BASELINE WINDOWS
# ======================================================

RAW_OUTPUT = (
    "results/data/baseline_windows_30s.csv"
)

baseline.to_csv(
    RAW_OUTPUT,
    index=False
)


# ======================================================
# CALCULATE BASELINE STATISTICS
# ======================================================

metrics = [
    "requests",
    "median_latency",
    "p95_latency",
    "error_rate",
]


summary = (
    baseline
    .groupby(
        ["fault_type", "service"]
    )[metrics]
    .agg(
        [
            "count",
            "mean",
            "std",
            "min",
            "max"
        ]
    )
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
    240
)

print("\n")
print("=" * 110)
print("BLAST — NORMAL BASELINE VARIABILITY")
print("=" * 110)

print(
    f"Window size: "
    f"{WINDOW_SECONDS} seconds"
)

print(
    f"Baseline windows: "
    f"{baseline['window_id'].nunique()} "
    f"per case approximately"
)

print(
    f"Raw observations: "
    f"{len(baseline)}"
)


# ======================================================
# LATENCY BASELINE
# ======================================================

print("\n")
print("=" * 110)
print("MEDIAN LATENCY BASELINE")
print("=" * 110)

latency_summary = (
    baseline
    .groupby(
        ["fault_type", "service"]
    )["median_latency"]
    .agg(
        [
            "count",
            "mean",
            "std",
            "min",
            "max"
        ]
    )
)

print(
    latency_summary.to_string(
        float_format=lambda x: f"{x:.4f}"
    )
)


# ======================================================
# P95 BASELINE
# ======================================================

print("\n")
print("=" * 110)
print("P95 LATENCY BASELINE")
print("=" * 110)

p95_summary = (
    baseline
    .groupby(
        ["fault_type", "service"]
    )["p95_latency"]
    .agg(
        [
            "count",
            "mean",
            "std",
            "min",
            "max"
        ]
    )
)

print(
    p95_summary.to_string(
        float_format=lambda x: f"{x:.4f}"
    )
)


# ======================================================
# REQUEST VOLUME BASELINE
# ======================================================

print("\n")
print("=" * 110)
print("REQUEST VOLUME BASELINE")
print("=" * 110)

request_summary = (
    baseline
    .groupby(
        ["fault_type", "service"]
    )["requests"]
    .agg(
        [
            "count",
            "mean",
            "std",
            "min",
            "max"
        ]
    )
)

print(
    request_summary.to_string(
        float_format=lambda x: f"{x:.4f}"
    )
)


# ======================================================
# ERROR RATE BASELINE
# ======================================================

print("\n")
print("=" * 110)
print("ERROR RATE BASELINE")
print("=" * 110)

error_summary = (
    baseline
    .groupby(
        ["fault_type", "service"]
    )["error_rate"]
    .agg(
        [
            "count",
            "mean",
            "std",
            "min",
            "max"
        ]
    )
)

print(
    error_summary.to_string(
        float_format=lambda x: f"{x:.6f}"
    )
)


# ======================================================
# CASE-LEVEL LATENCY VARIABILITY
# ======================================================

print("\n")
print("=" * 110)
print("CASE-LEVEL MEDIAN LATENCY VARIABILITY")
print("=" * 110)

case_latency = (
    baseline
    .groupby(
        ["case", "service"]
    )["median_latency"]
    .agg(
        [
            "count",
            "mean",
            "std",
            "min",
            "max"
        ]
    )
)

print(
    case_latency.to_string(
        float_format=lambda x: f"{x:.4f}"
    )
)


# ======================================================
# COEFFICIENT OF VARIATION
# ======================================================

print("\n")
print("=" * 110)
print("LATENCY COEFFICIENT OF VARIATION")
print("=" * 110)

cv = (
    baseline
    .groupby(
        ["case", "service"]
    )["median_latency"]
    .agg(
        ["mean", "std"]
    )
)

cv["coefficient_of_variation"] = (
    cv["std"] / cv["mean"]
)

print(
    cv.to_string(
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
    f"Raw baseline windows: "
    f"{RAW_OUTPUT}"
)

print("\nBaseline variability analysis complete.")