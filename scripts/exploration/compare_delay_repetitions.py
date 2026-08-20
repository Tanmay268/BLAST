import pandas as pd
import numpy as np
from pathlib import Path

CASES = [
    "re2ob_checkoutservice_delay_1",
    "re2ob_checkoutservice_delay_2",
    "re2ob_checkoutservice_delay_3",
]

BASE_DIR = Path("./data")


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
    # Split around injection
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

        normal_median = normal["duration"].median()
        faulty_median = faulty["duration"].median()

        normal_p95 = normal["duration"].quantile(0.95)
        faulty_p95 = faulty["duration"].quantile(0.95)

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

        normal_error_rate = (
            normal["statusCode"] != 0
        ).mean()

        faulty_error_rate = (
            faulty["statusCode"] != 0
        ).mean()

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
        })

    return pd.DataFrame(results)


# ======================================================
# Analyze all cases
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
# Save complete results
# ======================================================

results.to_csv(
    "results/data/checkout_delay_repetitions.csv",
    index=False
)

# ======================================================
# Print compact comparison
# ======================================================

print("\n")
print("=" * 100)
print("CHECKOUTSERVICE DELAY — REPETITION COMPARISON")
print("=" * 100)

comparison = results[
    [
        "case",
        "service",
        "normal_median",
        "faulty_median",
        "median_ratio",
        "normal_p95",
        "faulty_p95",
        "p95_ratio"
    ]
].copy()

print(
    comparison.to_string(
        index=False,
        float_format=lambda x: f"{x:.3f}"
    )
)

# ======================================================
# Root-service summary
# ======================================================

root = results[
    results["service"] == "checkoutservice"
].copy()

print("\n")
print("=" * 100)
print("CHECKOUTSERVICE — ROOT FAULT SUMMARY")
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
            "p95_ratio"
        ]
    ].to_string(
        index=False,
        float_format=lambda x: f"{x:.3f}"
    )
)

# ======================================================
# Downstream services
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
        float_format=lambda x: f"{x:.3f}"
    )
)

# ======================================================
# Average ratios
# ======================================================

print("\n")
print("=" * 100)
print("AVERAGE MEDIAN RATIO ACROSS THREE REPETITIONS")
print("=" * 100)

avg = (
    results
    .groupby("service")["median_ratio"]
    .agg(["mean", "std", "min", "max"])
    .sort_values("mean", ascending=False)
)

print(
    avg.to_string(
        float_format=lambda x: f"{x:.3f}"
    )
)

print("\nResults saved to:")
print("results/data/checkout_delay_repetitions.csv")

print("\nComparison complete.")