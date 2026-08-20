import pandas as pd
import numpy as np
import networkx as nx
from pathlib import Path
from scipy.stats import mannwhitneyu, norm


# ======================================================
# BLAST — PROPAGATION PREVALENCE AUDIT
# ======================================================
#
# context/07_NEXT_PHASE_PLAN.md, Step 3.5. Across every
# case available, what fraction of (fault_type, downstream
# edge) pairs show ANY statistically + practically
# significant downstream impairment? This determines
# whether learned edge transmission probabilities carry
# real signal (RQ2) or are mostly ~0 (in which case the
# structural/propagation half of the contribution is
# secondary to the business-capability set-selection half
# -- decide this now, on evidence, not in week 20).
#
# Supersedes the descriptive ratio-threshold approach in
# build_propagation_observations.py (median>=1.10 OR
# p95>=1.30, no significance test) with the same rigor as
# build_journey_impairment.py: Mann-Whitney U on duration +
# two-proportion test on error rate, Holm-corrected per
# case across its candidate downstream services, gated on
# a practical Cliff's-delta floor.
#
# Auto-discovers cases from data/ (any directory containing
# traces.parquet + inject_time.txt) rather than a hardcoded
# list, so it can be re-run unchanged after the RE2-OB
# expansion (Step 4/7).
# ======================================================

BASE_DIR = Path("./data")
GRAPH_FILE = "service_graph.csv"

OUTPUT_FILE = "propagation_prevalence.csv"
OUTPUT_SUMMARY = "propagation_prevalence_summary.csv"

MIN_WINDOW_SECONDS = 300
MIN_SAMPLES = 10
ALPHA = 0.05
CLIFFS_DELTA_FLOOR = 0.147


# ======================================================
# STATISTICS HELPERS (same as build_journey_impairment.py)
# ======================================================

def cliffs_delta_from_u(u_statistic, n1, n2):
    if n1 == 0 or n2 == 0:
        return np.nan
    return (2.0 * u_statistic) / (n1 * n2) - 1.0


def duration_test(fault_durations, baseline_durations):
    n1, n2 = len(fault_durations), len(baseline_durations)
    if n1 < MIN_SAMPLES or n2 < MIN_SAMPLES:
        return np.nan, np.nan
    if np.all(fault_durations == fault_durations[0]) and \
       np.all(baseline_durations == baseline_durations[0]) and \
       fault_durations[0] == baseline_durations[0]:
        return 1.0, 0.0
    result = mannwhitneyu(fault_durations, baseline_durations, alternative="two-sided")
    return result.pvalue, cliffs_delta_from_u(result.statistic, n1, n2)


def two_proportion_z_test(x1, n1, x2, n2):
    if n1 == 0 or n2 == 0:
        return np.nan
    p1, p2 = x1 / n1, x2 / n2
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
        adj = max((m - rank) * pvalues[idx], prev)
        adj = min(adj, 1.0)
        adjusted[idx] = adj
        prev = adj
    return adjusted


# ======================================================
# DISCOVER CASES
# ======================================================

def discover_cases():
    cases = []
    if not BASE_DIR.exists():
        return cases
    for d in sorted(BASE_DIR.iterdir()):
        if not d.is_dir():
            continue
        if (d / "traces.parquet").exists() and (d / "inject_time.txt").exists():
            cases.append(d.name)
    return cases


def infer_fault_type(case):
    for ft in ["cpu", "delay", "mem", "disk", "socket", "loss"]:
        if f"_{ft}_" in case:
            return ft
    return "unknown"


def infer_target_service(case, known_services):
    # naming convention: {benchmark}_{service}_{fault}_{instance}
    for svc in known_services:
        if f"_{svc}_" in case:
            return svc
    return None


# ======================================================
# LOAD SERVICE GRAPH
# ======================================================

print("=" * 110)
print("BLAST — PROPAGATION PREVALENCE AUDIT")
print("=" * 110)

graph_df = pd.read_csv(GRAPH_FILE)
G = nx.DiGraph()
for _, row in graph_df.iterrows():
    G.add_edge(row["source"], row["target"], calls=row.get("calls", 1))

known_services = sorted(set(G.nodes()))
print(f"\nService graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

cases = discover_cases()
print(f"Discovered {len(cases)} cases with local trace data: {cases}")

if not cases:
    raise RuntimeError(
        "No cases found under ./data with traces.parquet + inject_time.txt. "
        "Run the relevant download script first."
    )


# ======================================================
# PER-CASE, PER-SERVICE SIGNIFICANCE TEST
# ======================================================

all_rows = []

for case in cases:

    fault_type = infer_fault_type(case)
    target_service = infer_target_service(case, known_services)

    if target_service is None:
        print(f"\nWARNING: could not infer target service for {case}; skipping.")
        continue

    if target_service not in G:
        print(f"\nWARNING: {target_service} not in service graph; skipping {case}.")
        continue

    print(f"\nProcessing {case} (target={target_service}, fault={fault_type})...")

    df = pd.read_parquet(BASE_DIR / case / "traces.parquet")

    with open(BASE_DIR / case / "inject_time.txt") as f:
        inject_ms = int(f.read().strip()) * 1000

    min_t, max_t = df["startTimeMillis"].min(), df["startTimeMillis"].max()
    before_seconds = (inject_ms - min_t) / 1000
    after_seconds = (max_t - inject_ms) / 1000
    short_window = before_seconds < MIN_WINDOW_SECONDS or after_seconds < MIN_WINDOW_SECONDS

    df["window"] = np.where(df["startTimeMillis"] < inject_ms, "baseline", "fault")
    df["is_error"] = df["statusCode"] == 2

    descendants = nx.descendants(G, target_service)

    case_rows = []

    for downstream in sorted(descendants):

        try:
            distance = nx.shortest_path_length(G, target_service, downstream)
        except nx.NetworkXNoPath:
            continue

        direct_edge = G.has_edge(target_service, downstream)

        svc_spans = df[df["serviceName"] == downstream]
        baseline = svc_spans[svc_spans["window"] == "baseline"]
        fault = svc_spans[svc_spans["window"] == "fault"]

        n_baseline, n_fault = len(baseline), len(fault)

        baseline_dur = baseline["duration"].to_numpy(dtype=float)
        fault_dur = fault["duration"].to_numpy(dtype=float)

        p_value_duration, cliffs_delta = duration_test(fault_dur, baseline_dur)

        n_baseline_failed = int(baseline["is_error"].sum())
        n_fault_failed = int(fault["is_error"].sum())

        p_value_failure = two_proportion_z_test(
            n_fault_failed, n_fault, n_baseline_failed, n_baseline
        )

        fail_rate_delta = (
            (n_fault_failed / n_fault if n_fault > 0 else np.nan)
            - (n_baseline_failed / n_baseline if n_baseline > 0 else np.nan)
        )

        component_pvalues = [p for p in [p_value_duration, p_value_failure] if not np.isnan(p)]
        p_value_raw = min(1.0, 2 * min(component_pvalues)) if component_pvalues else np.nan

        insufficient_data = (
            n_baseline < MIN_SAMPLES or n_fault < MIN_SAMPLES or short_window
        )

        case_rows.append({
            "case": case,
            "fault_type": fault_type,
            "source": target_service,
            "target": downstream,
            "graph_distance": distance,
            "direct_edge": direct_edge,
            "n_baseline": n_baseline,
            "n_fault": n_fault,
            "p_value_raw": p_value_raw,
            "effect_size": cliffs_delta,
            "fail_rate_delta": fail_rate_delta,
            "insufficient_data": insufficient_data,
        })

    if not case_rows:
        continue

    case_df = pd.DataFrame(case_rows)
    testable = ~case_df["insufficient_data"]
    pvals = case_df["p_value_raw"].where(testable, np.nan).to_numpy()
    case_df["p_value"] = holm_bonferroni(pvals)

    case_df["propagated"] = (
        testable
        & (case_df["p_value"] < ALPHA)
        & (
            (case_df["effect_size"] >= CLIFFS_DELTA_FLOOR)
            | (case_df["fail_rate_delta"] > 0)
        )
    )

    all_rows.append(case_df)

    n_prop = int(case_df["propagated"].sum())
    print(f"  {len(case_df)} downstream edges tested, {n_prop} show propagation")


prevalence = pd.concat(all_rows, ignore_index=True)


# ======================================================
# PREVALENCE SUMMARY
# ======================================================

pd.set_option("display.max_columns", None)
pd.set_option("display.width", 240)

print("\n")
print("=" * 110)
print("PROPAGATION PREVALENCE — RAW RESULTS")
print("=" * 110)

print(
    prevalence[[
        "case", "fault_type", "source", "target", "graph_distance", "direct_edge",
        "n_baseline", "n_fault", "p_value", "effect_size", "propagated", "insufficient_data",
    ]].to_string(index=False, float_format=lambda x: f"{x:.4g}")
)

testable_prevalence = prevalence[~prevalence["insufficient_data"]]

overall_prevalence = testable_prevalence["propagated"].mean()

by_fault_type = (
    testable_prevalence
    .groupby("fault_type")["propagated"]
    .agg(["count", "sum", "mean"])
    .rename(columns={"count": "edges_tested", "sum": "edges_propagated", "mean": "prevalence"})
    .reset_index()
)

by_distance = (
    testable_prevalence
    .groupby(["fault_type", "graph_distance"])["propagated"]
    .agg(["count", "sum", "mean"])
    .rename(columns={"count": "edges_tested", "sum": "edges_propagated", "mean": "prevalence"})
    .reset_index()
)

by_direct = (
    testable_prevalence
    .groupby(["fault_type", "direct_edge"])["propagated"]
    .agg(["count", "sum", "mean"])
    .rename(columns={"count": "edges_tested", "sum": "edges_propagated", "mean": "prevalence"})
    .reset_index()
)

print("\n")
print("=" * 110)
print("PREVALENCE BY FAULT TYPE")
print("=" * 110)
print(by_fault_type.to_string(index=False, float_format=lambda x: f"{x:.4f}"))

print("\n")
print("=" * 110)
print("PREVALENCE BY GRAPH DISTANCE")
print("=" * 110)
print(by_distance.to_string(index=False, float_format=lambda x: f"{x:.4f}"))

print("\n")
print("=" * 110)
print("PREVALENCE: DIRECT VS INDIRECT EDGES")
print("=" * 110)
print(by_direct.to_string(index=False, float_format=lambda x: f"{x:.4f}"))

print("\n")
print("=" * 110)
print("HEADLINE FINDING")
print("=" * 110)

print(f"\nOverall propagation prevalence: {overall_prevalence:.1%} "
      f"({int(testable_prevalence['propagated'].sum())}/{len(testable_prevalence)} testable edges)")

if overall_prevalence >= 0.5:
    reading = (
        "HIGH prevalence -- the full BLAST propagation story (learned transmission "
        "probabilities carrying real signal, RQ2) is supported. The structural/graph "
        "half of the contribution remains load-bearing."
    )
else:
    reading = (
        "LOW prevalence -- most (fault, downstream-edge) pairs show no significant "
        "propagation. The contribution should rest primarily on the business-capability "
        "set-selection half; multi-hop propagation should be reframed as a secondary "
        "component, and RQ2 should be answered honestly as a negative/mixed result "
        "with characterisation of WHEN propagation occurs (fault type, distance)."
    )

print(f"\n{reading}")


# ======================================================
# SAVE
# ======================================================

prevalence.to_csv(OUTPUT_FILE, index=False)

summary = by_fault_type.copy()
summary.to_csv(OUTPUT_SUMMARY, index=False)

print("\n")
print("=" * 110)
print("FILES SAVED")
print("=" * 110)

print(OUTPUT_FILE)
print(OUTPUT_SUMMARY)

print("\nPropagation prevalence audit complete.")
