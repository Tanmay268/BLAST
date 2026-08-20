import json
import random
from itertools import combinations

import pandas as pd
import yaml

from blast_eval_lib import oracle_order, gt_loss_per_incident


# ======================================================
# BLAST — TRAIN TICKET GROUND-TRUTH SCENARIOS
# ======================================================
# Same design as build_ground_truth_scenarios.py: TEST-split
# only, oracle order from MEASURED magnitude (never F(S)).
# ======================================================

CASE_MAGNITUDE_FILE = "results/data/re2tt_case_capability_magnitude.csv"
SPLIT_FILE = "config/splits/split_re2tt_v1.yaml"
OVERLAY_FILE = "business_overlay/train_ticket_v1.yaml"

OUTPUT_FILE = "results/data/re2tt_ground_truth_scenarios.json"
OUTPUT_SUMMARY = "results/data/re2tt_ground_truth_scenarios_summary.csv"

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
    print("BLAST — TRAIN TICKET GROUND-TRUTH SCENARIO SYNTHESIS")
    print("=" * 110)

    case_mag = pd.read_csv(CASE_MAGNITUDE_FILE)
    weights = load_weights()
    test_types = load_test_types()

    print(f"\nTest-split incident types: {len(test_types)}")

    test_type_set = set(test_types)
    case_mag = case_mag[
        case_mag.apply(lambda r: (r["service"], r["fault_type"]) in test_type_set, axis=1)
    ]

    cases_by_type, incident_capabilities, type_of_case = {}, {}, {}

    for case, group in case_mag.groupby("case"):
        service = group["service"].iloc[0]
        fault_type = group["fault_type"].iloc[0]
        cases_by_type.setdefault((service, fault_type), []).append(case)
        type_of_case[case] = (service, fault_type)
        incident_capabilities[case] = {
            row["capability_id"]: row["magnitude"]
            for _, row in group.iterrows() if row["magnitude"] > 0
        }

    print(f"Test-split cases with capability data: {len(incident_capabilities)}")
    for t, cases in sorted(cases_by_type.items()):
        print(f"  {t}: {len(cases)} reps")

    available_types = list(cases_by_type.keys())
    if len(available_types) < 3:
        raise RuntimeError(f"Only {len(available_types)} test-split types with data.")

    rng = random.Random(SEED)
    all_scenarios, summary_rows = [], []

    for k in K_VALUES:

        k_eff = min(k, len(available_types))
        all_type_combos = list(combinations(available_types, k_eff))

        n_generated = 0
        seen = set()
        attempts, max_attempts = 0, SCENARIOS_PER_K * 50

        while n_generated < SCENARIOS_PER_K and attempts < max_attempts:
            attempts += 1
            type_combo = rng.choice(all_type_combos)
            incident_ids = tuple(sorted(rng.choice(cases_by_type[t]) for t in type_combo))
            if len(set(incident_ids)) != k_eff or incident_ids in seen:
                continue
            seen.add(incident_ids)
            n_generated += 1

            incident_ids_list = list(incident_ids)
            scenario_id = f"re2tt_scenario_k{k}_{n_generated:03d}"

            gt_loss = gt_loss_per_incident(
                incident_ids_list, {i: incident_capabilities[i] for i in incident_ids_list}, weights,
            )
            oracle = oracle_order(
                incident_ids_list, {i: incident_capabilities[i] for i in incident_ids_list}, weights,
            )

            all_scenarios.append({
                "scenario_id": scenario_id, "k": k, "incident_ids": incident_ids_list,
                "incident_types": [f"{type_of_case[i][0]}::{type_of_case[i][1]}" for i in incident_ids_list],
                "gt_loss": gt_loss, "oracle_order": oracle,
            })
            summary_rows.append({
                "scenario_id": scenario_id, "k": k, "incident_ids": ";".join(incident_ids_list),
                "total_gt_loss": sum(gt_loss.values()),
            })

        print(f"\nk={k}: generated {n_generated} scenarios ({len(all_type_combos)} possible combos)")
        if n_generated < SCENARIOS_PER_K:
            print(f"  WARNING: only {n_generated}/{SCENARIOS_PER_K} reachable.")

    with open(OUTPUT_FILE, "w") as f:
        json.dump(all_scenarios, f, indent=2)
    pd.DataFrame(summary_rows).to_csv(OUTPUT_SUMMARY, index=False)

    print(f"\nTotal scenarios: {len(all_scenarios)}")
    print(f"Saved: {OUTPUT_FILE}")
    print(f"Saved: {OUTPUT_SUMMARY}")
    print("\nGround-truth scenario synthesis complete.")


if __name__ == "__main__":
    main()
