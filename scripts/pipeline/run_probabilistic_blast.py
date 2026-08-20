import pandas as pd
import numpy as np


# ======================================================
# BLAST — PROBABILISTIC WEIGHTED OBJECTIVE
# ======================================================
#
# context/07_NEXT_PHASE_PLAN.md Step 5a / task list #9.
# ADR-016.
#
# F(S) = Sum_c  w_c * P(c impaired | S)
# P(c impaired | S) = 1 - Prod_{i in S} (1 - p(c|i))
#
# under independent activation. Replaces the pilot's binary
# coverage objective (run_blast_greedy.py /
# rerun_pilot_journey_level.py), which is kept as-is
# (historical artifacts, do not overwrite).
#
# Re-runs the submodularity empirical check as a regression
# test: weighted probabilistic coverage under independent
# activation is the standard KKT submodular setting, and
# this must still show 0 violations.
# ======================================================

PROBABILITIES_FILE = "results/data/incident_capability_probabilities.csv"

OUTPUT_GREEDY = "results/data/blast_greedy_probabilistic.csv"
OUTPUT_SUBMODULARITY = "results/data/submodularity_check_probabilistic.csv"

K_VALUES = [1, 2, 3, 4, 5, 6, 8, 10]


def load_incident_capability_probabilities():

    df = pd.read_csv(PROBABILITIES_FILE)

    df["incident_type"] = df["service"] + "::" + df["fault_type"]

    p_lookup = {}
    weight_lookup = {}

    for _, row in df.iterrows():
        p_lookup[(row["incident_type"], row["capability_id"])] = row["p_smoothed"]

    capability_ids = sorted(df["capability_id"].unique())
    incident_types = sorted(df["incident_type"].unique())

    return df, p_lookup, capability_ids, incident_types


def build_objective(p_lookup, capability_ids, weights):

    def F(selected_incidents):
        """Expected weighted capability coverage under
        independent activation."""

        total = 0.0

        for c in capability_ids:

            prob_none_impaired = 1.0
            for i in selected_incidents:
                p = p_lookup.get((i, c), 0.0)
                prob_none_impaired *= (1.0 - p)

            prob_impaired = 1.0 - prob_none_impaired
            total += weights.get(c, 1.0) * prob_impaired

        return total

    return F


def greedy_select(all_incidents, F):

    selected = []
    rows = []

    for step in range(1, len(all_incidents) + 1):

        remaining = [i for i in all_incidents if i not in selected]
        if not remaining:
            break

        current_value = F(selected)

        candidates = []
        for incident in remaining:
            gain = F(selected + [incident]) - current_value
            candidates.append((incident, gain))

        candidates.sort(key=lambda x: (-x[1], x[0]))
        winner, gain = candidates[0]

        selected.append(winner)

        rows.append({
            "selection_step": step,
            "selected_incident_type": winner,
            "marginal_gain": gain,
            "cumulative_F": F(selected),
        })

    return selected, pd.DataFrame(rows)


def submodularity_check(all_incidents, F, n_checks=200, seed=20260820):
    """Empirical regression test: for nested A subset B,
    marginal gain of adding x to A must be >= marginal gain
    of adding x to B."""

    rng = np.random.default_rng(seed)

    violations = 0
    checks = 0
    rows = []

    for _ in range(n_checks):

        # Random x, and random nested A subset B not containing x
        x = rng.choice(all_incidents)
        others = [i for i in all_incidents if i != x]

        rng.shuffle(others)
        split_a = rng.integers(0, len(others) + 1)
        split_b = rng.integers(split_a, len(others) + 1)

        A = others[:split_a]
        B = others[:split_b]

        gain_A = F(A + [x]) - F(A)
        gain_B = F(B + [x]) - F(B)

        checks += 1
        violated = gain_A + 1e-9 < gain_B

        if violated:
            violations += 1

        rows.append({
            "x": x,
            "|A|": len(A),
            "|B|": len(B),
            "gain_A": gain_A,
            "gain_B": gain_B,
            "violation": violated,
        })

    return checks, violations, pd.DataFrame(rows)


def main():

    print("=" * 110)
    print("BLAST — PROBABILISTIC WEIGHTED OBJECTIVE")
    print("=" * 110)

    df, p_lookup, capability_ids, incident_types = load_incident_capability_probabilities()

    print(f"\nIncident types: {len(incident_types)}")
    print(f"Capabilities: {len(capability_ids)}")

    weight_lookup = (
        df[["capability_id", "value_per_min"]].drop_duplicates()
        if "value_per_min" in df.columns
        else None
    )

    # value_per_min isn't in the probabilities file (that's the
    # magnitude file) -- pull it from the overlay directly.
    import yaml
    with open("business_overlay/online_boutique_v2.yaml") as f:
        overlay = yaml.safe_load(f)
    weights = {c["id"]: c["value_per_min"] for c in overlay["capabilities"]}

    F = build_objective(p_lookup, capability_ids, weights)

    print("\n")
    print("=" * 110)
    print("GREEDY SELECTION (PROBABILISTIC, WEIGHTED)")
    print("=" * 110)

    selected, greedy_results = greedy_select(incident_types, F)

    print(
        greedy_results.to_string(index=False, float_format=lambda x: f"{x:.4f}")
    )

    # ----------------------------------------------------
    # Independent baseline (standalone score, no set reasoning)
    # ----------------------------------------------------

    standalone_scores = {i: F([i]) for i in incident_types}
    baseline_order = sorted(incident_types, key=lambda i: (-standalone_scores[i], i))

    print("\n")
    print("=" * 110)
    print("BLAST (SET-SELECTION) VS INDEPENDENT BASELINE — F(S) AT EACH K")
    print("=" * 110)

    comparison_rows = []
    for k in K_VALUES:
        if k > len(incident_types):
            continue
        blast_S = selected[:k]
        baseline_S = baseline_order[:k]
        comparison_rows.append({
            "K": k,
            "BLAST_F": F(blast_S),
            "baseline_F": F(baseline_S),
            "gain": F(blast_S) - F(baseline_S),
        })

    comparison = pd.DataFrame(comparison_rows)
    print(comparison.to_string(index=False, float_format=lambda x: f"{x:.4f}"))

    # ----------------------------------------------------
    # Submodularity regression check
    # ----------------------------------------------------

    print("\n")
    print("=" * 110)
    print("SUBMODULARITY REGRESSION CHECK (PROBABILISTIC OBJECTIVE)")
    print("=" * 110)

    checks, violations, check_df = submodularity_check(incident_types, F)

    print(f"\nChecks: {checks}")
    print(f"Violations: {violations}")

    if violations == 0:
        print("PASS -- no submodularity violations detected under the probabilistic objective.")
    else:
        print("FAIL -- submodularity violated. Investigate before proceeding.")
        print(check_df[check_df["violation"]].to_string(index=False))

    # ----------------------------------------------------
    # Save
    # ----------------------------------------------------

    greedy_results.to_csv(OUTPUT_GREEDY, index=False)
    check_df.to_csv(OUTPUT_SUBMODULARITY, index=False)
    comparison.to_csv("results/data/blast_vs_baseline_probabilistic.csv", index=False)

    print("\n")
    print("=" * 110)
    print("FILES SAVED")
    print("=" * 110)
    print(OUTPUT_GREEDY)
    print(OUTPUT_SUBMODULARITY)
    print("results/data/blast_vs_baseline_probabilistic.csv")

    print(f"\nSubmodularity check: {'PASS' if violations == 0 else 'FAIL'}")
    print("\nProbabilistic BLAST run complete.")


if __name__ == "__main__":
    main()
