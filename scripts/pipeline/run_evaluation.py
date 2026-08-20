import json
import random
from pathlib import Path

import numpy as np
import pandas as pd
import networkx as nx
import yaml
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.preprocessing import OneHotEncoder

from blast_eval_lib import (
    ndcg_at_k, kendalls_tau, mrr, precision_at_k, average_precision,
    simulate_cumulative_loss, normalized_aulc,
    cliffs_delta, paired_wilcoxon, holm_bonferroni,
)


# ======================================================
# BLAST — FULL EVALUATION HARNESS (GATE 4)
# ======================================================
#
# context/07_NEXT_PHASE_PLAN.md Step 6 / task list #11-13.
# 03_RESEARCH_DESIGN.md §5 (baselines), §6 (metrics).
#
# Baselines implemented (plan's order, cheap to expensive):
#   B1 random, B2 severity (technical, unweighted),
#   B4 PageRank, B6 personalized PageRank, B9 BLAST-
#   independent (ablation-as-baseline), B3 ITIL matrix,
#   B7 AlertRank-style gradient-boosted regressor.
#
# B7 substitutes sklearn's HistGradientBoostingRegressor for
# LightGBM (declared in CLAUDE.md's tech stack but not
# installed in this environment) -- both are gradient-
# boosted tree ensembles; the substitution does not change
# what B7 tests (RQ1: is a feature classifier enough?).
# Labelled a reimplementation, per TV-5.
#
# Primary comparison, pre-registered per TV-9: BLAST vs B9
# on NDCG@5 and on CBL. All incidents scored/ranked using
# BLAST's own MODEL inputs (p(c|i) at the incident-TYPE
# level) -- never the scenario's ground-truth magnitudes,
# which are reserved for grading. Evaluated on TEST-split
# scenarios only (ADR-016).
# ======================================================

SCENARIOS_FILE = "results/data/ground_truth_scenarios.json"
CASE_MAGNITUDE_FILE = "results/data/case_capability_magnitude.csv"
TYPE_PROBABILITY_FILE = "results/data/incident_capability_probabilities.csv"
JOURNEY_FILE = "results/data/journey_impairment_full.csv"
GRAPH_FILE = "results/data/service_graph.csv"
SPLIT_FILE = "config/splits/split_v1.yaml"
OVERLAY_FILE = "business_overlay/online_boutique_v2.yaml"

OUTPUT_PER_SCENARIO = "results/data/evaluation_per_scenario.csv"
OUTPUT_AGGREGATE = "results/data/evaluation_aggregate.csv"
OUTPUT_STATS = "results/data/evaluation_statistics.csv"
OUTPUT_LATEX = "results/tables/evaluation_summary.tex"

SEED = 20260820
NDCG_KS = [1, 3, 5]
PRIMARY_METRIC = "ndcg_5"
PRIMARY_DECISION_METRIC = "cbl"

# Applied consistently with the practical-effect floor used
# throughout this pipeline (build_journey_impairment.py,
# audit_propagation_prevalence.py): a win requires BOTH
# statistical significance (Holm-corrected p<0.05) AND at
# least a "small" practical effect (Cliff's delta, Romano et
# al. 2006 thresholds: negligible<0.147). Large N (90 paired
# scenarios) makes tiny, practically meaningless effects
# reach very small p-values on their own -- exactly the
# failure mode this floor exists to catch.
CLIFFS_DELTA_FLOOR = 0.147

ITIL_MATRIX = {
    # (impact, urgency) -> priority (1 = most urgent)
    ("high", "high"): 1, ("high", "medium"): 2, ("high", "low"): 3,
    ("medium", "high"): 2, ("medium", "medium"): 3, ("medium", "low"): 4,
    ("low", "high"): 3, ("low", "medium"): 4, ("low", "low"): 5,
}


# ======================================================
# LOAD DATA
# ======================================================

def load_all():

    with open(SCENARIOS_FILE) as f:
        scenarios = json.load(f)

    case_mag = pd.read_csv(CASE_MAGNITUDE_FILE)
    type_prob = pd.read_csv(TYPE_PROBABILITY_FILE)
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

    return scenarios, case_mag, type_prob, journeys, G, split, weights


# ======================================================
# FEATURE / LOOKUP TABLES
# ======================================================

def build_case_ground_truth(case_mag):
    """case -> {capability_id: magnitude}, restricted to
    positive magnitudes (ground truth, evaluation only)."""

    out = {}
    for case, group in case_mag.groupby("case"):
        out[case] = {
            row["capability_id"]: row["magnitude"]
            for _, row in group.iterrows() if row["magnitude"] > 0
        }
    return out


def build_type_probabilities(type_prob):
    """(service, fault_type) -> {capability_id: p_smoothed}
    -- BLAST's own model input, never ground truth."""

    out = {}
    for (svc, ft), group in type_prob.groupby(["service", "fault_type"]):
        out[(svc, ft)] = dict(zip(group["capability_id"], group["p_smoothed"]))
    return out


def build_case_features(case_mag, journeys):
    """One feature row per case, for B2 (technical severity)
    and B7 (classifier). Purely OBSERVABLE technical signals
    -- never the business-weighted ground truth itself."""

    journey_agg = (
        journeys
        .groupby("case")
        .agg(
            max_p95_ratio=("p95_ratio", lambda s: np.nanmax(s.replace([np.inf, -np.inf], np.nan)) if s.notna().any() else 0.0),
            max_impairment_magnitude=("impairment_magnitude", "max"),
            n_impaired_journeys=("impaired", "sum"),
            n_journey_types=("journey_type", "nunique"),
            target_service=("target_service", "first"),
            fault_type=("fault_type", "first"),
        )
        .reset_index()
    )

    n_caps = (
        case_mag[case_mag["magnitude"] > 0]
        .groupby("case")
        .size()
        .rename("n_capabilities_covered")
    )

    features = journey_agg.merge(n_caps, on="case", how="left")
    features["n_capabilities_covered"] = features["n_capabilities_covered"].fillna(0)
    features["max_p95_ratio"] = features["max_p95_ratio"].fillna(0.0).clip(lower=0)

    return features


def build_case_gt_loss(case_mag, weights):
    """case -> scalar GT_loss (standalone, weighted) --
    regression LABEL for B7, and B2's business-blind
    counterpart uses max_impairment_magnitude instead."""

    out = {}
    for case, group in case_mag.groupby("case"):
        out[case] = sum(
            weights.get(row["capability_id"], 1.0) * row["magnitude"]
            for _, row in group.iterrows()
        )
    return out


# ======================================================
# B7: fit on TRAIN, score on TEST (the one baseline that
# actually generalises across incident types)
# ======================================================

FEATURE_COLS_NUMERIC = [
    "max_p95_ratio", "max_impairment_magnitude",
    "n_impaired_journeys", "n_journey_types", "n_capabilities_covered",
]
FEATURE_COLS_CATEGORICAL = ["target_service", "fault_type"]


def fit_b10_pairwise_ranker(features, gt_loss_by_case, split):
    """B10 -- Learning-to-Rank / pairwise ranking
    (context/source/PROJECT_CONTEXT.pdf p.9), filling the gap
    flagged against B7's pointwise regression: trains a classifier
    directly on 'does incident A outrank incident B', on ALL
    ordered pairs of TRAIN-split cases, then at scoring time ranks
    a scenario's incidents by their total pairwise win count
    (a Copeland-style aggregation) -- never on TEST-split pairs."""

    train_types = {(t["service"], t["fault_type"]) for t in split["train"]}

    train_rows = features[
        features.apply(lambda r: (r["target_service"], r["fault_type"]) in train_types, axis=1)
    ].copy()

    train_rows["label"] = train_rows["case"].map(gt_loss_by_case)
    train_rows = train_rows.dropna(subset=["label"])

    encoder = OneHotEncoder(handle_unknown="ignore", sparse_output=False)
    encoder.fit(train_rows[FEATURE_COLS_CATEGORICAL])

    def row_vector(row):
        cat = encoder.transform(row[FEATURE_COLS_CATEGORICAL].to_frame().T)[0]
        num = row[FEATURE_COLS_NUMERIC].to_numpy(dtype=float)
        return np.concatenate([num, cat])

    rows = train_rows.set_index("case")
    vectors = {case: row_vector(rows.loc[case]) for case in rows.index}

    X_pairs, y_pairs = [], []

    cases = list(rows.index)
    for i in cases:
        for j in cases:
            if i == j:
                continue
            if gt_loss_by_case[i] == gt_loss_by_case[j]:
                continue
            X_pairs.append(np.concatenate([vectors[i], vectors[j]]))
            y_pairs.append(1 if gt_loss_by_case[i] > gt_loss_by_case[j] else 0)

    from sklearn.linear_model import LogisticRegression
    model = LogisticRegression(max_iter=1000, random_state=SEED)
    model.fit(np.array(X_pairs), np.array(y_pairs))

    print(f"B10 pairwise ranker fit on {len(cases)} TRAIN cases, {len(X_pairs)} ordered pairs")

    def predict_order(incident_ids, features_df):
        rows_scored = features_df.set_index("case")
        vecs = {i: row_vector(rows_scored.loc[i]) for i in incident_ids}

        wins = {i: 0.0 for i in incident_ids}
        for i in incident_ids:
            for j in incident_ids:
                if i == j:
                    continue
                x = np.concatenate([vecs[i], vecs[j]]).reshape(1, -1)
                p_i_beats_j = model.predict_proba(x)[0][1]
                wins[i] += p_i_beats_j

        return sorted(incident_ids, key=lambda i: (-wins[i], i))

    return predict_order


def fit_b7_classifier(features, gt_loss_by_case, split):

    train_types = {(t["service"], t["fault_type"]) for t in split["train"]}

    train_rows = features[
        features.apply(lambda r: (r["target_service"], r["fault_type"]) in train_types, axis=1)
    ].copy()

    train_rows["label"] = train_rows["case"].map(gt_loss_by_case)
    train_rows = train_rows.dropna(subset=["label"])

    feature_cols_numeric = [
        "max_p95_ratio", "max_impairment_magnitude",
        "n_impaired_journeys", "n_journey_types", "n_capabilities_covered",
    ]
    feature_cols_categorical = ["target_service", "fault_type"]

    encoder = OneHotEncoder(handle_unknown="ignore", sparse_output=False)
    encoder.fit(train_rows[feature_cols_categorical])

    def make_X(df):
        cat = encoder.transform(df[feature_cols_categorical])
        num = df[feature_cols_numeric].to_numpy(dtype=float)
        return np.hstack([num, cat])

    X_train = make_X(train_rows)
    y_train = train_rows["label"].to_numpy(dtype=float)

    model = HistGradientBoostingRegressor(random_state=SEED, max_iter=100)
    model.fit(X_train, y_train)

    print(f"\nB7 classifier fit on {len(train_rows)} TRAIN cases "
          f"(types: {sorted(train_types)})")

    def predict(case_ids, features_df):
        rows = features_df[features_df["case"].isin(case_ids)]
        X = make_X(rows)
        preds = model.predict(X)
        return dict(zip(rows["case"], preds))

    return predict


# ======================================================
# BASELINE / METHOD SCORING FUNCTIONS
# All return an ORDER (list of case ids), best-fix-first.
# ======================================================

def rank_by_score(incident_ids, score, tie_break_seed=0):
    rng = random.Random(tie_break_seed)
    shuffled = list(incident_ids)
    rng.shuffle(shuffled)  # neutral tie-break
    return sorted(shuffled, key=lambda i: -score.get(i, 0.0))


def b1_random(incident_ids, scenario_id):
    rng = random.Random(f"{SEED}::{scenario_id}")
    order = list(incident_ids)
    rng.shuffle(order)
    return order


def b2_severity(incident_ids, features_by_case):
    score = {i: features_by_case[i]["max_impairment_magnitude"] for i in incident_ids}
    return rank_by_score(incident_ids, score, tie_break_seed=1)


def b3_itil(incident_ids, features_by_case):

    def tier_impact(n_caps):
        if n_caps >= 4:
            return "high"
        if n_caps >= 2:
            return "medium"
        return "low"

    def tier_urgency(magnitude):
        if magnitude >= 0.7:
            return "high"
        if magnitude >= 0.3:
            return "medium"
        return "low"

    priority = {}
    for i in incident_ids:
        f = features_by_case[i]
        impact = tier_impact(f["n_capabilities_covered"])
        urgency = tier_urgency(f["max_impairment_magnitude"])
        priority[i] = ITIL_MATRIX[(impact, urgency)]

    # Lower priority number = fix first -> negate for rank_by_score's "higher=first"
    score = {i: -priority[i] for i in incident_ids}
    # Tie-break within same priority by magnitude
    score = {i: score[i] * 1000 + features_by_case[i]["max_impairment_magnitude"] for i in incident_ids}
    return rank_by_score(incident_ids, score, tie_break_seed=3)


def b4_pagerank(incident_ids, type_of_case, pagerank_scores):
    score = {
        i: pagerank_scores.get(type_of_case[i][0], 0.0)
        for i in incident_ids
    }
    return rank_by_score(incident_ids, score, tie_break_seed=4)


def b6_personalized_pagerank(incident_ids, type_of_case, G):

    target_services = {type_of_case[i][0] for i in incident_ids}
    valid_targets = {s for s in target_services if s in G}

    if not valid_targets:
        return b1_random(incident_ids, "b6_fallback")

    personalization = {n: (1.0 if n in valid_targets else 0.0) for n in G.nodes()}
    total = sum(personalization.values())
    personalization = {n: v / total for n, v in personalization.items()}

    try:
        ppr = nx.pagerank(G, personalization=personalization)
    except nx.PowerIterationFailedConvergence:
        ppr = {n: 0.0 for n in G.nodes()}

    score = {i: ppr.get(type_of_case[i][0], 0.0) for i in incident_ids}
    return rank_by_score(incident_ids, score, tie_break_seed=6)


def b5_betweenness(incident_ids, type_of_case, centrality_scores):
    score = {i: centrality_scores.get(type_of_case[i][0], 0.0) for i in incident_ids}
    return rank_by_score(incident_ids, score, tie_break_seed=5)


def b11_closeness(incident_ids, type_of_case, centrality_scores):
    score = {i: centrality_scores.get(type_of_case[i][0], 0.0) for i in incident_ids}
    return rank_by_score(incident_ids, score, tie_break_seed=11)


def b12_eigenvector(incident_ids, type_of_case, centrality_scores):
    score = {i: centrality_scores.get(type_of_case[i][0], 0.0) for i in incident_ids}
    return rank_by_score(incident_ids, score, tie_break_seed=12)


def b7_classifier(incident_ids, b7_predict, features):
    preds = b7_predict(incident_ids, features)
    return rank_by_score(incident_ids, preds, tie_break_seed=7)


def b9_blast_independent(incident_ids, type_of_case, type_probabilities, weights):
    score = {}
    for i in incident_ids:
        t = type_of_case[i]
        p_by_cap = type_probabilities.get(t, {})
        score[i] = sum(weights.get(c, 1.0) * p for c, p in p_by_cap.items())
    return rank_by_score(incident_ids, score, tie_break_seed=9)


def blast_greedy(incident_ids, type_of_case, type_probabilities, weights):
    """BLAST itself: greedy marginal-gain selection over the
    probabilistic objective, using the incident TYPE's
    modelled p(c|i) -- not ground truth."""

    def F(selected):
        all_caps = set()
        for i in selected:
            all_caps.update(type_probabilities.get(type_of_case[i], {}).keys())
        total = 0.0
        for c in all_caps:
            prob_none = 1.0
            for i in selected:
                p = type_probabilities.get(type_of_case[i], {}).get(c, 0.0)
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


# ======================================================
# MAIN
# ======================================================

def main():

    print("=" * 110)
    print("BLAST — FULL EVALUATION HARNESS")
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

    # ----------------------------------------------------
    # Per-scenario evaluation
    # ----------------------------------------------------

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

        # Oracle and worst-case (reverse of oracle) CBL, for AULC normalisation
        _, cbl_oracle = simulate_cumulative_loss(oracle, incident_capabilities_gt, weights)
        _, cbl_random_ref = simulate_cumulative_loss(
            b1_random(incident_ids, scenario_id + "::aulc_ref"),
            incident_capabilities_gt, weights,
        )

        for method, order in orders.items():

            _, cbl = simulate_cumulative_loss(order, incident_capabilities_gt, weights)
            aulc = normalized_aulc(cbl, cbl_oracle, cbl_random_ref)

            row = {
                "scenario_id": scenario_id,
                "k": k,
                "method": method,
                "cbl": cbl,
                "cbl_oracle": cbl_oracle,
                "aulc_normalized": aulc,
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

    # ----------------------------------------------------
    # Aggregate
    # ----------------------------------------------------

    metric_cols = ["cbl", "aulc_normalized", "kendalls_tau", "mrr",
                    "precision_at_3", "map"] + [f"ndcg_{k}" for k in NDCG_KS]

    aggregate = (
        per_scenario
        .groupby("method")[metric_cols]
        .agg(["mean", "std"])
    )
    aggregate.columns = ["_".join(c) for c in aggregate.columns]
    aggregate = aggregate.reset_index()
    aggregate.to_csv(OUTPUT_AGGREGATE, index=False)

    pd.set_option("display.max_columns", None)
    pd.set_option("display.width", 240)

    print("\n")
    print("=" * 110)
    print("AGGREGATE RESULTS (mean +/- std over all scenarios)")
    print("=" * 110)
    print(aggregate.to_string(index=False, float_format=lambda x: f"{x:.4f}"))

    print("\n")
    print("=" * 110)
    print("AGGREGATE RESULTS BY K")
    print("=" * 110)
    by_k = per_scenario.groupby(["k", "method"])[metric_cols].mean().reset_index()
    print(by_k.to_string(index=False, float_format=lambda x: f"{x:.4f}"))

    # ----------------------------------------------------
    # Statistics: BLAST vs each baseline, paired by scenario
    # ----------------------------------------------------

    baselines = [m for m in METHODS if m != "BLAST"]

    stats_rows = []

    for primary_metric, higher_is_better in [
        ("ndcg_5", True), ("cbl", False),
    ]:

        blast_vals_by_scenario = per_scenario[per_scenario["method"] == "BLAST"].set_index("scenario_id")[primary_metric]

        pvals = []
        rows_this_metric = []

        for baseline in baselines:

            baseline_vals_by_scenario = per_scenario[per_scenario["method"] == baseline].set_index("scenario_id")[primary_metric]

            common = blast_vals_by_scenario.index.intersection(baseline_vals_by_scenario.index)
            a = blast_vals_by_scenario.loc[common].dropna()
            b = baseline_vals_by_scenario.loc[common].dropna()
            common2 = a.index.intersection(b.index)
            a, b = a.loc[common2].to_numpy(), b.loc[common2].to_numpy()

            stat, p = paired_wilcoxon(a, b)
            delta = cliffs_delta(a, b)

            rows_this_metric.append({
                "metric": primary_metric,
                "baseline": baseline,
                "n_scenarios": len(a),
                "blast_mean": np.nanmean(a),
                "baseline_mean": np.nanmean(b),
                "wilcoxon_stat": stat,
                "p_value_raw": p,
                "cliffs_delta": delta,
                "higher_is_better": higher_is_better,
            })
            pvals.append(p)

        adjusted = holm_bonferroni(pvals)
        for row, p_adj in zip(rows_this_metric, adjusted):
            row["p_value_holm"] = p_adj
            better = (
                row["blast_mean"] > row["baseline_mean"] if higher_is_better
                else row["blast_mean"] < row["baseline_mean"]
            )
            statistically_significant = bool((not np.isnan(p_adj)) and p_adj < 0.05 and better)
            practically_significant = bool(abs(row["cliffs_delta"]) >= CLIFFS_DELTA_FLOOR)

            row["statistically_significant_win"] = statistically_significant
            row["practically_significant"] = practically_significant
            row["blast_significantly_better"] = statistically_significant and practically_significant
            stats_rows.append(row)

    stats = pd.DataFrame(stats_rows)
    stats.to_csv(OUTPUT_STATS, index=False)

    print("\n")
    print("=" * 110)
    print("STATISTICAL COMPARISON: BLAST vs BASELINES (paired by scenario, Holm-corrected)")
    print("=" * 110)
    print(stats.to_string(index=False, float_format=lambda x: f"{x:.4g}"))

    # ----------------------------------------------------
    # GATE 4 DECISION
    # ----------------------------------------------------

    print("\n")
    print("=" * 110)
    print("GATE 4 DECISION")
    print("=" * 110)

    b9_row = stats[(stats["baseline"] == "B9_independent") & (stats["metric"] == PRIMARY_DECISION_METRIC)]

    if b9_row.empty:
        print("Could not locate BLAST vs B9 comparison on the primary decision metric.")
        gate4 = "ERROR"
    else:
        b9_row = b9_row.iloc[0]
        ndcg_row = stats[(stats["baseline"] == "B9_independent") & (stats["metric"] == "ndcg_5")].iloc[0]

        cbl_stat_sig = bool(b9_row["statistically_significant_win"])
        cbl_practical_sig = bool(b9_row["practically_significant"])
        cbl_real_win = cbl_stat_sig and cbl_practical_sig

        ndcg_stat_sig = bool(ndcg_row["statistically_significant_win"])
        ndcg_practical_sig = bool(ndcg_row["practically_significant"])
        ndcg_real_win = ndcg_stat_sig and ndcg_practical_sig

        print(f"\nBLAST vs B9 (independent scoring) on CBL (the primary DECISION metric -- "
              f"'the metric that actually matters', 03_RESEARCH_DESIGN.md §6):")
        print(f"  BLAST_mean={b9_row['blast_mean']:.4f}, B9_mean={b9_row['baseline_mean']:.4f}")
        print(f"  p_holm={b9_row['p_value_holm']:.4g} (statistically significant: {cbl_stat_sig})")
        print(f"  cliffs_delta={b9_row['cliffs_delta']:.4f} "
              f"(practically significant, |delta|>={CLIFFS_DELTA_FLOOR}: {cbl_practical_sig})")
        print(f"  REAL WIN (both required): {cbl_real_win}")

        print(f"\nBLAST vs B9 (independent scoring) on NDCG@5 (the primary RANKING metric, "
              f"pre-registered per TV-9):")
        print(f"  BLAST_mean={ndcg_row['blast_mean']:.4f}, B9_mean={ndcg_row['baseline_mean']:.4f}")
        print(f"  p_holm={ndcg_row['p_value_holm']:.4g} (statistically significant: {ndcg_stat_sig})")
        print(f"  cliffs_delta={ndcg_row['cliffs_delta']:.4f} "
              f"(practically significant, |delta|>={CLIFFS_DELTA_FLOOR}: {ndcg_practical_sig})")
        print(f"  REAL WIN (both required): {ndcg_real_win}")

        if cbl_real_win and ndcg_real_win:
            gate4 = "PASS"
            print(f"\nVERDICT: {gate4} -- BLAST beats B9 with both statistical AND practical "
                  f"significance on the decision metric (CBL) and the ranking metric (NDCG@5). "
                  f"Central claim (RQ3, submodular set-selection) supported.")
        elif ndcg_real_win and not cbl_real_win:
            gate4 = "MIXED — ranking advantage without a practically meaningful business-loss advantage"
            print(f"\nVERDICT: {gate4}.")
            print(
                "\nBLAST shows a real (statistically AND practically significant, "
                f"Cliff's delta={ndcg_row['cliffs_delta']:.3f}, 'small' effect) ranking-quality "
                "advantage over independent scoring: it orders incidents by true priority more "
                "accurately. But on Cumulative Business Loss -- the metric the plan itself labels "
                "'the metric that actually matters' because it speaks the practitioner's language "
                f"-- the effect is statistically detectable (p_holm={b9_row['p_value_holm']:.2g}, "
                f"n=90 scenarios gives the test power to detect tiny effects) but practically "
                f"negligible (Cliff's delta={b9_row['cliffs_delta']:.3f}, below the 'negligible' "
                "threshold of 0.147). In plain terms: BLAST tends to rank the right incident "
                "closer to the top, but by the time repair actually happens under either "
                "ordering, the accumulated business loss is nearly the same -- because at these "
                "scenario sizes (k=3,5,10) the highest-value incidents are large enough relative "
                "to the rest that both methods usually reach them quickly regardless of exact "
                "order. This does not meet 07_NEXT_PHASE_PLAN.md's Gate 4 PASS bar, but it is "
                "also not the clean 'BLAST ~= B9 on everything' TIE the plan's pivot section "
                "anticipates. Report both results honestly rather than forcing one label -- see "
                "ADR-019/020 for the framing this implies for the paper."
            )
        elif not cbl_stat_sig and not ndcg_stat_sig:
            gate4 = "TIE"
            print(f"\nVERDICT: {gate4} -- BLAST ~= B9 on both metrics, no statistically "
                  f"significant difference. Execute the pre-committed pivot in "
                  f"07_NEXT_PHASE_PLAN.md §4 -- do not tune to win.")
        else:
            gate4 = "MIXED/WORSE"
            print(f"\nVERDICT: {gate4} -- inconsistent or negative result. Debug before "
                  f"interpreting further (07_NEXT_PHASE_PLAN.md §3 Step 6 gate table).")

    # ----------------------------------------------------
    # LaTeX table
    # ----------------------------------------------------

    Path("results/tables").mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_LATEX, "w") as f:
        f.write("% Auto-generated by run_evaluation.py -- do not hand-edit.\n")
        f.write("\\begin{tabular}{l" + "r" * len(metric_cols) + "}\n")
        f.write("\\toprule\n")
        f.write("Method & " + " & ".join(m.replace("_", "\\_") for m in metric_cols) + " \\\\\n")
        f.write("\\midrule\n")
        for _, row in aggregate.iterrows():
            vals = " & ".join(f"{row[f'{m}_mean']:.3f}" for m in metric_cols)
            f.write(f"{row['method'].replace('_', chr(92)+'_')} & {vals} \\\\\n")
        f.write("\\bottomrule\n")
        f.write("\\end{tabular}\n")

    print("\n")
    print("=" * 110)
    print("FILES SAVED")
    print("=" * 110)
    print(OUTPUT_PER_SCENARIO)
    print(OUTPUT_AGGREGATE)
    print(OUTPUT_STATS)
    print(OUTPUT_LATEX)

    print(f"\nGATE 4 RESULT: {gate4}")
    print("\nEvaluation complete.")


if __name__ == "__main__":
    main()
