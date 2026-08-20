import pandas as pd
import numpy as np

TRACE_FILE = r".\data\re2ob_checkoutservice_delay_1\traces.parquet"
INJECT_FILE = r".\data\re2ob_checkoutservice_delay_1\inject_time.txt"

print("=" * 80)
print("BLAST — FAULT IMPACT INSPECTION")
print("=" * 80)

# --------------------------------------------------
# 1. Load data
# --------------------------------------------------

df = pd.read_parquet(TRACE_FILE)

with open(INJECT_FILE, "r") as f:
    inject_time = int(f.read().strip())

print(f"\nTotal spans: {len(df):,}")
print(f"Injection time: {inject_time}")

# --------------------------------------------------
# 2. Create normal / faulty periods
# --------------------------------------------------
#
# startTimeMillis is milliseconds
# inject_time is Unix timestamp in seconds
# --------------------------------------------------

inject_time_ms = inject_time * 1000

df["period"] = np.where(
    df["startTimeMillis"] < inject_time_ms,
    "normal",
    "faulty"
)

print("\n" + "=" * 80)
print("PERIOD DISTRIBUTION")
print("=" * 80)

print(df["period"].value_counts())

# --------------------------------------------------
# 3. Basic service-level impact
# --------------------------------------------------

print("\n" + "=" * 80)
print("SERVICE-LEVEL IMPACT")
print("=" * 80)

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

    # ----------------------------------------------
    # Basic counts
    # ----------------------------------------------

    normal_count = len(normal)
    faulty_count = len(faulty)

    # ----------------------------------------------
    # Duration statistics
    # ----------------------------------------------

    normal_median = (
        normal["duration"].median()
        if normal_count > 0 else np.nan
    )

    faulty_median = (
        faulty["duration"].median()
        if faulty_count > 0 else np.nan
    )

    normal_p95 = (
        normal["duration"].quantile(0.95)
        if normal_count > 0 else np.nan
    )

    faulty_p95 = (
        faulty["duration"].quantile(0.95)
        if faulty_count > 0 else np.nan
    )

    # ----------------------------------------------
    # Latency ratios
    # ----------------------------------------------

    if normal_median > 0:
        median_ratio = (
            faulty_median / normal_median
        )
    else:
        median_ratio = np.nan

    if normal_p95 > 0:
        p95_ratio = (
            faulty_p95 / normal_p95
        )
    else:
        p95_ratio = np.nan

    # ----------------------------------------------
    # Error rates
    #
    # RCAEval statusCode:
    # 0 = OK
    # non-zero = error
    # ----------------------------------------------

    normal_error_rate = (
        (normal["statusCode"] != 0).mean()
        if normal_count > 0
        else np.nan
    )

    faulty_error_rate = (
        (faulty["statusCode"] != 0).mean()
        if faulty_count > 0
        else np.nan
    )

    error_rate_change = (
        faulty_error_rate -
        normal_error_rate
        if not np.isnan(normal_error_rate)
        and not np.isnan(faulty_error_rate)
        else np.nan
    )

    results.append({
        "service": service,
        "normal_spans": normal_count,
        "faulty_spans": faulty_count,
        "normal_median": normal_median,
        "faulty_median": faulty_median,
        "median_ratio": median_ratio,
        "normal_p95": normal_p95,
        "faulty_p95": faulty_p95,
        "p95_ratio": p95_ratio,
        "normal_error_rate": normal_error_rate,
        "faulty_error_rate": faulty_error_rate,
        "error_rate_change": error_rate_change
    })

# --------------------------------------------------
# 4. Display results
# --------------------------------------------------

results_df = pd.DataFrame(results)

pd.set_option(
    "display.max_columns",
    None
)

pd.set_option(
    "display.width",
    200
)

print(
    results_df.to_string(
        index=False,
        float_format=lambda x: f"{x:.4f}"
    )
)

# --------------------------------------------------
# 5. Sort by latency change
# --------------------------------------------------

print("\n" + "=" * 80)
print("SERVICES SORTED BY MEDIAN LATENCY RATIO")
print("=" * 80)

print(
    results_df
    .sort_values(
        "median_ratio",
        ascending=False
    )
    .to_string(
        index=False,
        float_format=lambda x: f"{x:.4f}"
    )
)

# --------------------------------------------------
# 6. Save results
# --------------------------------------------------

OUTPUT_FILE = "fault_impact_checkout_delay_1.csv"

results_df.to_csv(
    OUTPUT_FILE,
    index=False
)

print(
    f"\nSaved results to: {OUTPUT_FILE}"
)

print("\nInspection complete.")