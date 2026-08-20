import json

import numpy as np
import pandas as pd
import yaml

from blast_eval_lib import (
    ndcg_at_k, simulate_cumulative_loss, cliffs_delta, paired_wilcoxon, holm_bonferroni,
)
from run_evaluation import blast_greedy, b9_blast_independent, build_case_ground_truth


# ======================================================
# BLAST — ABLATION STUDY (A1, A2, A7)
# ======================================================
#
# context/03_RESEARCH_DESIGN.md §7. Fills the "ablation
# study" gap flagged in the requirements matrix -- the
# headline ablation (A4, submodular vs independent = B9)
# was already the centrepiece of run_evaluation.py; this
# covers the three OTHER ablations that are actually
# meaningful to run given what this benchmark turned out
# to look like (see the "not applicable" notes for A3/A5,
# which are skipped with reasons, not silently omitted).
#
# A1  -business-overlay : service-level attribution
#     (the pre-ADR-014 pilot bug) vs journey-level.
#     Only ever run on the 6-case checkout pilot -- the
#     full 30-type corpus was NEVER processed under the
#     broken attribution, so this compares the two
#     ALREADY-COMPUTED pilot artifacts rather than
#     re-running anything.
# A2  -learned-p : BLAST's learned p(c|i) replaced with a
#     constant (uniform across every capability an
#     incident type touches) -- does the LEARNED part of
#     the probability estimate matter, or would any
#     nonzero constant do as well?
# A7  p estimation method : Beta-smoothed posterior
#     (current default) vs raw unsmoothed MLE -- does the
#     Beta(1,1) smoothing (build_incident_capability_model.py)
#     actually change anything with only 3 reps/type?
#
# A3 (-propagation) and A5 (-edge-types) are marked N/A,
# not run: the current F(S) never uses multi-hop cascade
# propagation or heterogeneous edge types as an input in
# the first place (ADR-018 demoted propagation before it
# became a live scoring input) -- there is nothing in the
# current implementation for either ablation to remove.
# ======================================================

SCENARIOS_FILE = "results/data/ground_truth_scenarios.json"
CASE_MAGNITUDE_FILE = "results/data/case_capability_magnitude.csv"
TYPE_PROBABILITY_FILE = "results/data/incident_capability_probabilities.csv"
OVERLAY_FILE = "business_overlay/online_boutique_v2.yaml"

OLD_MATRIX_FILE = "results/data/incident_capability_matrix.csv"      # service-level, pre-ADR-014
NEW_MATRIX_FILE = "results/data/incident_capability_matrix_v2.csv"   # journey-level, ADR-014

OUTPUT_A1 = "results/data/ablation_a1_attribution_level.csv"
OUTPUT_A2_A7 = "results/data/ablation_a2_a7_probability_model.csv"

CLIFFS_DELTA_FLOOR = 0.147
ALPHA = 0.05


def load_weights():
    with open(OVERLAY_FILE) as f:
        overlay = yaml.safe_load(f)
    return {c["id"]: c["value_per_min"] for c in overlay["capabilities"]}


# ======================================================
# A1 -- attribution level (pre-computed artifacts only)
# ======================================================

def run_a1():

    print("=" * 110)
    print("A1 -- ATTRIBUTION LEVEL (service-level vs journey-level, 6-case pilot only)")
    print("=" * 110)

    old = pd.read_csv(OLD_MATRIX_FILE)
    new = pd.read_csv(NEW_MATRIX_FILE)

    cap_cols_old = [c for c in old.columns if c not in ("incident_id", "fault_type")]
    cap_cols_new = [c for c in new.columns if c not in ("incident_id", "fault_type")]

    old["capabilities_covered"] = old[cap_cols_old].sum(axis=1)
    new["capabilities_covered"] = new[cap_cols_new].sum(axis=1)

    universe = len(cap_cols_old)

    rows = []
    for _, r in old.iterrows():
        rows.append({"incident_id": r["incident_id"], "attribution": "service_level (pre-ADR-014)",
                     "capabilities_covered": r["capabilities_covered"], "universe": universe,
                     "saturation": r["capabilities_covered"] / universe})
    for _, r in new.iterrows():
        rows.append({"incident_id": r["incident_id"], "attribution": "journey_level (ADR-014, current)",
                     "capabilities_covered": r["capabilities_covered"], "universe": universe,
                     "saturation": r["capabilities_covered"] / universe})

    result = pd.DataFrame(rows)
    print(result.to_string(index=False))

    summary = result.groupby("attribution")["saturation"].agg(["mean", "max"])
    print("\nMean / max capability-universe saturation per attribution method:")
    print(summary.to_string())

    result.to_csv(OUTPUT_A1, index=False)
    print(f"\nSaved: {OUTPUT_A1}")

    return result


# ======================================================
# A2 / A7 -- probability model variants
# ======================================================

def run_a2_a7():

    print("\n\n")
    print("=" * 110)
    print("A2 / A7 -- PROBABILITY MODEL: learned-vs-uniform, smoothed-vs-raw")
    print("=" * 110)

    with open(SCENARIOS_FILE) as f:
        scenarios = json.load(f)

    case_mag = pd.read_csv(CASE_MAGNITUDE_FILE)
    type_prob_df = pd.read_csv(TYPE_PROBABILITY_FILE)
    weights = load_weights()
    case_gt = build_case_ground_truth(case_mag)

    # --- variant A: current default (Beta-smoothed p_smoothed) ---
    smoothed = {}
    for (svc, ft), g in type_prob_df.groupby(["service", "fault_type"]):
        smoothed[(svc, ft)] = dict(zip(g["capability_id"], g["p_smoothed"]))

    # --- variant B (A7): raw unsmoothed MLE, no Beta(1,1) prior ---
    raw = {}
    for (svc, ft), g in type_prob_df.groupby(["service", "fault_type"]):
        raw[(svc, ft)] = dict(zip(g["capability_id"], g["raw_probability"]))

    # --- variant C (A2): uniform constant for every capability an
    #     incident type touches (touches = smoothed prob > 0), no
    #     learning at all -- same MEAN probability as the smoothed
    #     variant so the comparison isolates "learned per-capability
    #     value" from "any nonzero constant".
    mean_p = type_prob_df.loc[type_prob_df["n_impaired_reps"] > 0, "p_smoothed"].mean()
    uniform = {}
    for key, caps in smoothed.items():
        uniform[key] = {c: mean_p for c, p in caps.items() if p > 0}

    variants = {
        "learned_smoothed (current default)": smoothed,
        "learned_raw_unsmoothed (A7)": raw,
        "uniform_constant (A2, no learning)": uniform,
    }

    rows = []

    for variant_name, type_probabilities in variants.items():

        for sc in scenarios:

            incident_ids = sc["incident_ids"]
            k = sc["k"]
            oracle = sc["oracle_order"]
            gt_loss = {i: float(v) for i, v in sc["gt_loss"].items()}
            id_to_type = {
                i: tuple(t.split("::")) for i, t in zip(incident_ids, sc["incident_types"])
            }

            incident_capabilities_gt = {i: case_gt.get(i, {}) for i in incident_ids}

            blast_order = blast_greedy(incident_ids, id_to_type, type_probabilities, weights)
            _, cbl = simulate_cumulative_loss(blast_order, incident_capabilities_gt, weights)
            ndcg5 = ndcg_at_k(blast_order, gt_loss, min(5, k))

            rows.append({
                "variant": variant_name,
                "scenario_id": sc["scenario_id"],
                "k": k,
                "cbl": cbl,
                "ndcg_5": ndcg5,
            })

    result = pd.DataFrame(rows)

    pd.set_option("display.max_columns", None)
    pd.set_option("display.width", 200)

    summary = result.groupby("variant")[["cbl", "ndcg_5"]].agg(["mean", "std"])
    print(summary.to_string())

    # Statistical comparison: current default vs each alternative
    print("\nStatistical comparison (current default vs each variant, paired by scenario):")

    default_key = "learned_smoothed (current default)"
    default_cbl = result[result["variant"] == default_key].set_index("scenario_id")["cbl"]
    default_ndcg = result[result["variant"] == default_key].set_index("scenario_id")["ndcg_5"]

    for variant_name in variants:
        if variant_name == default_key:
            continue

        v_cbl = result[result["variant"] == variant_name].set_index("scenario_id")["cbl"]
        v_ndcg = result[result["variant"] == variant_name].set_index("scenario_id")["ndcg_5"]

        for metric_name, a, b in [("cbl", default_cbl, v_cbl), ("ndcg_5", default_ndcg, v_ndcg)]:
            common = a.index.intersection(b.index)
            stat, p = paired_wilcoxon(a.loc[common].to_numpy(), b.loc[common].to_numpy())
            delta = cliffs_delta(a.loc[common].to_numpy(), b.loc[common].to_numpy())
            real_effect = abs(delta) >= CLIFFS_DELTA_FLOOR and p < ALPHA
            print(f"  {metric_name:8s} default vs {variant_name:38s} "
                  f"p={p:.4g} cliffs_delta={delta:+.3f} real_effect={real_effect}")

    result.to_csv(OUTPUT_A2_A7, index=False)
    print(f"\nSaved: {OUTPUT_A2_A7}")

    return result


if __name__ == "__main__":
    run_a1()
    run_a2_a7()
    print("\nAblation study complete.")
