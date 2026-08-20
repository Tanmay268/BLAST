import json
from pathlib import Path

import numpy as np
import pandas as pd
import networkx as nx
import yaml

from blast_eval_lib import (
    ndcg_at_k, kendalls_tau, mrr, precision_at_k, average_precision,
    simulate_cumulative_loss, normalized_aulc,
    cliffs_delta, paired_wilcoxon, holm_bonferroni,
)
from run_evaluation import (
    build_case_ground_truth, build_type_probabilities, build_case_features,
    build_case_gt_loss, fit_b7_classifier, fit_b10_pairwise_ranker,
    b1_random, b2_severity, b3_itil, b4_pagerank, b5_betweenness,
    b6_personalized_pagerank, b7_classifier, b9_blast_independent,
    b11_closeness, b12_eigenvector, blast_greedy,
    NDCG_KS, CLIFFS_DELTA_FLOOR, PRIMARY_DECISION_METRIC,
)


# ======================================================
# BLAST — TRAIN TICKET FULL EVALUATION HARNESS
# ======================================================
#
# Same evaluation logic as run_evaluation.py -- every
# baseline function is IMPORTED from there (b1-b12,
# blast_greedy, the statistical machinery), not
# reimplemented, so the two systems are evaluated with
# provably identical methodology. Only data loading (which
# files, which overlay, which split) is Train-Ticket-
# specific.
# ======================================================

SCENARIOS_FILE = "results/data/re2tt_ground_truth_scenarios.json"
CASE_MAGNITUDE_FILE = "results/data/re2tt_case_capability_magnitude.csv"
TYPE_PROBABILITY_FILE = "results/data/re2tt_incident_capability_probabilities.csv"
JOURNEY_FILE = "results/data/re2tt_journey_impairment_full.csv"
GRAPH_FILE = "results/data/re2tt_service_graph.csv"
SPLIT_FILE = "config/splits/split_re2tt_v1.yaml"
OVERLAY_FILE = "business_overlay/train_ticket_v1.yaml"

OUTPUT_PER_SCENARIO = "results/data/re2tt_evaluation_per_scenario.csv"
OUTPUT_AGGREGATE = "results/data/re2tt_evaluation_aggregate.csv"
OUTPUT_STATS = "results/data/re2tt_evaluation_statistics.csv"
OUTPUT_LATEX = "results/tables/re2tt_evaluation_summary.tex"


def load_all():

    with open(SCENARIOS_FILE) as f:
        scenarios = json.load(f)

    case_mag = pd.read_csv(CASE_MAGNITUDE_FILE)
    type_prob_df = pd.read_csv(TYPE_PROBABILITY_FILE)
    journeys = pd.read_csv(JOURNEY_FILE)
    graph_df = pd.read_csv(GRAPH_FILE)

    with open(SPLIT_FILE) as f:
        split = yaml.safe_load(f)
    with open(OVERLAY_FILE) as f:
        overlay = yaml.safe_load(f)

    weights = {c["id"]: c["value_per_min"] for c in overlay["capabilities"]}

    G = nx.DiGraph()
    for _, row in graph_df.iterrows():
        G.add_edge(row["source"], row["target"], calls=row.get("calls", 1))

    # ts-auth-service (at least) never appears in a cross-service call
    # edge -- it's a leaf that doesn't call out, same pattern as
    # Online Boutique's leaf services. Add every target service as an
    # explicit (possibly isolated) node so PageRank/centrality see a
    # real, present node rather than silently defaulting via .get().
    target_services = journeys["target_service"].unique().tolist()
    G.add_nodes_from(target_services)

    return scenarios, case_mag, type_prob_df, journeys, G, split, weights


def main():

    print("=" * 110)
    print("BLAST — TRAIN TICKET FULL EVALUATION HARNESS")
    print("=" * 110)

    scenarios, case_mag, type_prob_df, journeys, G, split, weights = load_all()

    print(f"\nScenarios: {len(scenarios)}")
    print(f"Weights (capabilities): {len(weights)}")
    print(f"Service graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

    case_gt = build_case_ground_truth(case_mag)
    type_probabilities = build_type_probabilities(type_prob_df)
    features_df = build_case_features(case_mag, journeys)
    features_by_case = features_df.set_index("case").to_dict("index")
    gt_loss_by_case = build_case_gt_loss(case_mag, weights)

    type_of_case = {
        row["case"]: (row["target_service"], row["fault_type"])
        for _, row in features_df.iterrows()
    }

    pagerank_scores = nx.pagerank(G)
    betweenness_scores = nx.betweenness_centrality(G)
    closeness_scores = nx.closeness_centrality(G)
    try:
        eigenvector_scores = nx.eigenvector_centrality(G, max_iter=1000)
    except nx.PowerIterationFailedConvergence:
        eigenvector_scores = {n: 0.0 for n in G.nodes()}

    b7_predict = fit_b7_classifier(features_df, gt_loss_by_case, split)
    b10_predict_order = fit_b10_pairwise_ranker(features_df, gt_loss_by_case, split)

    METHODS = ["BLAST", "B1_random", "B2_severity", "B3_itil",
               "B4_pagerank", "B5_betweenness", "B6_ppr",
               "B7_classifier", "B9_independent", "B10_pairwise",
               "B11_closeness", "B12_eigenvector"]

    per_scenario_rows = []

    for sc in scenarios:

        scenario_id = sc["scenario_id"]
        k = sc["k"]
        incident_ids = sc["incident_ids"]
        oracle = sc["oracle_order"]
        gt_loss = {i: float(v) for i, v in sc["gt_loss"].items()}

        incident_capabilities_gt = {i: case_gt.get(i, {}) for i in incident_ids}

        orders = {
            "BLAST": blast_greedy(incident_ids, type_of_case, type_probabilities, weights),
            "B1_random": b1_random(incident_ids, scenario_id),
            "B2_severity": b2_severity(incident_ids, features_by_case),
            "B3_itil": b3_itil(incident_ids, features_by_case),
            "B4_pagerank": b4_pagerank(incident_ids, type_of_case, pagerank_scores),
            "B5_betweenness": b5_betweenness(incident_ids, type_of_case, betweenness_scores),
            "B6_ppr": b6_personalized_pagerank(incident_ids, type_of_case, G),
            "B7_classifier": b7_classifier(incident_ids, b7_predict, features_df),
            "B9_independent": b9_blast_independent(incident_ids, type_of_case, type_probabilities, weights),
            "B10_pairwise": b10_predict_order(incident_ids, features_df),
            "B11_closeness": b11_closeness(incident_ids, type_of_case, closeness_scores),
            "B12_eigenvector": b12_eigenvector(incident_ids, type_of_case, eigenvector_scores),
        }

        _, cbl_oracle = simulate_cumulative_loss(oracle, incident_capabilities_gt, weights)
        _, cbl_random_ref = simulate_cumulative_loss(
            b1_random(incident_ids, scenario_id + "::aulc_ref"), incident_capabilities_gt, weights,
        )

        for method, order in orders.items():

            _, cbl = simulate_cumulative_loss(order, incident_capabilities_gt, weights)
            aulc = normalized_aulc(cbl, cbl_oracle, cbl_random_ref)

            row = {
                "scenario_id": scenario_id, "k": k, "method": method,
                "cbl": cbl, "cbl_oracle": cbl_oracle, "aulc_normalized": aulc,
                "kendalls_tau": kendalls_tau(order, oracle),
                "mrr": mrr(order, oracle),
                "precision_at_3": precision_at_k(order, oracle, min(3, k)),
                "map": average_precision(order, oracle, k),
            }
            for kk in NDCG_KS:
                row[f"ndcg_{kk}"] = ndcg_at_k(order, gt_loss, min(kk, k))

            per_scenario_rows.append(row)

    per_scenario = pd.DataFrame(per_scenario_rows)
    per_scenario.to_csv(OUTPUT_PER_SCENARIO, index=False)

    metric_cols = ["cbl", "aulc_normalized", "kendalls_tau", "mrr",
                    "precision_at_3", "map"] + [f"ndcg_{k}" for k in NDCG_KS]

    aggregate = per_scenario.groupby("method")[metric_cols].agg(["mean", "std"])
    aggregate.columns = ["_".join(c) for c in aggregate.columns]
    aggregate = aggregate.reset_index()
    aggregate.to_csv(OUTPUT_AGGREGATE, index=False)

    pd.set_option("display.max_columns", None)
    pd.set_option("display.width", 240)

    print("\n")
    print("=" * 110)
    print("AGGREGATE RESULTS")
    print("=" * 110)
    print(aggregate.to_string(index=False, float_format=lambda x: f"{x:.4f}"))

    baselines = [m for m in METHODS if m != "BLAST"]
    stats_rows = []

    for primary_metric, higher_is_better in [("ndcg_5", True), ("cbl", False)]:

        blast_vals = per_scenario[per_scenario["method"] == "BLAST"].set_index("scenario_id")[primary_metric]
        pvals, rows_this_metric = [], []

        for baseline in baselines:
            baseline_vals = per_scenario[per_scenario["method"] == baseline].set_index("scenario_id")[primary_metric]
            common = blast_vals.index.intersection(baseline_vals.index)
            a = blast_vals.loc[common].dropna()
            b = baseline_vals.loc[common].dropna()
            common2 = a.index.intersection(b.index)
            a, b = a.loc[common2].to_numpy(), b.loc[common2].to_numpy()

            stat, p = paired_wilcoxon(a, b)
            delta = cliffs_delta(a, b)

            rows_this_metric.append({
                "metric": primary_metric, "baseline": baseline, "n_scenarios": len(a),
                "blast_mean": np.nanmean(a), "baseline_mean": np.nanmean(b),
                "wilcoxon_stat": stat, "p_value_raw": p, "cliffs_delta": delta,
                "higher_is_better": higher_is_better,
            })
            pvals.append(p)

        adjusted = holm_bonferroni(pvals)
        for row, p_adj in zip(rows_this_metric, adjusted):
            row["p_value_holm"] = p_adj
            better = row["blast_mean"] > row["baseline_mean"] if higher_is_better else row["blast_mean"] < row["baseline_mean"]
            stat_sig = bool((not np.isnan(p_adj)) and p_adj < 0.05 and better)
            prac_sig = bool(abs(row["cliffs_delta"]) >= CLIFFS_DELTA_FLOOR)
            row["statistically_significant_win"] = stat_sig
            row["practically_significant"] = prac_sig
            row["blast_significantly_better"] = stat_sig and prac_sig
            stats_rows.append(row)

    stats = pd.DataFrame(stats_rows)
    stats.to_csv(OUTPUT_STATS, index=False)

    print("\n")
    print("=" * 110)
    print("STATISTICAL COMPARISON: BLAST vs BASELINES")
    print("=" * 110)
    print(stats.to_string(index=False, float_format=lambda x: f"{x:.4g}"))

    b9_row = stats[(stats["baseline"] == "B9_independent") & (stats["metric"] == PRIMARY_DECISION_METRIC)]
    ndcg_row = stats[(stats["baseline"] == "B9_independent") & (stats["metric"] == "ndcg_5")]

    print("\n")
    print("=" * 110)
    print("CROSS-SYSTEM GATE 4 CHECK (Train Ticket)")
    print("=" * 110)

    if not b9_row.empty and not ndcg_row.empty:
        b9_row, ndcg_row = b9_row.iloc[0], ndcg_row.iloc[0]

        cbl_real = bool(b9_row["blast_significantly_better"])
        ndcg_real = bool(ndcg_row["blast_significantly_better"])

        print(f"\nBLAST vs B9 on CBL: BLAST={b9_row['blast_mean']:.2f} B9={b9_row['baseline_mean']:.2f} "
              f"p_holm={b9_row['p_value_holm']:.4g} delta={b9_row['cliffs_delta']:.3f} real_win={cbl_real}")
        print(f"BLAST vs B9 on NDCG@5: BLAST={ndcg_row['blast_mean']:.4f} B9={ndcg_row['baseline_mean']:.4f} "
              f"p_holm={ndcg_row['p_value_holm']:.4g} delta={ndcg_row['cliffs_delta']:.3f} real_win={ndcg_real}")

        print(f"\nOnline Boutique found: NDCG@5 real win=True, CBL real win=False (ADR-019).")
        print(f"Train Ticket finds:    NDCG@5 real win={ndcg_real}, CBL real win={cbl_real}.")

        if ndcg_real == True and cbl_real == False:
            print("\nSAME PATTERN as Online Boutique -- the ranking-accuracy finding "
                  "replicates cross-system; the CBL null result does too.")
        else:
            print("\nDIFFERENT PATTERN from Online Boutique -- this is itself an important "
                  "cross-system finding and should be written up as one, not smoothed over.")

    Path("results/tables").mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_LATEX, "w") as f:
        f.write("% Auto-generated by re2tt_run_evaluation.py.\n")
        f.write("\\begin{tabular}{l" + "r" * len(metric_cols) + "}\n\\toprule\n")
        f.write("Method & " + " & ".join(m.replace("_", "\\_") for m in metric_cols) + " \\\\\n\\midrule\n")
        for _, row in aggregate.iterrows():
            vals = " & ".join(f"{row[f'{m}_mean']:.3f}" for m in metric_cols)
            f.write(f"{row['method'].replace('_', chr(92)+'_')} & {vals} \\\\\n")
        f.write("\\bottomrule\n\\end{tabular}\n")

    print("\n")
    print("=" * 110)
    print("FILES SAVED")
    print("=" * 110)
    for f in [OUTPUT_PER_SCENARIO, OUTPUT_AGGREGATE, OUTPUT_STATS, OUTPUT_LATEX]:
        print(f)

    print("\nTrain Ticket evaluation complete.")


if __name__ == "__main__":
    main()
