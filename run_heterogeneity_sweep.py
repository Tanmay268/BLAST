from pathlib import Path

import numpy as np
import pandas as pd
import yaml
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from blast_eval_lib import (
    simulate_cumulative_loss, normalized_aulc, ndcg_at_k,
    cliffs_delta, paired_wilcoxon, holm_bonferroni,
)


# ======================================================
# BLAST — SYNTHETIC-TOPOLOGY HETEROGENEITY SWEEP
# ======================================================
#
# context/07_NEXT_PHASE_PLAN.md §4 (the pre-committed
# pivot), executed following ADR-019's Gate 4 finding:
# BLAST beats its independent-scoring ablation (B9) on
# ranking quality (NDCG@5) but not, practically, on
# Cumulative Business Loss -- traced to RCAEval's Online
# Boutique having near-identical capability FOOTPRINTS
# within a target service across all fault types (only the
# PROBABILITY/magnitude varies). This turns "it didn't work
# on CBL" into a falsifiable, predictive question: at what
# level of footprint heterogeneity DOES set-selection start
# winning on CBL?
#
# ------------------------------------------------------
# GENERATIVE MODEL
# ------------------------------------------------------
# Mirrors the REAL structure found in the corpus exactly,
# with one parameter exposed: heterogeneity h in [0,1].
#
# - N_SERVICES services, each "owns" a capability footprint
#   = a SHARED CORE (same capabilities for every service,
#   size = C*(1-h)) UNION a PRIVATE slice unique to that
#   service (the remaining C*h capabilities, partitioned
#   disjointly across services).
#     h=0: every service's footprint is identical (exactly
#          what ADR-019 found in the real corpus).
#     h=1: every service's footprint is fully disjoint from
#          every other service's.
# - Within a service, each (service, fault_type) incident
#   TYPE's per-capability probability is dominated by a
#   single fault-severity draw shared across that type's
#   whole footprint (mirrors the real finding: probability
#   varies mostly by FAULT, not by which capability).
# - Ground truth = the same probability used as BLAST's
#   model input. This is a deliberate simplification for
#   isolating the footprint-heterogeneity effect in
#   isolation: the real evaluation (run_evaluation.py)
#   already tested the separate question of estimation
#   noise/generalisation (train/test split, B7). This study
#   is scoped to structural heterogeneity only.
# - Weights: the REAL overlay's declared value_per_min,
#   fixed across the whole sweep, for direct comparability
#   with the real Gate 4 numbers.
# ======================================================

OVERLAY_FILE = "business_overlay/online_boutique_v2.yaml"

N_SERVICES = 5
N_FAULT_TYPES = 6
HETEROGENEITY_LEVELS = np.round(np.linspace(0.0, 1.0, 11), 2)
N_REPETITIONS_PER_LEVEL = 20
SCENARIOS_PER_K_PER_REP = 10
K_VALUES = [3, 5, 10]
SEED = 20260820
CLIFFS_DELTA_FLOOR = 0.147
ALPHA = 0.05

OUTPUT_SWEEP = "heterogeneity_sweep_results.csv"
OUTPUT_PLOT = "results/figures/heterogeneity_sweep.png"


def load_weights_and_capabilities():
    with open(OVERLAY_FILE) as f:
        overlay = yaml.safe_load(f)
    capability_ids = [c["id"] for c in overlay["capabilities"]]
    weights = {c["id"]: c["value_per_min"] for c in overlay["capabilities"]}
    return capability_ids, weights


def generate_footprints(capability_ids, heterogeneity, rng):
    """Returns {service_index: set(capability_ids)}."""

    C = len(capability_ids)
    core_size = int(round(C * (1 - heterogeneity)))

    shuffled = list(capability_ids)
    rng.shuffle(shuffled)

    core_caps = set(shuffled[:core_size])
    private_pool = shuffled[core_size:]

    footprints = {s: set(core_caps) for s in range(N_SERVICES)}

    for idx, cap in enumerate(private_pool):
        footprints[idx % N_SERVICES].add(cap)

    return footprints


def generate_incident_types(footprints, rng):
    """Returns {(service_idx, fault_idx): {capability_id: p}}."""

    types = {}

    for svc in range(N_SERVICES):
        for fault in range(N_FAULT_TYPES):

            severity = rng.uniform(0.15, 0.95)

            p_by_cap = {}
            for cap in footprints[svc]:
                jitter = rng.normal(0, 0.05)
                p_by_cap[cap] = float(np.clip(severity + jitter, 0.01, 0.99))

            types[(svc, fault)] = p_by_cap

    return types


def blast_greedy_order(incident_ids, id_to_type, incident_types, weights):

    def F(selected):
        all_caps = set()
        for i in selected:
            all_caps.update(incident_types[id_to_type[i]].keys())
        total = 0.0
        for c in all_caps:
            prob_none = 1.0
            for i in selected:
                p = incident_types[id_to_type[i]].get(c, 0.0)
                prob_none *= (1.0 - p)
            total += weights.get(c, 1.0) * (1.0 - prob_none)
        return total

    remaining = list(incident_ids)
    selected = []
    while remaining:
        current = F(selected)
        gains = [(i, F(selected + [i]) - current) for i in remaining]
        gains.sort(key=lambda x: (-x[1], x[0]))
        winner = gains[0][0]
        selected.append(winner)
        remaining.remove(winner)
    return selected


def b9_independent_order(incident_ids, id_to_type, incident_types, weights):
    score = {}
    for i in incident_ids:
        p_by_cap = incident_types[id_to_type[i]]
        score[i] = sum(weights.get(c, 1.0) * p for c, p in p_by_cap.items())
    return sorted(incident_ids, key=lambda i: (-score[i], i))


def oracle_order(incident_ids, incident_capabilities, weights):

    def coverage_value(selected):
        all_caps = set()
        for i in selected:
            all_caps.update(incident_capabilities[i].keys())
        total = 0.0
        for c in all_caps:
            total += weights.get(c, 1.0) * max(incident_capabilities[i].get(c, 0.0) for i in selected)
        return total

    remaining = list(incident_ids)
    selected = []
    while remaining:
        current = coverage_value(selected) if selected else 0.0
        best_i, best_gain = None, -np.inf
        for i in remaining:
            gain = coverage_value(selected + [i]) - current
            if gain > best_gain or (gain == best_gain and (best_i is None or i < best_i)):
                best_gain, best_i = gain, i
        selected.append(best_i)
        remaining.remove(best_i)
    return selected


def run_one_repetition(heterogeneity, rep_seed, capability_ids, weights):

    rng = np.random.default_rng(rep_seed)

    footprints = generate_footprints(capability_ids, heterogeneity, rng)
    incident_types = generate_incident_types(footprints, rng)

    all_type_keys = list(incident_types.keys())

    # Each "incident occurrence" for scenario purposes is just
    # the type itself here (no repetitions needed -- there is
    # no estimation-noise question in this study, see module
    # docstring).
    id_to_type = {f"{s}::{f}": (s, f) for s, f in all_type_keys}
    incident_ids_all = list(id_to_type.keys())
    incident_capabilities_gt = {i: incident_types[id_to_type[i]] for i in incident_ids_all}

    rows = []

    for k in K_VALUES:

        k_eff = min(k, len(incident_ids_all))

        # Direct sampling without replacement, not full
        # enumeration -- C(30,10) is ~30 million, too many to
        # materialise. Scenarios within a (heterogeneity, rep)
        # combo may occasionally repeat; negligible given 11
        # levels x 20 reps x several scenarios each already
        # gives ample independent draws overall.
        seen = set()
        scenarios_this_k = []
        attempts = 0
        while len(scenarios_this_k) < SCENARIOS_PER_K_PER_REP and attempts < SCENARIOS_PER_K_PER_REP * 20:
            attempts += 1
            draw = tuple(sorted(rng.choice(incident_ids_all, size=k_eff, replace=False)))
            if draw in seen:
                continue
            seen.add(draw)
            scenarios_this_k.append(draw)

        for draw in scenarios_this_k:

            incident_ids = list(draw)

            blast_order = blast_greedy_order(incident_ids, id_to_type, incident_types, weights)
            b9_order = b9_independent_order(incident_ids, id_to_type, incident_types, weights)
            oracle = oracle_order(incident_ids, incident_capabilities_gt, weights)

            gt_loss = {
                i: sum(weights.get(c, 1.0) * m for c, m in incident_capabilities_gt[i].items())
                for i in incident_ids
            }

            _, cbl_blast = simulate_cumulative_loss(blast_order, incident_capabilities_gt, weights)
            _, cbl_b9 = simulate_cumulative_loss(b9_order, incident_capabilities_gt, weights)
            _, cbl_oracle = simulate_cumulative_loss(oracle, incident_capabilities_gt, weights)

            ndcg_blast = ndcg_at_k(blast_order, gt_loss, min(5, k_eff))
            ndcg_b9 = ndcg_at_k(b9_order, gt_loss, min(5, k_eff))

            rows.append({
                "heterogeneity": heterogeneity,
                "rep_seed": rep_seed,
                "k": k,
                "cbl_blast": cbl_blast,
                "cbl_b9": cbl_b9,
                "cbl_oracle": cbl_oracle,
                "ndcg5_blast": ndcg_blast,
                "ndcg5_b9": ndcg_b9,
            })

    return rows


def main():

    print("=" * 110)
    print("BLAST — SYNTHETIC-TOPOLOGY HETEROGENEITY SWEEP")
    print("=" * 110)

    capability_ids, weights = load_weights_and_capabilities()

    print(f"\nCapabilities: {len(capability_ids)} (reusing real overlay weights)")
    print(f"Services: {N_SERVICES}, fault types: {N_FAULT_TYPES} "
          f"({N_SERVICES * N_FAULT_TYPES} incident types per repetition)")
    print(f"Heterogeneity levels: {list(HETEROGENEITY_LEVELS)}")
    print(f"Repetitions per level: {N_REPETITIONS_PER_LEVEL}")

    all_rows = []

    for h in HETEROGENEITY_LEVELS:
        for rep in range(N_REPETITIONS_PER_LEVEL):
            rep_seed = SEED + int(h * 1000) + rep
            all_rows.extend(run_one_repetition(h, rep_seed, capability_ids, weights))

    raw = pd.DataFrame(all_rows)

    print(f"\nTotal (BLAST, B9) paired scenario comparisons generated: {len(raw)}")

    # ----------------------------------------------------
    # Per-heterogeneity-level statistics
    # ----------------------------------------------------

    summary_rows = []

    for h, group in raw.groupby("heterogeneity"):

        cbl_blast = group["cbl_blast"].to_numpy()
        cbl_b9 = group["cbl_b9"].to_numpy()
        ndcg_blast = group["ndcg5_blast"].dropna().to_numpy()
        ndcg_b9 = group["ndcg5_b9"].dropna().to_numpy()

        cbl_stat, cbl_p = paired_wilcoxon(cbl_blast, cbl_b9)
        cbl_delta = cliffs_delta(cbl_blast, cbl_b9)

        ndcg_stat, ndcg_p = paired_wilcoxon(ndcg_blast, ndcg_b9)
        ndcg_delta = cliffs_delta(ndcg_blast, ndcg_b9)

        summary_rows.append({
            "heterogeneity": h,
            "n_scenarios": len(group),
            "cbl_blast_mean": cbl_blast.mean(),
            "cbl_b9_mean": cbl_b9.mean(),
            "cbl_p_raw": cbl_p,
            "cbl_cliffs_delta": cbl_delta,
            "ndcg5_blast_mean": ndcg_blast.mean(),
            "ndcg5_b9_mean": ndcg_b9.mean(),
            "ndcg5_p_raw": ndcg_p,
            "ndcg5_cliffs_delta": ndcg_delta,
        })

    summary = pd.DataFrame(summary_rows).sort_values("heterogeneity").reset_index(drop=True)

    # Holm correction across the swept levels, per metric family
    summary["cbl_p_holm"] = holm_bonferroni(summary["cbl_p_raw"].to_numpy())
    summary["ndcg5_p_holm"] = holm_bonferroni(summary["ndcg5_p_raw"].to_numpy())

    summary["cbl_blast_wins"] = (
        (summary["cbl_p_holm"] < ALPHA)
        & (summary["cbl_cliffs_delta"].abs() >= CLIFFS_DELTA_FLOOR)
        & (summary["cbl_blast_mean"] < summary["cbl_b9_mean"])
    )

    summary["ndcg5_blast_wins"] = (
        (summary["ndcg5_p_holm"] < ALPHA)
        & (summary["ndcg5_cliffs_delta"].abs() >= CLIFFS_DELTA_FLOOR)
        & (summary["ndcg5_blast_mean"] > summary["ndcg5_b9_mean"])
    )

    pd.set_option("display.max_columns", None)
    pd.set_option("display.width", 220)

    print("\n")
    print("=" * 110)
    print("HETEROGENEITY SWEEP RESULTS")
    print("=" * 110)
    print(summary.to_string(index=False, float_format=lambda x: f"{x:.4f}"))

    # ----------------------------------------------------
    # Crossover point
    # ----------------------------------------------------

    print("\n")
    print("=" * 110)
    print("CROSSOVER ANALYSIS")
    print("=" * 110)

    cbl_winning = summary[summary["cbl_blast_wins"]]

    if cbl_winning.empty:
        print("\nNo heterogeneity level in [0,1] produced a practically significant CBL "
              "advantage for BLAST over B9 in this sweep. The real corpus's heterogeneity "
              "(effectively ~0, per ADR-019's footprint finding) is consistent with this: "
              "no CBL advantage was found there either.")
        crossover = None
    else:
        crossover = cbl_winning["heterogeneity"].min()
        print(f"\nCROSSOVER at heterogeneity >= {crossover:.2f}: BLAST achieves a statistically "
              f"AND practically significant CBL advantage over B9 from this point onward.")
        print(f"\nAt crossover: BLAST_CBL={cbl_winning.iloc[0]['cbl_blast_mean']:.2f}, "
              f"B9_CBL={cbl_winning.iloc[0]['cbl_b9_mean']:.2f}, "
              f"Cliff's delta={cbl_winning.iloc[0]['cbl_cliffs_delta']:.3f}")

    ndcg_winning = summary[summary["ndcg5_blast_wins"]]
    if not ndcg_winning.empty:
        ndcg_crossover = ndcg_winning["heterogeneity"].min()
        print(f"\nNDCG@5 practical advantage holds from heterogeneity >= {ndcg_crossover:.2f} "
              f"onward (real corpus already showed this at its effective heterogeneity ~0).")

    # ----------------------------------------------------
    # Plot
    # ----------------------------------------------------

    Path("results/figures").mkdir(parents=True, exist_ok=True)

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    ax = axes[0]
    ax.plot(summary["heterogeneity"], summary["cbl_blast_mean"], marker="o", label="BLAST")
    ax.plot(summary["heterogeneity"], summary["cbl_b9_mean"], marker="s", label="B9 (independent)")
    if crossover is not None:
        ax.axvline(crossover, color="grey", linestyle="--", alpha=0.6, label=f"crossover ({crossover:.2f})")
    ax.set_xlabel("Capability-footprint heterogeneity")
    ax.set_ylabel("Mean Cumulative Business Loss (lower is better)")
    ax.set_title("CBL vs footprint heterogeneity")
    ax.legend()

    ax2 = axes[1]
    ax2.plot(summary["heterogeneity"], summary["cbl_cliffs_delta"], marker="o", color="tab:red")
    ax2.axhline(CLIFFS_DELTA_FLOOR, color="grey", linestyle=":", label="practical-significance floor")
    ax2.axhline(-CLIFFS_DELTA_FLOOR, color="grey", linestyle=":")
    ax2.axhline(0, color="black", linewidth=0.5)
    ax2.set_xlabel("Capability-footprint heterogeneity")
    ax2.set_ylabel("Cliff's delta (BLAST vs B9, CBL)")
    ax2.set_title("Effect size vs heterogeneity")
    ax2.legend()

    fig.tight_layout()
    fig.savefig(OUTPUT_PLOT, dpi=150)
    print(f"\nPlot saved: {OUTPUT_PLOT}")

    # ----------------------------------------------------
    # Save
    # ----------------------------------------------------

    summary.to_csv(OUTPUT_SWEEP, index=False)

    print("\n")
    print("=" * 110)
    print("FILES SAVED")
    print("=" * 110)
    print(OUTPUT_SWEEP)
    print(OUTPUT_PLOT)

    print("\nHeterogeneity sweep complete.")


if __name__ == "__main__":
    main()
