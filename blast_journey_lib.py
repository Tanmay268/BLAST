import pandas as pd
import numpy as np
from pathlib import Path
from scipy.stats import mannwhitneyu, norm


# ======================================================
# BLAST — SHARED JOURNEY-EXTRACTION / SIGNIFICANCE LIBRARY
# ======================================================
#
# Extracted from build_journey_impairment.py (the validated
# 6-case pilot script, ADR-014/015, Gate 2a PASSED) so the
# full RE2-OB batch pipeline (run_full_re2ob_pipeline.py)
# uses IDENTICAL attribution logic -- no drift between the
# pilot result already reported and the corpus-scale run.
#
# See JOURNEY_TYPING_RULE.md for the rationale.
# ======================================================

MIN_WINDOW_SECONDS = 300
MIN_JOURNEY_SAMPLES = 10
ALPHA = 0.05
CLIFFS_DELTA_FLOOR = 0.147

NOISE_OPERATION_SUBSTRINGS = [
    "Health/Check",
    "TraceService/Export",
]

GENERIC_ROOT_OPERATIONS = {"frontend"}

JOURNEY_LABELS = {
    frozenset(["Convert", "GetAds", "GetCart", "GetProduct",
               "GetSupportedCurrencies", "ListRecommendations"]):
        "Product Detail View",
    frozenset(["Convert", "GetCart", "GetProduct", "GetQuote",
               "GetSupportedCurrencies", "ListRecommendations"]):
        "Cart View",
    frozenset(["AddItem", "GetProduct"]):
        "Add To Cart",
    frozenset(["Convert", "GetAds", "GetCart",
               "GetSupportedCurrencies", "ListProducts"]):
        "Home Page View",
    frozenset(["GetProduct", "GetSupportedCurrencies",
               "ListRecommendations", "PlaceOrder"]):
        "Place Order",
}


# ======================================================
# STATISTICS HELPERS
# ======================================================

def cliffs_delta_from_u(u_statistic, n1, n2):
    if n1 == 0 or n2 == 0:
        return np.nan
    return (2.0 * u_statistic) / (n1 * n2) - 1.0


def duration_test(fault_durations, baseline_durations):

    n1 = len(fault_durations)
    n2 = len(baseline_durations)

    if n1 < MIN_JOURNEY_SAMPLES or n2 < MIN_JOURNEY_SAMPLES:
        return np.nan, np.nan

    if np.all(fault_durations == fault_durations[0]) and \
       np.all(baseline_durations == baseline_durations[0]) and \
       fault_durations[0] == baseline_durations[0]:
        return 1.0, 0.0

    result = mannwhitneyu(fault_durations, baseline_durations, alternative="two-sided")
    delta = cliffs_delta_from_u(result.statistic, n1, n2)

    return result.pvalue, delta


def two_proportion_z_test(x1, n1, x2, n2):

    if n1 == 0 or n2 == 0:
        return np.nan

    p1 = x1 / n1
    p2 = x2 / n2
    p_pool = (x1 + x2) / (n1 + n2)

    if p_pool in (0.0, 1.0):
        return 1.0

    se = np.sqrt(p_pool * (1 - p_pool) * (1 / n1 + 1 / n2))

    if se == 0:
        return 1.0

    z = (p1 - p2) / se

    return 2 * (1 - norm.cdf(abs(z)))


def holm_bonferroni(pvalues):

    pvalues = np.asarray(pvalues, dtype=float)
    adjusted = np.full(len(pvalues), np.nan)

    valid_idx = np.where(~np.isnan(pvalues))[0]

    if len(valid_idx) == 0:
        return adjusted

    order = valid_idx[np.argsort(pvalues[valid_idx])]
    m = len(order)

    prev = 0.0

    for rank, idx in enumerate(order):
        adj = (m - rank) * pvalues[idx]
        adj = max(adj, prev)
        adj = min(adj, 1.0)
        adjusted[idx] = adj
        prev = adj

    return adjusted


# ======================================================
# JOURNEY EXTRACTION FOR ONE CASE
# ======================================================

def extract_journeys(case, case_dir, faulty_service, fault_type):
    """case_dir: Path to the directory containing traces.parquet
    and inject_time.txt for this case. faulty_service/fault_type
    passed explicitly (caller determines these from the case
    naming convention or a manifest, not re-derived here)."""

    trace_file = case_dir / "traces.parquet"
    inject_file = case_dir / "inject_time.txt"

    df = pd.read_parquet(trace_file)

    with open(inject_file, "r") as f:
        inject_time = int(f.read().strip())

    inject_ms = inject_time * 1000

    min_t = df["startTimeMillis"].min()
    max_t = df["startTimeMillis"].max()

    before_seconds = (inject_ms - min_t) / 1000
    after_seconds = (max_t - inject_ms) / 1000

    short_window = (
        before_seconds < MIN_WINDOW_SECONDS
        or after_seconds < MIN_WINDOW_SECONDS
    )

    roots = df[df["parentSpanID"].isna()].copy()

    noise_mask = pd.Series(False, index=roots.index)
    for pattern in NOISE_OPERATION_SUBSTRINGS:
        noise_mask |= roots["operationName"].str.contains(pattern, na=False)

    journey_roots = roots[~noise_mask].copy()

    wrapper_roots = journey_roots[
        journey_roots["operationName"].isin(GENERIC_ROOT_OPERATIONS)
    ]

    wrapper_trace_to_root_span = dict(
        zip(wrapper_roots["traceID"], wrapper_roots["spanID"])
    )
    wrapper_trace_ids = set(wrapper_trace_to_root_span)

    candidates = df[
        df["traceID"].isin(wrapper_trace_ids)
        & df["parentSpanID"].notna()
    ].copy()

    candidates["root_span_id"] = candidates["traceID"].map(wrapper_trace_to_root_span)

    direct_children = candidates[
        candidates["parentSpanID"].astype(str)
        == candidates["root_span_id"].astype(str)
    ]

    signature_by_trace = (
        direct_children.groupby("traceID")["methodName"]
        .apply(lambda s: tuple(sorted(set(s.dropna().astype(str)))))
        .to_dict()
    )

    def classify(row):

        if row["operationName"] in GENERIC_ROOT_OPERATIONS:
            signature = signature_by_trace.get(row["traceID"], tuple())
            type_id = "frontend::" + ("+".join(signature) if signature else "empty")
            label = JOURNEY_LABELS.get(frozenset(signature), type_id)
            return type_id, label, signature

        type_id = f"orphaned::{row['operationName']}"
        label = f"{row['operationName']} (orphaned root)"
        own_method = (row["methodName"],) if pd.notna(row["methodName"]) else tuple()

        return type_id, label, own_method

    classified = journey_roots.apply(lambda r: classify(r), axis=1, result_type="expand")

    journey_roots["journey_type_id"] = classified[0]
    journey_roots["journey_label"] = classified[1]
    journey_roots["signature"] = classified[2]

    any_error = (
        df.assign(is_error=(df["statusCode"] == 2))
        .groupby("traceID")["is_error"]
        .any()
    )

    journey_roots["any_error"] = journey_roots["traceID"].map(any_error)

    journey_roots["window"] = np.where(
        journey_roots["startTimeMillis"] < inject_ms, "baseline", "fault"
    )

    journey_roots["case"] = case
    journey_roots["fault_type"] = fault_type
    journey_roots["faulty_service"] = faulty_service
    journey_roots["before_seconds_available"] = before_seconds
    journey_roots["after_seconds_available"] = after_seconds
    journey_roots["short_window"] = short_window

    return journey_roots[[
        "case", "fault_type", "faulty_service",
        "traceID", "journey_type_id", "journey_label", "signature",
        "duration", "any_error", "window",
        "before_seconds_available", "after_seconds_available",
        "short_window",
    ]]


# ======================================================
# PER-CASE, PER-JOURNEY-TYPE SIGNIFICANCE TESTING
# ======================================================

def summarize_case(journeys):

    case = journeys["case"].iloc[0]
    fault_type = journeys["fault_type"].iloc[0]
    faulty_service = journeys["faulty_service"].iloc[0]
    short_window = bool(journeys["short_window"].iloc[0])
    before_seconds = journeys["before_seconds_available"].iloc[0]
    after_seconds = journeys["after_seconds_available"].iloc[0]

    rows = []

    for journey_type_id, group in journeys.groupby("journey_type_id"):

        label = group["journey_label"].iloc[0]

        baseline = group[group["window"] == "baseline"]
        fault = group[group["window"] == "fault"]

        n_baseline = len(baseline)
        n_fault = len(fault)

        baseline_dur = baseline["duration"].to_numpy(dtype=float)
        fault_dur = fault["duration"].to_numpy(dtype=float)

        def q(arr, p):
            return float(np.quantile(arr, p)) if len(arr) > 0 else np.nan

        baseline_p50, baseline_p95, baseline_p99 = (
            q(baseline_dur, 0.50), q(baseline_dur, 0.95), q(baseline_dur, 0.99)
        )
        fault_p50, fault_p95, fault_p99 = (
            q(fault_dur, 0.50), q(fault_dur, 0.95), q(fault_dur, 0.99)
        )

        p95_ratio = (
            fault_p95 / baseline_p95
            if baseline_p95 and baseline_p95 > 0
            else np.nan
        )

        baseline_throughput = n_baseline / before_seconds if before_seconds > 0 else np.nan
        fault_throughput = n_fault / after_seconds if after_seconds > 0 else np.nan

        if not np.isnan(baseline_p99):
            baseline_degraded_rate = float((baseline_dur > baseline_p99).mean()) if n_baseline > 0 else np.nan
            fault_degraded_rate = float((fault_dur > baseline_p99).mean()) if n_fault > 0 else np.nan
        else:
            baseline_degraded_rate = np.nan
            fault_degraded_rate = np.nan

        degraded_rate_delta = (
            fault_degraded_rate - baseline_degraded_rate
            if not np.isnan(fault_degraded_rate) and not np.isnan(baseline_degraded_rate)
            else np.nan
        )

        n_baseline_failed = int(baseline["any_error"].sum())
        n_fault_failed = int(fault["any_error"].sum())

        baseline_fail_rate = n_baseline_failed / n_baseline if n_baseline > 0 else np.nan
        fault_fail_rate = n_fault_failed / n_fault if n_fault > 0 else np.nan

        fail_rate_delta = (
            fault_fail_rate - baseline_fail_rate
            if not np.isnan(fault_fail_rate) and not np.isnan(baseline_fail_rate)
            else np.nan
        )

        p_value_duration, cliffs_delta = duration_test(fault_dur, baseline_dur)

        p_value_failure = two_proportion_z_test(
            n_fault_failed, n_fault, n_baseline_failed, n_baseline
        )

        component_pvalues = [
            p for p in [p_value_duration, p_value_failure] if not np.isnan(p)
        ]

        p_value_raw = min(1.0, 2 * min(component_pvalues)) if component_pvalues else np.nan

        insufficient_data = (
            n_baseline < MIN_JOURNEY_SAMPLES
            or n_fault < MIN_JOURNEY_SAMPLES
            or short_window
        )

        magnitude = 0.0
        if not np.isnan(cliffs_delta):
            magnitude += max(cliffs_delta, 0.0)
        if not np.isnan(fail_rate_delta):
            magnitude += max(fail_rate_delta, 0.0)

        rows.append({
            "case": case,
            "fault_type": fault_type,
            "target_service": faulty_service,
            "journey_type": journey_type_id,
            "journey_label": label,
            "signature": "+".join(group["signature"].iloc[0]),
            "n_baseline": n_baseline,
            "n_fault": n_fault,
            "baseline_p50": baseline_p50,
            "baseline_p95": baseline_p95,
            "baseline_p99": baseline_p99,
            "fault_p50": fault_p50,
            "fault_p95": fault_p95,
            "fault_p99": fault_p99,
            "p95_ratio": p95_ratio,
            "baseline_throughput": baseline_throughput,
            "fault_throughput": fault_throughput,
            "baseline_degraded_rate": baseline_degraded_rate,
            "fault_degraded_rate": fault_degraded_rate,
            "degraded_rate_delta": degraded_rate_delta,
            "baseline_fail_rate": baseline_fail_rate,
            "fault_fail_rate": fault_fail_rate,
            "fail_rate_delta": fail_rate_delta,
            "p_value_raw": p_value_raw,
            "effect_size": cliffs_delta,
            "impairment_magnitude": magnitude,
            "insufficient_data": insufficient_data,
            "short_window": short_window,
        })

    case_df = pd.DataFrame(rows)

    testable = ~case_df["insufficient_data"]

    pvals = case_df["p_value_raw"].where(testable, np.nan).to_numpy()
    case_df["p_value"] = holm_bonferroni(pvals)

    case_df["impaired"] = (
        testable
        & (case_df["p_value"] < ALPHA)
        & (
            (case_df["effect_size"] >= CLIFFS_DELTA_FLOOR)
            | (case_df["fail_rate_delta"] > 0)
        )
    )

    return case_df
