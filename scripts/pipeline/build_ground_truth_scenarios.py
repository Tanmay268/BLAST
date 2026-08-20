import json
import random
from itertools import combinations
from pathlib import Path

import pandas as pd
import yaml

from blast_eval_lib import oracle_order, gt_loss_per_incident


# ======================================================
# BLAST — GROUND-TRUTH SCENARIOS
# ======================================================
#
# context/07_NEXT_PHASE_PLAN.md Step 5b / task list #10.
#
# Composes multi-incident scenarios from TEST-split
# incident occurrences (ADR-016: evaluation happens on
# held-out incident types so that whatever the pipeline
# fits on train -- B7's classifier -- is judged fairly).
# k incidents from DISTINCT (service, fault) TYPES per
# scenario (never two reps of the same type in one
# scenario -- that would be a degenerate, not a multi-
# incident, scenario). >=30 scenarios per k in {3,5,10}.
#
# Ground truth per scenario:
#  - GT_loss(i): standalone measured loss per incident
#    (relevance grade for NDCG).
#  - oracle_order: sequential greedy order over MEASURED
#    magnitudes (union/max composition, TV-2), NEVER F(S)
#    and never a fitted model -- the plain, model-free rule
#    that makes it defensible as an oracle.
#
# Composition assumption (TV-2, explicit): combining
# independently-injected faults' measured effects assumes
# they compose; we use union/max, the conservative choice.
# ======================================================

CASE_MAGNITUDE_FILE = "results/data/case_capability_magnitude.csv"
SPLIT_FILE = "config/splits/split_v1.yaml"
OVERLAY_FILE = "business_overlay/online_boutique_v2.yaml"

OUTPUT_FILE = "results/data/ground_truth_scenarios.json"
OUTPUT_SUMMARY = "results/data/ground_truth_scenarios_summary.csv"

K_VALUES = [3, 5, 10]
SCENARIOS_PER_K = 30
SEED = 20260820


def load_weights():
    with open(OVERLAY_FILE) as f:
        overlay = yaml.safe_load(f)
    return {c["id"]: c["value_per_min"] for c in overlay["capabilities"]}


def load_test_types():
    with open(SPLIT_FILE) as f:
        split = yaml.safe_load(f)
    return [(t["service"], t["fault_type"]) for t in split["test"]]


def main():

    print("=" * 110)
    print("BLAST — GROUND-TRUTH SCENARIO SYNTHESIS")
    print("=" * 110)

    case_mag = pd.read_csv(CASE_MAGNITUDE_FILE)
    weights = load_weights()
    test_types = load_test_types()

    print(f"\nTest-split incident types: {len(test_types)}")
    for s, f in test_types:
        print(f"  {s} / {f}")

    # ----------------------------------------------------
    # Build case -> {capability: magnitude}, restricted to
    # TEST-split types
    # ----------------------------------------------------

    test_type_set = set(test_types)
    case_mag = case_mag[
        case_mag.apply(lambda r: (r["service"], r["fault_type"]) in test_type_set, axis=1)
    ]

    cases_by_type = {}
    incident_capabilities = {}
    type_of_case = {}

    for case, group in case_mag.groupby("case"):
        service = group["service"].iloc[0]
        fault_type = group["fault_type"].iloc[0]
        cases_by_type.setdefault((service, fault_type), []).append(case)
        type_of_case[case] = (service, fault_type)
        incident_capabilities[case] = {
            row["capability_id"]: row["magnitude"]
            for _, row in group.iterrows()
            if row["magnitude"] > 0
        }

    print(f"\nTest-split cases with capability data: {len(incident_capabilities)}")
    for t, cases in sorted(cases_by_type.items()):
        print(f"  {t}: {len(cases)} reps -- {cases}")

    available_types = list(cases_by_type.keys())

    if len(available_types) < 3:
        raise RuntimeError(
            f"Only {len(available_types)} test-split incident types with data -- "
            f"need at least 3 for k=3 scenarios."
        )

    # ----------------------------------------------------
    # Synthesize scenarios per k
    # ----------------------------------------------------

    rng = random.Random(SEED)

    all_scenarios = []
    summary_rows = []

    for k in K_VALUES:

        if k > len(available_types):
            print(f"\nWARNING: k={k} exceeds {len(available_types)} available test-split "
                  f"incident types -- capping at k={len(available_types)} "
                  f"(only 1 possible type-combination, varied by repetition draw).")
            k_eff = len(available_types)
        else:
            k_eff = k

        all_type_combos = list(combinations(available_types, k_eff))

        n_generated = 0
        seen_scenarios = set()
        attempts = 0
        max_attempts = SCENARIOS_PER_K * 50

        while n_generated < SCENARIOS_PER_K and attempts < max_attempts:

            attempts += 1

            type_combo = rng.choice(all_type_combos)

            incident_ids = tuple(sorted(
                rng.choice(cases_by_type[t]) for t in type_combo
            ))

            if len(set(incident_ids)) != k_eff:
                continue  # degenerate draw, retry

            if incident_ids in seen_scenarios:
                continue

            seen_scenarios.add(incident_ids)
            n_generated += 1

            incident_ids_list = list(incident_ids)

            scenario_id = f"scenario_k{k}_{n_generated:03d}"

            gt_loss = gt_loss_per_incident(
                incident_ids_list,
                {i: incident_capabilities[i] for i in incident_ids_list},
                weights,
            )

            oracle = oracle_order(
                incident_ids_list,
                {i: incident_capabilities[i] for i in incident_ids_list},
                weights,
            )

            all_scenarios.append({
                "scenario_id": scenario_id,
                "k": k,
                "incident_ids": incident_ids_list,
                "incident_types": [
                    f"{type_of_case[i][0]}::{type_of_case[i][1]}"
                    for i in incident_ids_list
                ],
                "gt_loss": gt_loss,
                "oracle_order": oracle,
            })

            summary_rows.append({
                "scenario_id": scenario_id,
                "k": k,
                "incident_ids": ";".join(incident_ids_list),
                "total_gt_loss": sum(gt_loss.values()),
            })

        print(f"\nk={k}: generated {n_generated} scenarios "
              f"({len(all_type_combos)} possible type-combinations, "
              f"{attempts} draws attempted)")

        if n_generated < SCENARIOS_PER_K:
            print(f"  WARNING: only {n_generated}/{SCENARIOS_PER_K} distinct scenarios "
                  f"reachable for k={k} given {len(available_types)} test-split types "
                  f"and up to 3 reps each.")

    # ----------------------------------------------------
    # Save
    # ----------------------------------------------------

    with open(OUTPUT_FILE, "w") as f:
        json.dump(all_scenarios, f, indent=2)

    pd.DataFrame(summary_rows).to_csv(OUTPUT_SUMMARY, index=False)

    print("\n")
    print("=" * 110)
    print("SUMMARY")
    print("=" * 110)
    print(f"Total scenarios: {len(all_scenarios)}")
    for k in K_VALUES:
        n = sum(1 for s in all_scenarios if s["k"] == k)
        print(f"  k={k}: {n} scenarios")

    print("\n")
    print("=" * 110)
    print("FILES SAVED")
    print("=" * 110)
    print(OUTPUT_FILE)
    print(OUTPUT_SUMMARY)

    print("\nGround-truth scenario synthesis complete.")


if __name__ == "__main__":
    main()
