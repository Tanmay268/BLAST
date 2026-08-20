import pandas as pd
import numpy as np
import yaml
from pathlib import Path


# ======================================================
# BLAST — INCIDENT x CAPABILITY PROBABILITY / MAGNITUDE MODEL
# ======================================================
#
# context/07_NEXT_PHASE_PLAN.md Step 5a/5b groundwork.
#
# An "incident" for modelling purposes is a (service,
# fault_type) TYPE, not a single repetition -- the 3
# repetitions per RE2-OB (service, fault) combination are
# the unit of statistical support for estimating this
# type's own capability impact, not distinct incidents
# (ADR-012: never split reps of one type across train/test).
#
# Produces TWO artifacts from the same underlying data,
# kept deliberately separate per 07_NEXT_PHASE_PLAN.md §1.3:
#
# 1. incident_capability_probabilities.csv -- p(c|i), the
#    Beta(1,1)-smoothed probability that incident TYPE i's
#    repertoire impairs capability c, derived from the
#    BINARY impaired flag across reps. Feeds BLAST's own
#    probabilistic objective F(S) (Step 9). This is BLAST
#    grading its own homework's input -- fine for the model,
#    NOT fine as ground truth.
#
# 2. incident_capability_magnitude.csv -- continuous
#    measured_impairment_magnitude(c|i), MAX-aggregated
#    across reps and across journey types realising c.
#    Feeds ground truth GT_loss (Step 10), which per the
#    plan must be computed from MEASURED impairment and
#    NEVER from F(S).
#
# Scope note on train/test separation (see ADR-016): p(c|i)
# and magnitude(c|i) are estimated from a type's OWN
# repetitions -- direct measurement, not a model fit on
# other incident types and generalised to new ones. They
# are computed for every incident type regardless of split.
# The train/test split (config/splits/split_v1.yaml) matters
# for (a) B7's classifier, which DOES fit across incident
# types, and (b) restricting evaluation scenarios (Step 10)
# to TEST-split incidents so B7 is judged on genuinely
# held-out types.
# ======================================================

JOURNEY_FILE = "journey_impairment_full.csv"
OVERLAY_FILE = "business_overlay/online_boutique_v2.yaml"

OUTPUT_PROBABILITIES = "incident_capability_probabilities.csv"
OUTPUT_MAGNITUDES = "incident_capability_magnitude.csv"
OUTPUT_CASE_MAGNITUDES = "case_capability_magnitude.csv"

BETA_ALPHA = 1.0
BETA_BETA = 1.0


def load_overlay():
    with open(OVERLAY_FILE, "r") as f:
        overlay = yaml.safe_load(f)

    capability_ids = [c["id"] for c in overlay["capabilities"]]
    capability_display = {c["id"]: c["display"] for c in overlay["capabilities"]}
    capability_weight = {c["id"]: c["value_per_min"] for c in overlay["capabilities"]}

    operation_to_capabilities = {}
    for c in overlay["capabilities"]:
        for op in c["realised_by"]:
            operation_to_capabilities.setdefault(op, []).append(c["id"])

    return overlay, capability_ids, capability_display, capability_weight, operation_to_capabilities


def per_case_capability_coverage(journeys, operation_to_capabilities, capability_ids):
    """Returns two dicts keyed by case:
    - binary coverage: {capability_id: 0/1}
    - magnitude: {capability_id: max impairment_magnitude among
      impaired journeys realising it, else 0.0}
    """

    journeys = journeys.copy()
    journeys["signature"] = journeys["signature"].fillna("")

    binary_by_case = {}
    magnitude_by_case = {}

    for case, group in journeys.groupby("case"):

        covered = {c: 0 for c in capability_ids}
        magnitude = {c: 0.0 for c in capability_ids}

        impaired_journeys = group[group["impaired"]]

        for _, row in impaired_journeys.iterrows():
            ops = [o for o in row["signature"].split("+") if o]
            for op in ops:
                for cap_id in operation_to_capabilities.get(op, []):
                    covered[cap_id] = 1
                    magnitude[cap_id] = max(magnitude[cap_id], row["impairment_magnitude"])

        binary_by_case[case] = covered
        magnitude_by_case[case] = magnitude

    return binary_by_case, magnitude_by_case


def main():

    print("=" * 110)
    print("BLAST — INCIDENT x CAPABILITY PROBABILITY / MAGNITUDE MODEL")
    print("=" * 110)

    journeys = pd.read_csv(JOURNEY_FILE)
    overlay, capability_ids, capability_display, capability_weight, operation_to_capabilities = load_overlay()

    print(f"\nJourney impairment rows: {len(journeys)}")
    print(f"Cases: {journeys['case'].nunique()}")
    print(f"Capabilities: {len(capability_ids)}")

    binary_by_case, magnitude_by_case = per_case_capability_coverage(
        journeys, operation_to_capabilities, capability_ids
    )

    # ----------------------------------------------------
    # Map case -> (service, fault_type) TYPE
    # ----------------------------------------------------

    case_meta = (
        journeys[["case", "target_service", "fault_type"]]
        .drop_duplicates()
        .set_index("case")
    )

    type_of_case = {
        case: (row["target_service"], row["fault_type"])
        for case, row in case_meta.iterrows()
    }

    cases_by_type = {}
    for case, t in type_of_case.items():
        cases_by_type.setdefault(t, []).append(case)

    print(f"\nDistinct (service, fault_type) incident types: {len(cases_by_type)}")

    reps_per_type = {t: len(cs) for t, cs in cases_by_type.items()}
    under3 = {t: n for t, n in reps_per_type.items() if n != 3}
    if under3:
        print(f"\nNOTE: {len(under3)} incident types do not have exactly 3 usable "
              f"repetitions (likely due to excluded_cases.csv entries): {under3}")

    # ----------------------------------------------------
    # Aggregate per incident TYPE
    # ----------------------------------------------------

    prob_rows = []
    magnitude_rows = []

    for (service, fault_type), cases in sorted(cases_by_type.items()):

        n_reps = len(cases)

        for cap_id in capability_ids:

            n_impaired = sum(binary_by_case[c][cap_id] for c in cases)

            posterior_alpha = BETA_ALPHA + n_impaired
            posterior_beta = BETA_BETA + (n_reps - n_impaired)
            p_smoothed = posterior_alpha / (posterior_alpha + posterior_beta)

            max_magnitude = max(magnitude_by_case[c][cap_id] for c in cases)
            mean_magnitude = np.mean([magnitude_by_case[c][cap_id] for c in cases])

            prob_rows.append({
                "service": service,
                "fault_type": fault_type,
                "capability_id": cap_id,
                "capability": capability_display[cap_id],
                "n_reps": n_reps,
                "n_impaired_reps": n_impaired,
                "raw_probability": n_impaired / n_reps if n_reps > 0 else np.nan,
                "posterior_alpha": posterior_alpha,
                "posterior_beta": posterior_beta,
                "p_smoothed": p_smoothed,
            })

            magnitude_rows.append({
                "service": service,
                "fault_type": fault_type,
                "capability_id": cap_id,
                "capability": capability_display[cap_id],
                "n_reps": n_reps,
                "max_magnitude": max_magnitude,
                "mean_magnitude": mean_magnitude,
                "value_per_min": capability_weight[cap_id],
                "weighted_max_magnitude": max_magnitude * capability_weight[cap_id],
            })

    probabilities = pd.DataFrame(prob_rows)
    magnitudes = pd.DataFrame(magnitude_rows)

    # ----------------------------------------------------
    # Per-CASE (specific occurrence, not type-aggregated)
    # capability magnitude -- this is what scenario
    # synthesis (Step 10) uses as ground truth for a
    # specific instantiated incident, since GT must reflect
    # what actually happened in that occurrence, not the
    # type's average behaviour.
    # ----------------------------------------------------

    case_rows = []
    for case, mags in magnitude_by_case.items():
        service, fault_type = type_of_case[case]
        for cap_id, mag in mags.items():
            case_rows.append({
                "case": case,
                "service": service,
                "fault_type": fault_type,
                "capability_id": cap_id,
                "capability": capability_display[cap_id],
                "magnitude": mag,
                "value_per_min": capability_weight[cap_id],
                "weighted_magnitude": mag * capability_weight[cap_id],
            })

    case_magnitudes = pd.DataFrame(case_rows)

    # ----------------------------------------------------
    # Display
    # ----------------------------------------------------

    pd.set_option("display.max_columns", None)
    pd.set_option("display.width", 220)

    print("\n")
    print("=" * 110)
    print("INCIDENT-TYPE CAPABILITY IMPACT PROBABILITIES (p(c|i))")
    print("=" * 110)

    nonzero = probabilities[probabilities["n_impaired_reps"] > 0]
    print(f"\n{len(nonzero)} / {len(probabilities)} (incident type, capability) pairs "
          f"have at least one impaired repetition.")

    print(
        nonzero.sort_values(["service", "fault_type", "p_smoothed"], ascending=[True, True, False])
        .to_string(index=False, float_format=lambda x: f"{x:.4f}")
    )

    print("\n")
    print("=" * 110)
    print("CAPABILITY IMPACT MAGNITUDE (measured, for ground truth)")
    print("=" * 110)

    nonzero_mag = magnitudes[magnitudes["max_magnitude"] > 0]
    print(
        nonzero_mag.sort_values(["service", "fault_type", "weighted_max_magnitude"], ascending=[True, True, False])
        .to_string(index=False, float_format=lambda x: f"{x:.4f}")
    )

    # ----------------------------------------------------
    # Per-type footprint summary (differentiation check,
    # generalised Gate 2a across the full corpus)
    # ----------------------------------------------------

    footprint_rows = []
    for (service, fault_type), cases in sorted(cases_by_type.items()):
        covered = {c for c in capability_ids if any(binary_by_case[case][c] for case in cases)}
        footprint_rows.append({
            "service": service,
            "fault_type": fault_type,
            "capabilities_covered": len(covered),
            "capability_list": ";".join(sorted(capability_display[c] for c in covered)),
        })

    footprint = pd.DataFrame(footprint_rows)

    print("\n")
    print("=" * 110)
    print("PER-INCIDENT-TYPE CAPABILITY FOOTPRINT (FULL CORPUS)")
    print("=" * 110)
    print(footprint.to_string(index=False))

    n_saturated = int((footprint["capabilities_covered"] == len(capability_ids)).sum())
    print(f"\nIncident types covering all {len(capability_ids)}/{len(capability_ids)} capabilities: "
          f"{n_saturated}/{len(footprint)}")
    print(f"Mean capabilities covered: {footprint['capabilities_covered'].mean():.2f} / {len(capability_ids)}")

    # ----------------------------------------------------
    # Save
    # ----------------------------------------------------

    probabilities.to_csv(OUTPUT_PROBABILITIES, index=False)
    magnitudes.to_csv(OUTPUT_MAGNITUDES, index=False)
    case_magnitudes.to_csv(OUTPUT_CASE_MAGNITUDES, index=False)
    footprint.to_csv("incident_type_capability_footprint.csv", index=False)

    print("\n")
    print("=" * 110)
    print("FILES SAVED")
    print("=" * 110)
    print(OUTPUT_PROBABILITIES)
    print(OUTPUT_MAGNITUDES)
    print(OUTPUT_CASE_MAGNITUDES)
    print("incident_type_capability_footprint.csv")

    print("\nIncident capability model complete.")


if __name__ == "__main__":
    main()
