import numpy as np
from scipy.stats import kendalltau, wilcoxon, mannwhitneyu


# ======================================================
# BLAST — EVALUATION METRICS LIBRARY
# ======================================================
#
# context/03_RESEARCH_DESIGN.md §6. Shared by
# run_evaluation.py. Operates on plain Python
# lists/dicts, not the frozen Incident/Scenario dataclasses
# in CLAUDE.md's "Frozen interfaces" -- consistent with the
# rest of this experimental-scripts phase (flat data
# structures throughout; the dataclass contract is the
# target for the eventual src/blast/ package, not this
# phase, see 02_ARCHITECTURE.md).
# ======================================================


# ------------------------------------------------------
# Ranking quality
# ------------------------------------------------------

def ndcg_at_k(ordered_ids, relevance, k):
    """ordered_ids: candidate ranking, best first.
    relevance: dict id -> non-negative graded relevance
    (here, GT_loss). NDCG@k against the IDEAL order (sorted
    by relevance desc)."""

    def dcg(ids):
        total = 0.0
        for rank, i in enumerate(ids[:k], start=1):
            total += relevance.get(i, 0.0) / np.log2(rank + 1)
        return total

    ideal_order = sorted(relevance.keys(), key=lambda i: -relevance[i])

    idcg = dcg(ideal_order)
    if idcg == 0:
        return np.nan

    return dcg(ordered_ids) / idcg


def kendalls_tau(ordered_ids, ground_truth_order):
    """Kendall's tau between a candidate order and the
    ground-truth order, over the common set of ids."""

    common = [i for i in ordered_ids if i in ground_truth_order]
    if len(common) < 2:
        return np.nan

    candidate_ranks = {i: r for r, i in enumerate(ordered_ids)}
    gt_ranks = {i: r for r, i in enumerate(ground_truth_order)}

    x = [candidate_ranks[i] for i in common]
    y = [gt_ranks[i] for i in common]

    tau, _ = kendalltau(x, y)
    return tau


def mrr(ordered_ids, ground_truth_order):
    """Reciprocal rank of the single worst (first-to-fix)
    ground-truth incident in the candidate ordering."""

    if not ground_truth_order:
        return np.nan

    target = ground_truth_order[0]

    if target not in ordered_ids:
        return 0.0

    rank = ordered_ids.index(target) + 1
    return 1.0 / rank


def precision_at_k(ordered_ids, ground_truth_order, k):
    """Fraction of the candidate's top-k that fall in the
    ground truth's top-k."""

    top_k_candidate = set(ordered_ids[:k])
    top_k_truth = set(ground_truth_order[:k])

    if not top_k_truth:
        return np.nan

    return len(top_k_candidate & top_k_truth) / len(top_k_truth)


def average_precision(ordered_ids, ground_truth_order, k):
    """Standard Average Precision: mean of Precision@rank taken at
    each position in the candidate order where that item is one of
    the ground truth's top-k ("relevant"). Rewards relevant items
    appearing EARLY, not just being present somewhere in the top-k
    (which is all precision_at_k checks) -- the brief's requested
    'MAP' metric (03_RESEARCH_DESIGN.md never specified this one;
    added directly against context/source/PROJECT_CONTEXT.pdf p.12)."""

    relevant = set(ground_truth_order[:k])
    if not relevant:
        return np.nan

    hits = 0
    precisions = []

    for rank, incident in enumerate(ordered_ids, start=1):
        if incident in relevant:
            hits += 1
            precisions.append(hits / rank)

    if not precisions:
        return 0.0

    return sum(precisions) / len(relevant)


# ------------------------------------------------------
# Decision quality: sequential-repair simulation
# ------------------------------------------------------

def simulate_cumulative_loss(ordered_ids, incident_capabilities, weights, repair_cost=None):
    """ordered_ids: repair order, first incident fixed first.
    incident_capabilities: dict incident_id -> {capability_id: magnitude}.
    weights: dict capability_id -> value_per_min.
    repair_cost: dict incident_id -> cost (default: uniform 1.0 each,
    i.e. "one engineer, one incident at a time" per
    03_RESEARCH_DESIGN.md §2, repair-capacity default --
    stated explicitly since no real repair-duration data exists).

    Returns (loss_curve, CBL). loss_curve[t] is the loss RATE
    incurred while incident t is being repaired (i.e. the
    business impact of everything still broken, using union/
    max composition across the still-unrepaired incidents --
    the same conservative composition rule as scenario
    synthesis, TV-2). CBL = sum(loss_curve[t] * cost[t]).
    """

    if repair_cost is None:
        repair_cost = {i: 1.0 for i in ordered_ids}

    remaining = list(ordered_ids)
    loss_curve = []

    all_capabilities = set()
    for caps in incident_capabilities.values():
        all_capabilities.update(caps.keys())

    for t in ordered_ids:

        loss_rate = 0.0
        for c in all_capabilities:
            still_impaired_magnitude = max(
                (incident_capabilities[i].get(c, 0.0) for i in remaining),
                default=0.0,
            )
            loss_rate += weights.get(c, 1.0) * still_impaired_magnitude

        loss_curve.append(loss_rate)
        remaining.remove(t)

    cbl = sum(loss_curve[i] * repair_cost[ordered_ids[i]] for i in range(len(ordered_ids)))

    return loss_curve, cbl


def normalized_aulc(cbl_method, cbl_oracle, cbl_random):
    """0 = matches the oracle ordering, 1 = matches random.
    Lower is better. NaN if oracle and random tie (degenerate
    scenario -- all orderings equivalent)."""

    denom = cbl_random - cbl_oracle
    if denom == 0:
        return np.nan

    return (cbl_method - cbl_oracle) / denom


# ------------------------------------------------------
# Ground-truth (oracle) ordering: greedy sequential
# recovery of the most unrecovered measured business value,
# using MEASURED magnitudes only -- never F(S), never a
# fitted model (07_NEXT_PHASE_PLAN.md §1.3 / Step 5b).
# ------------------------------------------------------

def oracle_order(incident_ids, incident_capabilities, weights):

    def coverage_value(selected):
        all_caps = set()
        for i in selected:
            all_caps.update(incident_capabilities[i].keys())
        total = 0.0
        for c in all_caps:
            total += weights.get(c, 1.0) * max(
                incident_capabilities[i].get(c, 0.0) for i in selected
            )
        return total

    remaining = list(incident_ids)
    selected = []

    while remaining:

        current_value = coverage_value(selected) if selected else 0.0

        best_incident = None
        best_gain = -np.inf

        for i in remaining:
            gain = coverage_value(selected + [i]) - current_value
            if gain > best_gain or (gain == best_gain and (best_incident is None or i < best_incident)):
                best_gain = gain
                best_incident = i

        selected.append(best_incident)
        remaining.remove(best_incident)

    return selected


def gt_loss_per_incident(incident_ids, incident_capabilities, weights):
    """GT_loss(i) = Sum_c w_c * magnitude(c|i) -- standalone
    measured loss, used for NDCG/MRR relevance grading (not
    the sequential/oracle order itself, which accounts for
    overlap)."""

    return {
        i: sum(weights.get(c, 1.0) * m for c, m in incident_capabilities[i].items())
        for i in incident_ids
    }


# ------------------------------------------------------
# Statistics
# ------------------------------------------------------

def cliffs_delta(sample_a, sample_b):
    """Two-sample Cliff's delta via the Mann-Whitney U
    relationship: delta = 2U/(n1*n2) - 1. Positive => sample_a
    stochastically greater than sample_b."""

    a = np.asarray(sample_a, dtype=float)
    b = np.asarray(sample_b, dtype=float)

    n1, n2 = len(a), len(b)
    if n1 == 0 or n2 == 0:
        return np.nan

    if np.all(a == a[0]) and np.all(b == b[0]) and a[0] == b[0]:
        return 0.0

    result = mannwhitneyu(a, b, alternative="two-sided")
    return (2.0 * result.statistic) / (n1 * n2) - 1.0


def paired_wilcoxon(sample_a, sample_b):
    """Wilcoxon signed-rank test for paired samples (same
    scenarios, two methods). Returns (statistic, p_value).
    NaN if all differences are zero (scipy raises)."""

    a = np.asarray(sample_a, dtype=float)
    b = np.asarray(sample_b, dtype=float)

    if np.allclose(a, b):
        return np.nan, 1.0

    try:
        result = wilcoxon(a, b)
        return result.statistic, result.pvalue
    except ValueError:
        return np.nan, np.nan


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
