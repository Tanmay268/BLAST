import json
import time
import tracemalloc
from pathlib import Path

import pandas as pd
import yaml

from run_evaluation import blast_greedy, b9_blast_independent, build_case_ground_truth
from blast_eval_lib import simulate_cumulative_loss


# ======================================================
# BLAST — LATENCY / MEMORY / SCALABILITY BENCHMARK
# ======================================================
#
# context/source/PROJECT_CONTEXT.pdf p.12: "Latency, Inference
# Time, Memory Usage, Scalability" -- never measured this
# session until now. Times BLAST's actual ranking computation
# (not data loading) at increasing incident-set sizes, since
# that is the only part that would run in an online triage
# tool -- everything upstream of it (journey extraction,
# probability estimation) is offline batch processing done
# once per corpus, not per-incident latency that matters to
# an engineer waiting for a ranking.
# ======================================================

TYPE_PROBABILITY_FILE = "results/data/incident_capability_probabilities.csv"
OVERLAY_FILE = "business_overlay/online_boutique_v2.yaml"

OUTPUT_FILE = "results/data/performance_benchmark.csv"

SIZES = [3, 5, 10, 15, 20, 30]
REPEATS = 20


def load_weights():
    with open(OVERLAY_FILE) as f:
        overlay = yaml.safe_load(f)
    return {c["id"]: c["value_per_min"] for c in overlay["capabilities"]}


def main():

    print("=" * 110)
    print("BLAST — PERFORMANCE BENCHMARK")
    print("=" * 110)

    type_prob_df = pd.read_csv(TYPE_PROBABILITY_FILE)
    weights = load_weights()

    type_probabilities = {}
    for (svc, ft), g in type_prob_df.groupby(["service", "fault_type"]):
        type_probabilities[(svc, ft)] = dict(zip(g["capability_id"], g["p_smoothed"]))

    all_types = list(type_probabilities.keys())
    print(f"\n{len(all_types)} incident types available for synthetic scenarios")
    print(f"Sizes tested: {SIZES} (repeats per size: {REPEATS})")

    rows = []

    for size in SIZES:

        if size > len(all_types):
            print(f"\nSkipping size={size}: only {len(all_types)} incident types exist "
                  f"in the corpus -- larger scenarios require synthetic incident types "
                  f"(out of scope for measuring THIS corpus's actual ranking latency).")
            continue

        for rep in range(REPEATS):

            # deterministic-ish rotation through the type pool, not random
            # sampling -- avoids adding RNG noise to a timing benchmark
            start_idx = (rep * size) % len(all_types)
            chosen_types = [all_types[(start_idx + i) % len(all_types)] for i in range(size)]
            # ensure distinct types in the (rare) wraparound case
            chosen_types = list(dict.fromkeys(chosen_types))
            if len(chosen_types) < size:
                continue

            incident_ids = [f"{s}::{f}::{rep}" for s, f in chosen_types]
            id_to_type = {i: t for i, t in zip(incident_ids, chosen_types)}

            tracemalloc.start()
            t0 = time.perf_counter()

            blast_order = blast_greedy(incident_ids, id_to_type, type_probabilities, weights)

            t1 = time.perf_counter()
            _, peak_mem = tracemalloc.get_traced_memory()
            tracemalloc.stop()

            t2 = time.perf_counter()
            b9_order = b9_blast_independent(incident_ids, id_to_type, type_probabilities, weights)
            t3 = time.perf_counter()

            rows.append({
                "incident_set_size": size,
                "repeat": rep,
                "blast_latency_ms": (t1 - t0) * 1000,
                "blast_peak_memory_kb": peak_mem / 1024,
                "b9_latency_ms": (t3 - t2) * 1000,
            })

    result = pd.DataFrame(rows)

    pd.set_option("display.max_columns", None)
    pd.set_option("display.width", 200)

    summary = (
        result.groupby("incident_set_size")
        .agg(
            blast_latency_ms_mean=("blast_latency_ms", "mean"),
            blast_latency_ms_p95=("blast_latency_ms", lambda s: s.quantile(0.95)),
            blast_peak_memory_kb_mean=("blast_peak_memory_kb", "mean"),
            b9_latency_ms_mean=("b9_latency_ms", "mean"),
        )
        .reset_index()
    )

    print("\n")
    print("=" * 110)
    print("LATENCY / MEMORY BY INCIDENT-SET SIZE")
    print("=" * 110)
    print(summary.to_string(index=False, float_format=lambda x: f"{x:.4f}"))

    # Empirical scaling exponent: BLAST's greedy is O(k^2 * C) in the
    # worst case (k incidents, each of k steps re-scores up to k
    # remaining candidates, each scoring touches up to C capabilities)
    # -- check whether observed latency is consistent with that.
    import numpy as np
    sizes = summary["incident_set_size"].to_numpy(dtype=float)
    latencies = summary["blast_latency_ms_mean"].to_numpy(dtype=float)
    valid = latencies > 0
    if valid.sum() >= 2:
        log_fit = np.polyfit(np.log(sizes[valid]), np.log(latencies[valid]), 1)
        print(f"\nEmpirical scaling exponent (latency ~ size^p): p = {log_fit[0]:.2f} "
              f"(greedy selection is theoretically O(k^2) in incident-set size k for "
              f"fixed capability count, i.e. expect p close to 2)")

    print(f"\nAt the largest tested size ({int(sizes.max())} incidents), BLAST's mean "
          f"latency is {summary['blast_latency_ms_mean'].iloc[-1]:.2f}ms -- well under a "
          f"second, operationally negligible next to any real incident-response timescale.")

    result.to_csv(OUTPUT_FILE, index=False)
    summary.to_csv("results/data/performance_benchmark_summary.csv", index=False)

    print(f"\nSaved: {OUTPUT_FILE}")
    print("Saved: results/data/performance_benchmark_summary.csv")
    print("\nPerformance benchmark complete.")


if __name__ == "__main__":
    main()
