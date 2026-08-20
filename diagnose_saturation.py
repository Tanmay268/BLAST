import pandas as pd
from pathlib import Path


# ======================================================
# BLAST — SATURATION DIAGNOSIS (Gate 1a)
# ======================================================
#
# context/07_NEXT_PHASE_PLAN.md, Step 1.
#
# The pilot showed incident 1 covering 9/9 business
# capabilities, so every later incident had zero marginal
# coverage. The plan's working hypothesis is that a single
# service, once flagged impaired, drags in most/all of the
# capability universe because attribution is service-level.
#
# This script does NOT assume which service plays that
# role. The plan text names frontendservice as the
# candidate amplifier, but all 6 pilot cases inject faults
# into checkoutservice, so the fault target itself is at
# least as plausible a culprit. We compute it from data.
#
# For each of the 6 pilot cases:
#   - which services are flagged impaired, with scores
#   - which capabilities each impaired service maps to
#   - the resulting union
#   - which impaired service(s) contribute each capability
#   - whether a single service accounts for most of the
#     union (the "dominant" service for that case)
#
# Then a cross-case verdict for Gate 1a.
# ======================================================

IMPAIRMENT_FILE = "impairment_detection_results.csv"
CAPABILITY_FILE = "business_capabilities.csv"

OUTPUT_CASE_DETAIL = "diagnose_saturation_case_detail.csv"
OUTPUT_SUMMARY = "diagnose_saturation_summary.csv"

# A single impaired service covering this fraction of a
# case's capability union counts as "dominant" for that case.
DOMINANCE_THRESHOLD = 0.7

# Gate 1a: this fraction of cases must show a dominant
# service for the amplifier hypothesis to be CONFIRMED.
CASE_FRACTION_THRESHOLD = 0.8


# ======================================================
# LOAD DATA
# ======================================================

print("=" * 100)
print("BLAST — SATURATION DIAGNOSIS (GATE 1a)")
print("=" * 100)

imp = pd.read_csv(IMPAIRMENT_FILE)
cap = pd.read_csv(CAPABILITY_FILE)

imp.columns = imp.columns.str.strip()
cap.columns = cap.columns.str.strip()

print(f"\nImpairment rows: {len(imp)}")
print(f"Capability mapping rows: {len(cap)}")

capability_universe = sorted(cap["business_capability"].unique())
universe_size = len(capability_universe)

print(f"\nCapability universe ({universe_size}): {capability_universe}")

# service -> set of capabilities it maps to
service_capabilities = (
    cap.groupby("service")["business_capability"]
    .apply(lambda s: set(s))
    .to_dict()
)


# ======================================================
# PER-CASE DIAGNOSIS
# ======================================================

case_detail_rows = []
summary_rows = []

cases = sorted(imp["case"].unique())

for case in cases:

    case_rows = imp[imp["case"] == case]
    fault_type = case_rows["fault_type"].iloc[0]
    faulty_service = (
        case_rows["faulty_service"].iloc[0]
        if "faulty_service" in case_rows.columns
        else None
    )

    impaired = (
        case_rows[case_rows["impaired"]]
        .sort_values("impairment_score", ascending=False)
    )

    print("\n")
    print("=" * 100)
    print(f"CASE: {case}  (fault_type={fault_type}, target={faulty_service})")
    print("=" * 100)

    if len(impaired) == 0:
        print("  No services flagged impaired.")
        summary_rows.append({
            "case": case,
            "fault_type": fault_type,
            "faulty_service": faulty_service,
            "n_impaired_services": 0,
            "union_size": 0,
            "saturation_fraction": 0.0,
            "dominant_service": None,
            "dominant_capabilities": 0,
            "dominance_fraction": 0.0,
            "is_dominated": False,
            "target_is_dominant": False,
        })
        continue

    print(f"\n  Impaired services ({len(impaired)}):")

    per_service_caps = {}

    for _, row in impaired.iterrows():
        service = row["service"]
        score = row["impairment_score"]
        caps = service_capabilities.get(service, set())
        per_service_caps[service] = caps

        print(f"    {service:<26} score={score:.3f}  -> {len(caps)} capabilities")
        for c in sorted(caps):
            print(f"        - {c}")

        for c in sorted(caps):
            case_detail_rows.append({
                "case": case,
                "fault_type": fault_type,
                "faulty_service": faulty_service,
                "impaired_service": service,
                "impairment_score": score,
                "business_capability": c,
            })

    union = set()
    for caps in per_service_caps.values():
        union |= caps

    print(f"\n  Union of capabilities across impaired services ({len(union)}/{universe_size}):")

    for c in sorted(union):
        contributors = sorted(
            s for s, caps in per_service_caps.items() if c in caps
        )
        print(f"    {c:<28} <- {', '.join(contributors)}")

    # Dominant service: the impaired service whose own
    # capability set is largest.
    dominant_service = max(per_service_caps, key=lambda s: len(per_service_caps[s]))
    dominant_caps = len(per_service_caps[dominant_service])
    dominance_fraction = (dominant_caps / len(union)) if union else 0.0
    is_dominated = dominance_fraction >= DOMINANCE_THRESHOLD
    target_is_dominant = (dominant_service == faulty_service)

    print(
        f"\n  Dominant service: {dominant_service} "
        f"({dominant_caps}/{len(union)} = {dominance_fraction:.1%} of the union)"
    )
    print(f"  Dominant service is the fault target: {target_is_dominant}")
    print(f"  Case classified as single-service-dominated: {is_dominated}")

    summary_rows.append({
        "case": case,
        "fault_type": fault_type,
        "faulty_service": faulty_service,
        "n_impaired_services": len(impaired),
        "union_size": len(union),
        "saturation_fraction": len(union) / universe_size,
        "dominant_service": dominant_service,
        "dominant_capabilities": dominant_caps,
        "dominance_fraction": dominance_fraction,
        "is_dominated": is_dominated,
        "target_is_dominant": target_is_dominant,
    })


case_detail = pd.DataFrame(case_detail_rows)
summary = pd.DataFrame(summary_rows)


# ======================================================
# CROSS-CASE VERDICT — GATE 1a
# ======================================================

print("\n")
print("=" * 100)
print("CROSS-CASE SUMMARY")
print("=" * 100)

print(
    summary.to_string(
        index=False,
        float_format=lambda x: f"{x:.3f}",
    )
)

n_cases = len(summary)
n_dominated = int(summary["is_dominated"].sum())
n_target_dominant = int(summary["target_is_dominant"].sum())
mean_saturation = summary["saturation_fraction"].mean()
mean_dominance = summary["dominance_fraction"].mean()
dominated_fraction = n_dominated / n_cases if n_cases else 0.0

dominant_service_counts = (
    summary["dominant_service"].value_counts().to_dict()
)

print("\n")
print("=" * 100)
print("GATE 1a — FRONTEND/SERVICE-AMPLIFIER HYPOTHESIS")
print("=" * 100)

print(f"\nCases evaluated: {n_cases}")
print(f"Cases where a single service covers >= {DOMINANCE_THRESHOLD:.0%} of the union: "
      f"{n_dominated}/{n_cases} ({dominated_fraction:.1%})")
print(f"Cases where the dominant service IS the fault-injection target: "
      f"{n_target_dominant}/{n_cases}")
print(f"Mean capability-union saturation (union_size / {universe_size}): {mean_saturation:.1%}")
print(f"Mean dominance fraction of the top service: {mean_dominance:.1%}")
print(f"Dominant-service frequency: {dominant_service_counts}")

if dominated_fraction >= CASE_FRACTION_THRESHOLD:

    verdict = "CONFIRMED"

    print(f"\nVERDICT: {verdict}")
    print(
        "\nA single impaired service accounts for most of each case's capability "
        "union in >= {:.0%} of cases.".format(CASE_FRACTION_THRESHOLD)
    )

    if n_target_dominant == n_dominated and n_dominated > 0:
        print(
            "\nThe dominant service is consistently the fault-injection target "
            "itself, not a downstream amplifier like frontendservice. This is "
            "still a service-level attribution bug: build_business_capabilities.py "
            "maps operations by the CALLER's serviceName, so every downstream RPC "
            "the fault target happens to issue (GetCart, PlaceOrder, Convert, "
            "Charge, ShipOrder, ...) is attributed to the target service itself, "
            "regardless of which callee actually served the capability."
        )

    print(
        "\nACTION: proceed to Step 2 — build_journey_impairment.py, rebuilding "
        "attribution at the operation/journey level so a capability is only "
        "attributed to the operation that actually realises it, not to whichever "
        "service happens to be the caller."
    )

else:

    verdict = "REFUTED"

    print(f"\nVERDICT: {verdict}")
    print(
        "\nNo single service dominates the union in most cases. Capability sets "
        "differ per impaired service but still union to near-total coverage. "
        "The likely cause is that the capability model is too coarse relative to "
        "the number of services (9 capabilities over 7 services is nearly 1:1)."
    )
    print(
        "\nACTION: do not proceed straight to attribution rework. Re-plan Step 2 "
        "around finer-grained / more numerous business capabilities before "
        "rebuilding the attribution mechanism."
    )

print(f"\nGate 1a result: {verdict}")


# ======================================================
# SAVE
# ======================================================

case_detail.to_csv(OUTPUT_CASE_DETAIL, index=False)
summary.to_csv(OUTPUT_SUMMARY, index=False)

print("\n")
print("=" * 100)
print("FILES SAVED")
print("=" * 100)

print(f"Case-level capability attribution: {OUTPUT_CASE_DETAIL}")
print(f"Cross-case summary: {OUTPUT_SUMMARY}")

print("\nSaturation diagnosis complete.")
