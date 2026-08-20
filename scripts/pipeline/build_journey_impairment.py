import pandas as pd
import numpy as np
from pathlib import Path

from blast_journey_lib import extract_journeys, summarize_case


# ======================================================
# BLAST — JOURNEY-LEVEL IMPAIRMENT ATTRIBUTION (6-CASE PILOT)
# ======================================================
#
# context/07_NEXT_PHASE_PLAN.md, Step 2. Fixes the
# saturation bug confirmed by diagnose_saturation.py
# (Gate 1a). See JOURNEY_TYPING_RULE.md and ADR-014/015
# in context/01_DECISION_LOG.md for the full rationale.
#
# Gate 2a PASSED against this pilot's output -- see
# rerun_pilot_journey_level.py.
#
# The extraction/significance-testing logic lives in
# blast_journey_lib.py, shared with
# run_full_re2ob_pipeline.py (the 90-case corpus run) so
# the two never drift apart.
# ======================================================


CASES = [
    "re2ob_checkoutservice_delay_1",
    "re2ob_checkoutservice_delay_2",
    "re2ob_checkoutservice_delay_3",
    "re2ob_checkoutservice_cpu_1",
    "re2ob_checkoutservice_cpu_2",
    "re2ob_checkoutservice_cpu_3",
]

BASE_DIR = Path("./data")

OUTPUT_FILE = "results/data/journey_impairment.csv"
OUTPUT_SIGNATURE_CATALOG = "results/data/journey_signature_catalog.csv"


# ======================================================
# RUN ALL CASES
# ======================================================

print("=" * 110)
print("BLAST — JOURNEY-LEVEL IMPAIRMENT ATTRIBUTION (6-CASE PILOT)")
print("=" * 110)

all_journeys = []
all_summaries = []

for case in CASES:

    print(f"\nProcessing {case}...")

    fault_type = "delay" if "_delay_" in case else "cpu"

    journeys = extract_journeys(
        case, BASE_DIR / case,
        faulty_service="checkoutservice",
        fault_type=fault_type,
    )
    all_journeys.append(journeys)

    print(
        f"  {len(journeys)} journey traces "
        f"({journeys['journey_type_id'].nunique()} distinct types)"
    )

    if journeys["short_window"].iloc[0]:
        print(
            f"  WARNING: short window "
            f"(before={journeys['before_seconds_available'].iloc[0]:.1f}s, "
            f"after={journeys['after_seconds_available'].iloc[0]:.1f}s) "
            f"-- significance tests suppressed for this case"
        )

    summary = summarize_case(journeys)
    all_summaries.append(summary)

all_journeys = pd.concat(all_journeys, ignore_index=True)
journey_impairment = pd.concat(all_summaries, ignore_index=True)


# ======================================================
# SIGNATURE CATALOG (methodological transparency)
# ======================================================

catalog = (
    all_journeys
    .assign(signature_str=all_journeys["signature"].apply(
        lambda s: "+".join(s) if s else "(empty)"
    ))
    .groupby(["journey_type_id", "journey_label", "signature_str"])
    .size()
    .reset_index(name="n_traces")
    .sort_values("n_traces", ascending=False)
)


# ======================================================
# DISPLAY
# ======================================================

pd.set_option("display.max_columns", None)
pd.set_option("display.width", 260)

print("\n")
print("=" * 110)
print("JOURNEY SIGNATURE CATALOG")
print("=" * 110)

print(catalog.to_string(index=False))

print("\n")
print("=" * 110)
print("JOURNEY IMPAIRMENT SUMMARY")
print("=" * 110)

display_cols = [
    "case", "fault_type", "journey_type", "journey_label",
    "n_baseline", "n_fault", "p95_ratio",
    "fail_rate_delta", "degraded_rate_delta",
    "p_value", "effect_size", "impairment_magnitude",
    "impaired", "insufficient_data",
]

print(
    journey_impairment[display_cols].to_string(
        index=False,
        float_format=lambda x: f"{x:.4f}",
    )
)

print("\n")
print("=" * 110)
print("IMPAIRED JOURNEY TYPES BY CASE")
print("=" * 110)

for case, group in journey_impairment.groupby("case"):

    impaired = group[group["impaired"]].sort_values(
        "impairment_magnitude", ascending=False
    )

    print(f"\n{case}")

    if len(impaired) == 0:
        print("  No journey types detected as impaired.")
        continue

    for _, row in impaired.iterrows():
        print(
            f"  {row['journey_label']:<24} "
            f"p95_ratio={row['p95_ratio']:.2f} "
            f"p_value={row['p_value']:.4g} "
            f"effect={row['effect_size']:.3f} "
            f"magnitude={row['impairment_magnitude']:.3f}"
        )


# ======================================================
# SAVE
# ======================================================

journey_impairment.to_csv(OUTPUT_FILE, index=False)
catalog.to_csv(OUTPUT_SIGNATURE_CATALOG, index=False)

print("\n")
print("=" * 110)
print("FILES SAVED")
print("=" * 110)

print(f"Journey impairment: {OUTPUT_FILE}")
print(f"Signature catalog: {OUTPUT_SIGNATURE_CATALOG}")

print("\nJourney impairment attribution complete.")
