import pandas as pd
import numpy as np
import yaml


# ======================================================
# BLAST — TRAIN TICKET INCIDENT x CAPABILITY MODEL
# ======================================================
# Same logic as build_incident_capability_model.py --
# see that file's docstring for the full rationale on why
# p(c|i) and magnitude(c|i) are computed per incident TYPE
# from its own repetitions (ADR-016), and kept separate.
# ======================================================

JOURNEY_FILE = "results/data/re2tt_journey_impairment_full.csv"
OVERLAY_FILE = "business_overlay/train_ticket_v1.yaml"

OUTPUT_PROBABILITIES = "results/data/re2tt_incident_capability_probabilities.csv"
OUTPUT_MAGNITUDES = "results/data/re2tt_incident_capability_magnitude.csv"
OUTPUT_CASE_MAGNITUDES = "results/data/re2tt_case_capability_magnitude.csv"
OUTPUT_FOOTPRINT = "results/data/re2tt_incident_type_capability_footprint.csv"

BETA_ALPHA = 1.0
BETA_BETA = 1.0


def load_overlay():
    with open(OVERLAY_FILE) as f:
        overlay = yaml.safe_load(f)
    capability_ids = [c["id"] for c in overlay["capabilities"]]
    display = {c["id"]: c["display"] for c in overlay["capabilities"]}
    weight = {c["id"]: c["value_per_min"] for c in overlay["capabilities"]}
    op_to_caps = {}
    for c in overlay["capabilities"]:
        for op in c["realised_by"]:
            op_to_caps.setdefault(op, []).append(c["id"])
    return capability_ids, display, weight, op_to_caps


def per_case_capability_coverage(journeys, op_to_caps, capability_ids):

    journeys = journeys.copy()
    journeys["signature"] = journeys["signature"].fillna("")

    binary_by_case, magnitude_by_case = {}, {}

    for case, group in journeys.groupby("case"):

        covered = {c: 0 for c in capability_ids}
        magnitude = {c: 0.0 for c in capability_ids}

        for _, row in group[group["impaired"]].iterrows():
            ops = [o for o in row["signature"].split("+") if o]
            for op in ops:
                for cap_id in op_to_caps.get(op, []):
                    covered[cap_id] = 1
                    magnitude[cap_id] = max(magnitude[cap_id], row["impairment_magnitude"])

        binary_by_case[case] = covered
        magnitude_by_case[case] = magnitude

    return binary_by_case, magnitude_by_case


def main():

    print("=" * 110)
    print("BLAST — TRAIN TICKET INCIDENT x CAPABILITY MODEL")
    print("=" * 110)

    journeys = pd.read_csv(JOURNEY_FILE)
    capability_ids, display, weight, op_to_caps = load_overlay()

    print(f"\nJourney rows: {len(journeys)}, cases: {journeys['case'].nunique()}, "
          f"capabilities: {len(capability_ids)}")

    binary_by_case, magnitude_by_case = per_case_capability_coverage(journeys, op_to_caps, capability_ids)

    case_meta = journeys[["case", "target_service", "fault_type"]].drop_duplicates().set_index("case")
    type_of_case = {c: (r["target_service"], r["fault_type"]) for c, r in case_meta.iterrows()}

    cases_by_type = {}
    for case, t in type_of_case.items():
        cases_by_type.setdefault(t, []).append(case)

    print(f"Distinct incident types: {len(cases_by_type)}")

    # Sanity: any journey type with NO operation mapped to a capability
    # at all? Flags overlay coverage gaps rather than silently ranking
    # incidents as "impaired nothing".
    all_ops_seen = set()
    for sig in journeys["signature"].fillna(""):
        all_ops_seen.update(o for o in sig.split("+") if o)
    unmapped_ops = sorted(all_ops_seen - set(op_to_caps.keys()))
    if unmapped_ops:
        print(f"\nWARNING: {len(unmapped_ops)} observed operation(s) have NO capability "
              f"mapping in {OVERLAY_FILE} -- any journey touching only these contributes "
              f"nothing to capability attribution:")
        for op in unmapped_ops[:20]:
            print(f"  {op}")

    prob_rows, magnitude_rows = [], []

    for (service, fault_type), cases in sorted(cases_by_type.items()):
        n_reps = len(cases)
        for cap_id in capability_ids:
            n_impaired = sum(binary_by_case[c][cap_id] for c in cases)
            a = BETA_ALPHA + n_impaired
            b = BETA_BETA + (n_reps - n_impaired)
            p_smoothed = a / (a + b)
            max_mag = max(magnitude_by_case[c][cap_id] for c in cases)
            prob_rows.append({
                "service": service, "fault_type": fault_type, "capability_id": cap_id,
                "capability": display[cap_id], "n_reps": n_reps, "n_impaired_reps": n_impaired,
                "raw_probability": n_impaired / n_reps if n_reps else np.nan,
                "posterior_alpha": a, "posterior_beta": b, "p_smoothed": p_smoothed,
            })
            magnitude_rows.append({
                "service": service, "fault_type": fault_type, "capability_id": cap_id,
                "capability": display[cap_id], "n_reps": n_reps, "max_magnitude": max_mag,
                "value_per_min": weight[cap_id], "weighted_max_magnitude": max_mag * weight[cap_id],
            })

    probabilities = pd.DataFrame(prob_rows)
    magnitudes = pd.DataFrame(magnitude_rows)

    case_rows = []
    for case, mags in magnitude_by_case.items():
        service, fault_type = type_of_case[case]
        for cap_id, mag in mags.items():
            case_rows.append({
                "case": case, "service": service, "fault_type": fault_type,
                "capability_id": cap_id, "capability": display[cap_id], "magnitude": mag,
                "value_per_min": weight[cap_id], "weighted_magnitude": mag * weight[cap_id],
            })
    case_magnitudes = pd.DataFrame(case_rows)

    footprint_rows = []
    for (service, fault_type), cases in sorted(cases_by_type.items()):
        covered = {c for c in capability_ids if any(binary_by_case[case][c] for case in cases)}
        footprint_rows.append({
            "service": service, "fault_type": fault_type,
            "capabilities_covered": len(covered),
            "capability_list": ";".join(sorted(display[c] for c in covered)),
        })
    footprint = pd.DataFrame(footprint_rows)

    pd.set_option("display.max_columns", None)
    pd.set_option("display.width", 220)

    print("\n")
    print("=" * 110)
    print("PER-INCIDENT-TYPE CAPABILITY FOOTPRINT")
    print("=" * 110)
    print(footprint.to_string(index=False))

    n_saturated = int((footprint["capabilities_covered"] == len(capability_ids)).sum())
    print(f"\nIncident types covering all {len(capability_ids)}/{len(capability_ids)} capabilities: "
          f"{n_saturated}/{len(footprint)}")
    print(f"Mean capabilities covered: {footprint['capabilities_covered'].mean():.2f} / {len(capability_ids)}")

    probabilities.to_csv(OUTPUT_PROBABILITIES, index=False)
    magnitudes.to_csv(OUTPUT_MAGNITUDES, index=False)
    case_magnitudes.to_csv(OUTPUT_CASE_MAGNITUDES, index=False)
    footprint.to_csv(OUTPUT_FOOTPRINT, index=False)

    print("\n")
    print("=" * 110)
    print("FILES SAVED")
    print("=" * 110)
    for f in [OUTPUT_PROBABILITIES, OUTPUT_MAGNITUDES, OUTPUT_CASE_MAGNITUDES, OUTPUT_FOOTPRINT]:
        print(f)

    print("\nTrain Ticket incident capability model complete.")


if __name__ == "__main__":
    main()
