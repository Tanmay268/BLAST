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

# Primary analysis window
WINDOW_SECONDS = 30


# ======================================================
# DETERMINE FAULT TYPE
# ======================================================

def get_fault_type(case):

    if "_delay_" in case:
        return "delay"

    if "_cpu_" in case:
        return "cpu"

    return "unknown"


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

    inject_ms = inject_time * 1000

    # --------------------------------------------------
    # Check whether 30-second matched windows exist
    # --------------------------------------------------

    min_time = df["startTimeMillis"].min()
    max_time = df["startTimeMillis"].max()

    before_seconds = (
        inject_ms - min_time
    ) / 1000

    after_seconds = (
        max_time - inject_ms
    ) / 1000

    if before_seconds < WINDOW_SECONDS:
        print(
            f"Skipping {case}: "
            f"only {before_seconds:.2f}s before injection"
        )
        return None

    if after_seconds < WINDOW_SECONDS:
        print(
            f"Skipping {case}: "
            f"only {after_seconds:.2f}s after injection"
        )
        return None

    # --------------------------------------------------
    # Matched windows
    # --------------------------------------------------

    pre_start = inject_ms - WINDOW_SECONDS * 1000
    pre_end = inject_ms

    post_start = inject_ms
    post_end = inject_ms + WINDOW_SECONDS * 1000

    pre = df[
        (df["startTimeMillis"] >= pre_start) &
        (df["startTimeMillis"] < pre_end)
    ].copy()

    post = df[
        (df["startTimeMillis"] >= post_start) &
        (df["startTimeMillis"] < post_end)
    ].copy()

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
    # Service-level analysis
    # --------------------------------------------------

    for service in services:

        pre_service = pre[
            pre["serviceName"] == service
        ]

        post_service = post[
            post["serviceName"] == service
        ]

        # ----------------------------------------------
        # Skip if either side has no observations
        # ----------------------------------------------

        if (
            len(pre_service) == 0
            or len(post_service) == 0
        ):
            continue

        # ----------------------------------------------
        # REQUEST VOLUME
        #
        # IMPORTANT:
        # One trace can contain many spans.
        #
        # Therefore:
        # request count = unique traceIDs
        # ----------------------------------------------

        pre_requests = (
            pre_service["traceID"]
            .nunique()
        )

        post_requests = (
            post_service["traceID"]
            .nunique()
        )

        request_volume_ratio = (
            post_requests / pre_requests
            if pre_requests > 0
            else np.nan
        )

        # ----------------------------------------------
        # SPAN VOLUME
        #
        # Kept for diagnostic purposes only.
        # NOT treated as request volume.
        # ----------------------------------------------

        pre_spans = len(pre_service)
        post_spans = len(post_service)

        span_volume_ratio = (
            post_spans / pre_spans
            if pre_spans > 0
            else np.nan
        )

        # ----------------------------------------------
        # LATENCY
        # ----------------------------------------------

        pre_median = (
            pre_service["duration"].median()
        )

        post_median = (
            post_service["duration"].median()
        )

        pre_p95 = (
            pre_service["duration"].quantile(0.95)
        )

        post_p95 = (
            post_service["duration"].quantile(0.95)
        )

        median_latency_ratio = (
            post_median / pre_median
            if pre_median > 0
            else np.nan
        )

        p95_latency_ratio = (
            post_p95 / pre_p95
            if pre_p95 > 0
            else np.nan
        )

        # ----------------------------------------------
        # ERROR RATE
        #
        # statusCode == 0 → successful
        # non-zero        → error
        # ----------------------------------------------

        pre_error_rate = (
            pre_service["statusCode"] != 0
        ).mean()

        post_error_rate = (
            post_service["statusCode"] != 0
        ).mean()

        error_rate_change = (
            post_error_rate -
            pre_error_rate
        )

        # ----------------------------------------------
        # Store result
        # ----------------------------------------------

        results.append({

            "case": case,

            "fault_type":
                get_fault_type(case),

            "faulty_service":
                "checkoutservice",

            "service":
                service,

            "window_seconds":
                WINDOW_SECONDS,

            # Request volume
            "pre_requests":
                pre_requests,

            "post_requests":
                post_requests,

            "request_volume_ratio":
                request_volume_ratio,

            # Span volume
            "pre_spans":
                pre_spans,

            "post_spans":
                post_spans,

            "span_volume_ratio":
                span_volume_ratio,

            # Latency
            "pre_median_latency":
                pre_median,

            "post_median_latency":
                post_median,

            "median_latency_ratio":
                median_latency_ratio,

            "pre_p95_latency":
                pre_p95,

            "post_p95_latency":
                post_p95,

            "p95_latency_ratio":
                p95_latency_ratio,

            # Errors
            "pre_error_rate":
                pre_error_rate,

            "post_error_rate":
                post_error_rate,

            "error_rate_change":
                error_rate_change,
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


# ------------------------------------------------------
# Safety check
# ------------------------------------------------------

if not all_results:

    raise RuntimeError(
        "No cases produced usable results."
    )


results = pd.concat(
    all_results,
    ignore_index=True
)


# ======================================================
# SAVE DATASET
# ======================================================

OUTPUT_FILE = (
    "impairment_dataset_30s.csv"
)

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
    240
)


# ======================================================
# BASIC SUMMARY
# ======================================================

print("\n")
print("=" * 110)
print("BLAST — IMPAIRMENT DATASET")
print("=" * 110)

print(
    f"Cases analyzed : "
    f"{results['case'].nunique()}"
)

print(
    f"Services       : "
    f"{results['service'].nunique()}"
)

print(
    f"Window         : "
    f"{WINDOW_SECONDS} seconds"
)

print(
    f"Rows           : "
    f"{len(results)}"
)


# ======================================================
# ROOT SERVICE
# ======================================================

print("\n")
print("=" * 110)
print("ROOT SERVICE — CHECKOUTSERVICE")
print("=" * 110)

root = results[
    results["service"] == "checkoutservice"
]

print(
    root[
        [
            "case",
            "fault_type",
            "pre_requests",
            "post_requests",
            "request_volume_ratio",
            "median_latency_ratio",
            "p95_latency_ratio",
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

print("\n")
print("=" * 110)
print("DOWNSTREAM SERVICE IMPAIRMENT")
print("=" * 110)

downstream = results[
    results["service"] != "checkoutservice"
]

print(
    downstream[
        [
            "case",
            "fault_type",
            "service",
            "pre_requests",
            "post_requests",
            "request_volume_ratio",
            "median_latency_ratio",
            "p95_latency_ratio",
            "error_rate_change"
        ]
    ].to_string(
        index=False,
        float_format=lambda x: f"{x:.4f}"
    )
)


# ======================================================
# FAULT-TYPE SUMMARY
# ======================================================

print("\n")
print("=" * 110)
print("FAULT-TYPE SUMMARY")
print("=" * 110)

summary = (
    results
    .groupby(
        ["fault_type", "service"]
    )[
        [
            "request_volume_ratio",
            "median_latency_ratio",
            "p95_latency_ratio",
            "error_rate_change"
        ]
    ]
    .agg(
        ["mean", "std"]
    )
)

print(
    summary.to_string(
        float_format=lambda x: f"{x:.4f}"
    )
)


# ======================================================
# FINAL
# ======================================================

print("\n")
print("=" * 110)
print("DATASET SAVED")
print("=" * 110)

print(
    f"File: {OUTPUT_FILE}"
)

print("\nImpairment dataset construction complete.")