import json
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from blast_eval_lib import (
    ndcg_at_k, simulate_cumulative_loss, cliffs_delta, paired_wilcoxon, holm_bonferroni,
)
from run_evaluation import blast_greedy, b9_blast_independent, build_case_ground_truth


# ======================================================
# BLAST — VALUE MODEL SENSITIVITY SWEEP (A6)
# ======================================================
#
# context/03_RESEARCH_DESIGN.md §3.3: "Report BLAST's results
# under all of them. If your ranking advantage survives
# value-model perturbation, the result is robust... If it
# collapses under uniform weighting, you have learned
# something important and must report it."
#
# Reruns the headline BLAST-vs-B9 comparison (NDCG@5, CBL)
# under each of the 5 value models in business_overlay/ --
# same 90 test scenarios, same probability model, only the
# capability weights change.
# ======================================================

SCENARIOS_FILE = "results/data/ground_truth_scenarios.json"
CASE_MAGNITUDE_FILE = "results/data/case_capability_magnitude.csv"
TYPE_PROBABILITY_FILE = "results/data/incident_capability_probabilities.csv"

OVERLAYS = {
    "revenue_weighted": "business_overlay/online_boutique_v2.yaml",
    "uniform": "business_overlay/sensitivity_sweep/uniform.yaml",
    "user_volume_weighted": "business_overlay/sensitivity_sweep/user_volume_weighted.yaml",
    "sla_urgency_weighted": "business_overlay/sensitivity_sweep/sla_urgency_weighted.yaml",
    "adversarial_inverted": "business_overlay/sensitivity_sweep/adversarial_inverted.yaml",
}

OUTPUT_FILE = "results/data/value_model_sweep.csv"

CLIFFS_DELTA_FLOOR = 0.147
ALPHA = 0.05


def load_weights(path):
    with open(path) as f:
        overlay = yaml.safe_load(f)
    return {c["id"]: c["value_per_min"] for c in overlay["capabilities"]}


def main():

    print("=" * 110)
    print("BLAST — VALUE MODEL SENSITIVITY SWEEP (A6)")
    print("=" * 110)

    with open(SCENARIOS_FILE) as f:
        scenarios = json.load(f)

    case_mag = pd.read_csv(CASE_MAGNITUDE_FILE)
    type_prob_df = pd.read_csv(TYPE_PROBABILITY_FILE)
    case_gt = build_case_ground_truth(case_mag)

    type_probabilities = {}
    for (svc, ft), g in type_prob_df.groupby(["service", "fault_type"]):
        type_probabilities[(svc, ft)] = dict(zip(g["capability_id"], g["p_smoothed"]))

    all_rows = []

    for model_name, overlay_path in OVERLAYS.items():

        weights = load_weights(overlay_path)
        print(f"\n{model_name}: {weights}")

        for sc in scenarios:

            incident_ids = sc["incident_ids"]
            k = sc["k"]
            id_to_type = {
                i: tuple(t.split("::")) for i, t in zip(incident_ids, sc["incident_types"])
            }

            incident_capabilities_gt = {i: case_gt.get(i, {}) for i in incident_ids}
            gt_loss = {
                i: sum(weights.get(c, 1.0) * m for c, m in incident_capabilities_gt[i].items())
                for i in incident_ids
            }

            blast_order = blast_greedy(incident_ids, id_to_type, type_probabilities, weights)
            b9_order = b9_blast_independent(incident_ids, id_to_type, type_probabilities, weights)

            _, cbl_blast = simulate_cumulative_loss(blast_order, incident_capabilities_gt, weights)
            _, cbl_b9 = simulate_cumulative_loss(b9_order, incident_capabilities_gt, weights)

            ndcg_blast = ndcg_at_k(blast_order, gt_loss, min(5, k))
            ndcg_b9 = ndcg_at_k(b9_order, gt_loss, min(5, k))

            all_rows.append({
                "value_model": model_name, "scenario_id": sc["scenario_id"], "k": k,
                "cbl_blast": cbl_blast, "cbl_b9": cbl_b9,
                "ndcg5_blast": ndcg_blast, "ndcg5_b9": ndcg_b9,
            })

    result = pd.DataFrame(all_rows)

    pd.set_option("display.max_columns", None)
    pd.set_option("display.width", 200)

    print("\n")
    print("=" * 110)
    print("RESULTS PER VALUE MODEL")
    print("=" * 110)

    summary_rows = []

    for model_name, group in result.groupby("value_model"):

        cbl_b, cbl_9 = group["cbl_blast"].to_numpy(), group["cbl_b9"].to_numpy()
        ndcg_b, ndcg_9 = group["ndcg5_blast"].to_numpy(), group["ndcg5_b9"].to_numpy()

        cbl_stat, cbl_p = paired_wilcoxon(cbl_b, cbl_9)
        cbl_delta = cliffs_delta(cbl_b, cbl_9)
        ndcg_stat, ndcg_p = paired_wilcoxon(ndcg_b, ndcg_9)
        ndcg_delta = cliffs_delta(ndcg_b, ndcg_9)

        summary_rows.append({
            "value_model": model_name,
            "cbl_blast_mean": cbl_b.mean(), "cbl_b9_mean": cbl_9.mean(),
            "cbl_p_raw": cbl_p, "cbl_cliffs_delta": cbl_delta,
            "ndcg5_blast_mean": ndcg_b.mean(), "ndcg5_b9_mean": ndcg_9.mean(),
            "ndcg5_p_raw": ndcg_p, "ndcg5_cliffs_delta": ndcg_delta,
        })

    summary = pd.DataFrame(summary_rows)
    summary["cbl_p_holm"] = holm_bonferroni(summary["cbl_p_raw"].to_numpy())
    summary["ndcg5_p_holm"] = holm_bonferroni(summary["ndcg5_p_raw"].to_numpy())

    summary["blast_wins_ndcg5"] = (
        (summary["ndcg5_p_holm"] < ALPHA)
        & (summary["ndcg5_cliffs_delta"].abs() >= CLIFFS_DELTA_FLOOR)
        & (summary["ndcg5_blast_mean"] > summary["ndcg5_b9_mean"])
    )
    summary["blast_wins_cbl"] = (
        (summary["cbl_p_holm"] < ALPHA)
        & (summary["cbl_cliffs_delta"].abs() >= CLIFFS_DELTA_FLOOR)
        & (summary["cbl_blast_mean"] < summary["cbl_b9_mean"])
    )

    print(summary.to_string(index=False, float_format=lambda x: f"{x:.4f}"))

    n_ndcg_wins = int(summary["blast_wins_ndcg5"].sum())
    n_cbl_wins = int(summary["blast_wins_cbl"].sum())
    n_models = len(summary)

    print("\n")
    print("=" * 110)
    print("ROBUSTNESS VERDICT")
    print("=" * 110)
    print(f"\nBLAST's NDCG@5 advantage over B9 survives in {n_ndcg_wins}/{n_models} value models.")
    print(f"BLAST's CBL advantage over B9 survives in {n_cbl_wins}/{n_models} value models.")

    if n_ndcg_wins == n_models:
        print("\nThe ranking-accuracy advantage is ROBUST to value-model choice -- it holds "
              "even under uniform weighting and the adversarial-inverted model, so it is not "
              "an artifact of the specific declared weights (03_RESEARCH_DESIGN.md §3.3).")
    else:
        print(f"\nThe ranking-accuracy advantage is CONDITIONAL on value-model choice -- it "
              f"does not survive in all {n_models} models tested. Report which models it holds "
              f"under and why, per §3.3's own instruction: this is itself a finding, not a "
              f"failure to hide.")

    result.to_csv(OUTPUT_FILE, index=False)
    summary.to_csv("results/data/value_model_sweep_summary.csv", index=False)

    print(f"\nSaved: {OUTPUT_FILE}")
    print("Saved: results/data/value_model_sweep_summary.csv")
    print("\nValue model sensitivity sweep complete.")


if __name__ == "__main__":
    main()
