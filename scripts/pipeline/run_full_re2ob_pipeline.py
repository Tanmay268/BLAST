import sys
import time
import shutil
import traceback
from pathlib import Path

import pandas as pd
from huggingface_hub import snapshot_download

from blast_journey_lib import extract_journeys, summarize_case


# ======================================================
# BLAST — FULL RE2-OB BATCH PIPELINE
# ======================================================
#
# context/07_NEXT_PHASE_PLAN.md, Step 4 (task list #6-7).
#
# 90 cases = 5 target services x 6 fault types x 3
# repetitions (enumerated from the HuggingFace dataset
# listing, not assumed -- see the enumeration check run
# before this script was written).
#
# Per case: download traces.parquet + inject_time.txt only
# -> extract journeys -> summarize (same logic as the
# validated 6-case pilot, via blast_journey_lib.py) ->
# checkpoint the summary -> DELETE the raw trace file
# (ADR-004: raw traces deleted after distillation; disk is
# the binding constraint, not compute).
#
# Resumable: a case with an existing checkpoint is skipped.
# Re-running this script after an interruption picks up
# where it left off. Failures are logged to
# excluded_cases.csv and do not stop the run.
# ======================================================

REPO_ID = "phamquiluan/RCAEval"

TARGET_SERVICES = [
    "checkoutservice",
    "currencyservice",
    "emailservice",
    "productcatalogservice",
    "recommendationservice",
]

FAULT_TYPES = ["cpu", "delay", "disk", "loss", "mem", "socket"]

INSTANCES = [1, 2, 3]

BASE_DIR = Path("./data")
CHECKPOINT_DIR = Path("./results/data/journey_checkpoints")
SIGNATURE_CHECKPOINT_DIR = Path("./results/data/journey_signature_checkpoints")

EXCLUDED_CASES_FILE = "results/data/excluded_cases.csv"
FINAL_OUTPUT = "results/data/journey_impairment_full.csv"
FINAL_SIGNATURE_CATALOG = "results/data/journey_signature_catalog_full.csv"

CHECKPOINT_DIR.mkdir(exist_ok=True)
SIGNATURE_CHECKPOINT_DIR.mkdir(exist_ok=True)


def all_cases():
    cases = []
    for svc in TARGET_SERVICES:
        for fault in FAULT_TYPES:
            for inst in INSTANCES:
                cases.append((f"re2ob_{svc}_{fault}_{inst}", svc, fault))
    return cases


def process_case(case, svc, fault_type):

    case_dir = BASE_DIR / case

    # --------------------------------------------------
    # Download (traces.parquet + inject_time.txt only)
    # --------------------------------------------------

    snapshot_download(
        repo_id=REPO_ID,
        repo_type="dataset",
        allow_patterns=[f"{case}/traces.parquet", f"{case}/inject_time.txt"],
        local_dir=str(BASE_DIR),
    )

    if not (case_dir / "traces.parquet").exists():
        raise FileNotFoundError(f"traces.parquet missing after download for {case}")

    if not (case_dir / "inject_time.txt").exists():
        raise FileNotFoundError(f"inject_time.txt missing after download for {case}")

    # --------------------------------------------------
    # Extract + summarize
    # --------------------------------------------------

    journeys = extract_journeys(case, case_dir, faulty_service=svc, fault_type=fault_type)

    if len(journeys) == 0:
        raise ValueError(f"No journey traces extracted for {case}")

    summary = summarize_case(journeys)

    signature_summary = (
        journeys
        .assign(signature_str=journeys["signature"].apply(
            lambda s: "+".join(s) if s else "(empty)"
        ))
        .groupby(["journey_type_id", "journey_label", "signature_str"])
        .size()
        .reset_index(name="n_traces")
    )
    signature_summary.insert(0, "case", case)

    short_window = bool(journeys["short_window"].iloc[0])
    before_seconds = float(journeys["before_seconds_available"].iloc[0])
    after_seconds = float(journeys["after_seconds_available"].iloc[0])

    return summary, signature_summary, short_window, before_seconds, after_seconds


def cleanup_case_dir(case):
    case_dir = BASE_DIR / case
    if case_dir.exists():
        shutil.rmtree(case_dir, ignore_errors=True)


def main():

    print("=" * 110)
    print("BLAST — FULL RE2-OB BATCH PIPELINE")
    print("=" * 110)

    cases = all_cases()
    print(f"\nTotal cases to process: {len(cases)}")

    excluded_rows = []
    if Path(EXCLUDED_CASES_FILE).exists():
        excluded_rows = pd.read_csv(EXCLUDED_CASES_FILE).to_dict("records")
        print(f"Loaded {len(excluded_rows)} prior exclusion records")

    n_skipped = 0
    n_processed = 0
    n_failed = 0

    t_start = time.time()

    for i, (case, svc, fault_type) in enumerate(cases, start=1):

        checkpoint_file = CHECKPOINT_DIR / f"{case}.csv"

        if checkpoint_file.exists():
            n_skipped += 1
            continue

        print(f"\n[{i}/{len(cases)}] {case} (target={svc}, fault={fault_type})...", flush=True)

        try:
            summary, signature_summary, short_window, before_s, after_s = process_case(
                case, svc, fault_type
            )

            summary.to_csv(checkpoint_file, index=False)
            signature_summary.to_csv(
                SIGNATURE_CHECKPOINT_DIR / f"{case}.csv", index=False
            )

            # Clear any stale exclusion record from a previous failed
            # attempt at this case -- it succeeded now.
            excluded_rows = [r for r in excluded_rows if r["case"] != case]

            if short_window:
                excluded_rows.append({
                    "case": case,
                    "target_service": svc,
                    "fault_type": fault_type,
                    "reason": "short_window",
                    "detail": f"before={before_s:.1f}s after={after_s:.1f}s "
                              f"(min required {300}s each side)",
                    "hard_exclusion": False,
                })
                print(f"  WARNING: short window (before={before_s:.1f}s, after={after_s:.1f}s) "
                      f"-- kept, flagged insufficient_data in output")

            n_processed += 1
            n_impaired = int(summary["impaired"].sum())
            print(f"  OK -- {len(summary)} journey types, {n_impaired} impaired")

        except Exception as e:

            n_failed += 1
            print(f"  FAILED: {e}")
            traceback.print_exc(limit=2)

            excluded_rows.append({
                "case": case,
                "target_service": svc,
                "fault_type": fault_type,
                "reason": type(e).__name__,
                "detail": str(e)[:300],
                "hard_exclusion": True,
            })

        finally:
            cleanup_case_dir(case)

            excluded_df = pd.DataFrame(excluded_rows)
            if not excluded_df.empty:
                # A retried case may have failed before and succeeded/failed
                # again now -- keep only the most recent record per case.
                excluded_df = excluded_df.drop_duplicates(subset=["case"], keep="last")
            excluded_df.to_csv(EXCLUDED_CASES_FILE, index=False)

    elapsed = time.time() - t_start

    print("\n")
    print("=" * 110)
    print("BATCH RUN SUMMARY")
    print("=" * 110)
    print(f"Already checkpointed (skipped): {n_skipped}")
    print(f"Newly processed: {n_processed}")
    print(f"Failed: {n_failed}")
    print(f"Elapsed this run: {elapsed:.1f}s")

    # ----------------------------------------------------
    # Consolidate all checkpoints into final outputs
    # ----------------------------------------------------

    checkpoint_files = sorted(CHECKPOINT_DIR.glob("*.csv"))

    if not checkpoint_files:
        print("\nNo checkpoints found -- nothing to consolidate.")
        return

    all_summaries = pd.concat(
        [pd.read_csv(f) for f in checkpoint_files], ignore_index=True
    )
    all_summaries.to_csv(FINAL_OUTPUT, index=False)

    sig_files = sorted(SIGNATURE_CHECKPOINT_DIR.glob("*.csv"))
    if sig_files:
        all_signatures = pd.concat(
            [pd.read_csv(f) for f in sig_files], ignore_index=True
        )
        catalog = (
            all_signatures
            .groupby(["journey_type_id", "journey_label", "signature_str"])["n_traces"]
            .sum()
            .reset_index()
            .sort_values("n_traces", ascending=False)
        )
        catalog.to_csv(FINAL_SIGNATURE_CATALOG, index=False)

    print("\n")
    print("=" * 110)
    print("CONSOLIDATED OUTPUT")
    print("=" * 110)
    print(f"Total cases with checkpoints: {len(checkpoint_files)} / {len(cases)}")
    print(f"Total journey-type rows: {len(all_summaries)}")
    print(f"Saved: {FINAL_OUTPUT}")
    print(f"Saved: {FINAL_SIGNATURE_CATALOG}")
    print(f"Saved: {EXCLUDED_CASES_FILE} ({len(excluded_rows)} exclusion records)")

    remaining = len(cases) - len(checkpoint_files)
    if remaining > 0:
        print(f"\n{remaining} cases still unprocessed (hard failures). "
              f"Re-run this script to retry, or inspect {EXCLUDED_CASES_FILE}.")
    else:
        print("\nAll cases processed. Pipeline complete.")


if __name__ == "__main__":
    main()
