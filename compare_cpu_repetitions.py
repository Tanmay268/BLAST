import pandas as pd
import numpy as np
from pathlib import Path

# ======================================================
# CONFIGURATION
# ======================================================

CASES = [
    "re2ob_checkoutservice_cpu_1",
    "re2ob_checkoutservice_cpu_2",
    "re2ob_checkoutservice_cpu_3",
]

BASE_DIR = Path("./data")


# ======================================================
# ANALYZE ONE CASE
# ======================================================

def analyze_case(case):

    case_dir = BASE_DIR / case

    trace_file = case_dir / "traces.parquet"
    inject_file = case_dir / "inject_time.txt"

    print(f"\nLoading {case}...")

    df = pd.read_parquet(trace_file)

    with open(inject_file, "r") as f:
        inject_time = int(f.read().strip())

    inject_time_ms = inject_time * 1000

    # --------------------------------------------------
    # Split into normal and faulty periods
    # --------------------------------------------------

    df["period"] = np.where(
        df["startTimeMillis"] < inject_time_ms,
        "normal",
        "faulty"
    )

    services = sorted(
        df["serviceName"]
        .dropna()
        .unique()
    )

    results = []

    for service in services:

        service_df = df[
            df["serviceName"] == service
        ]

        normal = service_df[
            service_df["period"] == "normal"
        ]

        faulty = service_df[
            service_df["period"] == "faulty"
        ]

        if len(normal) == 0 or len(faulty) == 0:
            continue

        # --------------------------------------------------
        # Duration statistics
        # --------------------------------------------------

        normal_median = normal["duration"].median()
        faulty_median = faulty["duration"].median()

        normal_p95 = normal["duration"].quantile(0.95)
        faulty_p95 = faulty["duration"].quantile(0.95)

        # --------------------------------------------------
        # Ratios
        # --------------------------------------------------

        median_ratio = (
            faulty_median / normal_median
            if normal_median > 0
            else np.nan
        )

        p95_ratio = (
            faulty_p95 / normal_p95
            if normal_p95 > 0
            else np.nan
        )

        # --------------------------------------------------
        # Error rates
        # --------------------------------------------------

        normal_error_rate = (
            normal["statusCode"] != 0
        ).mean()

        faulty_error_rate = (
            faulty["statusCode"] != 0
        ).mean()

        error_rate_change = (
            faulty_error_rate -
            normal_error_rate
        )

        results.append({
            "case": case,
            "service": service,

            "normal_spans": len(normal),
            "faulty_spans": len(faulty),

            "normal_median": normal_median,
            "faulty_median": faulty_median,
            "median_ratio": median_ratio,

            "normal_p95": normal_p95,
            "faulty_p95": faulty_p95,
            "p95_ratio": p95_ratio,

            "normal_error_rate": normal_error_rate,
            "faulty_error_rate": faulty_error_rate,
            "error_rate_change": error_rate_change,
        })

    return pd.DataFrame(results)


# ======================================================
# ANALYZE ALL THREE CASES
# ======================================================

all_results = []

for case in CASES:

    result = analyze_case(case)

    all_results.append(result)


results = pd.concat(
    all_results,
    ignore_index=True
)


# ======================================================
# SAVE COMPLETE RESULTS
# ======================================================

OUTPUT_FILE = "checkout_cpu_repetitions.csv"

results.to_csv(
    OUTPUT_FILE,
    index=False
)


# ======================================================
# DISPLAY SETTINGS
# ======================================================

pd.set_option(
    "display.max_columns",
    None
)

pd.set_option(
    "display.width",
    220
)


# ======================================================
# FULL COMPARISON
# ======================================================

print("\n")
print("=" * 100)
print("CHECKOUTSERVICE CPU — REPETITION COMPARISON")
print("=" * 100)

comparison = results[
    [
        "case",
        "service",
        "normal_spans",
        "faulty_spans",
        "normal_median",
        "faulty_median",
        "median_ratio",
        "normal_p95",
        "faulty_p95",
        "p95_ratio",
        "normal_error_rate",
        "faulty_error_rate",
        "error_rate_change"
    ]
].copy()

print(
    comparison.to_string(
        index=False,
        float_format=lambda x: f"{x:.4f}"
    )
)


# ======================================================
# ROOT SERVICE SUMMARY
# ======================================================

root = results[
    results["service"] == "checkoutservice"
].copy()

print("\n")
print("=" * 100)
print("CHECKOUTSERVICE — CPU ROOT FAULT SUMMARY")
print("=" * 100)

print(
    root[
        [
            "case",
            "normal_median",
            "faulty_median",
            "median_ratio",
            "normal_p95",
            "faulty_p95",
            "p95_ratio",
            "normal_error_rate",
            "faulty_error_rate",
            "error_rate_change"
        ]
    ].to_string(
        index=False,
        float_format=lambda x: f"{x:.4f}"
    )
)


# ======================================================
# DOWNSTREAM SERVICES
# ======================================================

downstream_services = [
    "frontendservice",
    "paymentservice",
    "currencyservice",
    "emailservice",
    "productcatalogservice",
    "recommendationservice"
]

downstream = results[
    results["service"].isin(downstream_services)
].copy()


# ======================================================
# DOWNSTREAM MEDIAN RATIOS
# ======================================================

print("\n")
print("=" * 100)
print("DOWNSTREAM SERVICE MEDIAN RATIOS")
print("=" * 100)

pivot = downstream.pivot(
    index="service",
    columns="case",
    values="median_ratio"
)

print(
    pivot.to_string(
        float_format=lambda x: f"{x:.4f}"
    )
)


# ======================================================
# DOWNSTREAM P95 RATIOS
# ======================================================

print("\n")
print("=" * 100)
print("DOWNSTREAM SERVICE P95 RATIOS")
print("=" * 100)

p95_pivot = downstream.pivot(
    index="service",
    columns="case",
    values="p95_ratio"
)

print(
    p95_pivot.to_string(
        float_format=lambda x: f"{x:.4f}"
    )
)


# ======================================================
# AVERAGE MEDIAN RATIO
# ======================================================

print("\n")
print("=" * 100)
print("AVERAGE MEDIAN RATIO ACROSS THREE CPU REPETITIONS")
print("=" * 100)

avg = (
    results
    .groupby("service")["median_ratio"]
    .agg([
        "mean",
        "std",
        "min",
        "max"
    ])
    .sort_values(
        "mean",
        ascending=False
    )
)

print(
    avg.to_string(
        float_format=lambda x: f"{x:.4f}"
    )
)


# ======================================================
# AVERAGE P95 RATIO
# ======================================================

print("\n")
print("=" * 100)
print("AVERAGE P95 RATIO ACROSS THREE CPU REPETITIONS")
print("=" * 100)

avg_p95 = (
    results
    .groupby("service")["p95_ratio"]
    .agg([
        "mean",
        "std",
        "min",
        "max"
    ])
    .sort_values(
        "mean",
        ascending=False
    )
)

print(
    avg_p95.to_string(
        float_format=lambda x: f"{x:.4f}"
    )
)


# ======================================================
# ERROR RATE COMPARISON
# ======================================================

print("\n")
print("=" * 100)
print("AVERAGE ERROR RATE CHANGE")
print("=" * 100)

error_summary = (
    results
    .groupby("service")["error_rate_change"]
    .agg([
        "mean",
        "std",
        "min",
        "max"
    ])
    .sort_values(
        "mean",
        ascending=False
    )
)

print(
    error_summary.to_string(
        float_format=lambda x: f"{x:.6f}"
    )
)


# ======================================================
# FINAL
# ======================================================

print("\n")
print("=" * 100)
print("RESULTS SAVED")
print("=" * 100)

print(f"File: {OUTPUT_FILE}")

print("\nComparison complete.")