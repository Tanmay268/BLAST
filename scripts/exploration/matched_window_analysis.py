import pandas as pd
import numpy as np
from pathlib import Path

CASES = [
    "re2ob_checkoutservice_delay_1",
    "re2ob_checkoutservice_delay_2",
    "re2ob_checkoutservice_delay_3",
    "re2ob_checkoutservice_cpu_1",
    "re2ob_checkoutservice_cpu_2",
    "re2ob_checkoutservice_cpu_3",
]

WINDOWS = [10, 30, 60, 120, 300]

BASE_DIR = Path("./data")


def analyze_case(case, window):

    case_dir = BASE_DIR / case

    df = pd.read_parquet(
        case_dir / "traces.parquet"
    )

    with open(case_dir / "inject_time.txt") as f:
        inject_time = int(f.read().strip())

    inject_ms = inject_time * 1000

    min_time = df["startTimeMillis"].min()
    max_time = df["startTimeMillis"].max()

    # --------------------------------------------------
    # Check whether equal windows are available
    # --------------------------------------------------

    before_seconds = (
        inject_ms - min_time
    ) / 1000

    after_seconds = (
        max_time - inject_ms
    ) / 1000

    if before_seconds < window or after_seconds < window:
        return None

    # --------------------------------------------------
    # Matched windows
    # --------------------------------------------------

    pre_start = inject_ms - window * 1000
    pre_end = inject_ms

    post_start = inject_ms
    post_end = inject_ms + window * 1000

    pre = df[
        (df["startTimeMillis"] >= pre_start) &
        (df["startTimeMillis"] < pre_end)
    ]

    post = df[
        (df["startTimeMillis"] >= post_start) &
        (df["startTimeMillis"] < post_end)
    ]

    results = []

    services = sorted(
        df["serviceName"]
        .dropna()
        .unique()
    )

    for service in services:

        normal = pre[
            pre["serviceName"] == service
        ]

        faulty = post[
            post["serviceName"] == service
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

        normal_error = (
            normal["statusCode"] != 0
        ).mean()

        faulty_error = (
            faulty["statusCode"] != 0
        ).mean()

        results.append({
            "case": case,
            "window_seconds": window,
            "service": service,

            "pre_spans": len(normal),
            "post_spans": len(faulty),

            "pre_median": normal_median,
            "post_median": faulty_median,
            "median_ratio": median_ratio,

            "pre_p95": normal_p95,
            "post_p95": faulty_p95,
            "p95_ratio": p95_ratio,

            "pre_error_rate": normal_error,
            "post_error_rate": faulty_error,

            "error_rate_change":
                faulty_error - normal_error
        })

    return pd.DataFrame(results)


# ======================================================
# RUN ANALYSIS
# ======================================================

all_results = []

for case in CASES:

    for window in WINDOWS:

        print(
            f"Analyzing {case} "
            f"with {window}s window..."
        )

        result = analyze_case(
            case,
            window
        )

        if result is not None:
            all_results.append(result)


results = pd.concat(
    all_results,
    ignore_index=True
)

# ======================================================
# SAVE
# ======================================================

OUTPUT = "results/data/matched_window_results.csv"

results.to_csv(
    OUTPUT,
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
    220
)

print("\n" + "=" * 100)
print("MATCHED-WINDOW ANALYSIS")
print("=" * 100)

print(
    results.to_string(
        index=False,
        float_format=lambda x: f"{x:.4f}"
    )
)

# ======================================================
# ROOT SERVICE SUMMARY
# ======================================================

root = results[
    results["service"] == "checkoutservice"
]

print("\n" + "=" * 100)
print("CHECKOUTSERVICE — WINDOW SENSITIVITY")
print("=" * 100)

print(
    root[
        [
            "case",
            "window_seconds",
            "pre_spans",
            "post_spans",
            "median_ratio",
            "p95_ratio"
        ]
    ].to_string(
        index=False,
        float_format=lambda x: f"{x:.4f}"
    )
)

# ======================================================
# DOWNSTREAM SUMMARY
# ======================================================

downstream = results[
    results["service"] != "checkoutservice"
]

print("\n" + "=" * 100)
print("DOWNSTREAM MEDIAN RATIOS")
print("=" * 100)

print(
    downstream[
        [
            "case",
            "window_seconds",
            "service",
            "median_ratio",
            "p95_ratio"
        ]
    ].to_string(
        index=False,
        float_format=lambda x: f"{x:.4f}"
    )
)

print("\nResults saved to:")
print(OUTPUT)