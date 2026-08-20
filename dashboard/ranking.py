import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PIPELINE = ROOT / "scripts" / "pipeline"

# Reuse the exact same ranking/metric logic the evaluation harness
# uses -- never reimplement it here, to avoid the dashboard silently
# drifting from what was actually measured (the whole point of
# ADR-014's "shared library" pattern, applied again here).
if str(PIPELINE) not in sys.path:
    sys.path.insert(0, str(PIPELINE))

from blast_eval_lib import (  # noqa: E402
    simulate_cumulative_loss, ndcg_at_k, kendalls_tau, mrr,
)


def blast_greedy_order(incident_ids, id_to_type, type_probabilities, weights):
    """Live re-computation of BLAST's greedy marginal-gain order,
    identical logic to scripts/pipeline/run_evaluation.py."""

    def F(selected):
        all_caps = set()
        for i in selected:
            all_caps.update(type_probabilities.get(id_to_type[i], {}).keys())
        total = 0.0
        for c in all_caps:
            prob_none = 1.0
            for i in selected:
                p = type_probabilities.get(id_to_type[i], {}).get(c, 0.0)
                prob_none *= (1.0 - p)
            total += weights.get(c, 1.0) * (1.0 - prob_none)
        return total

    remaining = list(incident_ids)
    selected = []
    steps = []

    while remaining:
        current = F(selected)
        gains = [(i, F(selected + [i]) - current) for i in remaining]
        gains.sort(key=lambda x: (-x[1], x[0]))
        winner, gain = gains[0]
        selected.append(winner)
        remaining.remove(winner)
        steps.append({"incident": winner, "marginal_gain": gain, "cumulative_F": F(selected)})

    return selected, steps


def independent_order(incident_ids, id_to_type, type_probabilities, weights):

    score = {}
    for i in incident_ids:
        p_by_cap = type_probabilities.get(id_to_type[i], {})
        score[i] = sum(weights.get(c, 1.0) * p for c, p in p_by_cap.items())

    order = sorted(incident_ids, key=lambda i: (-score[i], i))
    return order, score


def evaluate_order(order, incident_capabilities_gt, weights, oracle_order=None):
    """Returns CBL and, if an oracle order is supplied, ranking metrics."""

    loss_curve, cbl = simulate_cumulative_loss(order, incident_capabilities_gt, weights)

    result = {"cbl": cbl, "loss_curve": loss_curve}

    if oracle_order is not None:
        gt_loss = {
            i: sum(weights.get(c, 1.0) * m for c, m in incident_capabilities_gt[i].items())
            for i in order
        }
        result["kendalls_tau"] = kendalls_tau(order, oracle_order)
        result["mrr"] = mrr(order, oracle_order)
        result["ndcg_5"] = ndcg_at_k(order, gt_loss, min(5, len(order)))

    return result
