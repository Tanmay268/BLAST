import yaml
from pathlib import Path
import random


# ======================================================
# BLAST — FROZEN TRAIN/TEST SPLIT
# ======================================================
#
# ADR-012: strict split by fault case, stratified by
# service AND fault type, created and frozen BEFORE any
# modelling (before edge-probability fitting, Step 9).
#
# Split at the (service, fault) level, not the case level
# -- the 3 repetitions of a given (service, fault) combo
# are the SAME incident type observed 3 times. Splitting
# reps across train/test would leak: a repetition's
# measured behaviour would inform the very edge
# probabilities used to score its held-out twin.
#
# context/07_NEXT_PHASE_PLAN.md task list #8.
# ======================================================

SEED = 20260820  # fixed and logged, per hard rule #5 (determinism)

TARGET_SERVICES = [
    "checkoutservice",
    "currencyservice",
    "emailservice",
    "productcatalogservice",
    "recommendationservice",
]

FAULT_TYPES = ["cpu", "delay", "disk", "loss", "mem", "socket"]

TEST_FAULTS_PER_SERVICE = 2  # of 6 -> 1/3 test, 2/3 train, by combo

OUTPUT_DIR = Path("config/splits")
OUTPUT_FILE = OUTPUT_DIR / "split_v1.yaml"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def build_split():

    rng = random.Random(SEED)

    train_combos = []
    test_combos = []

    for svc in TARGET_SERVICES:

        faults = list(FAULT_TYPES)
        rng.shuffle(faults)

        test_faults = sorted(faults[:TEST_FAULTS_PER_SERVICE])
        train_faults = sorted(faults[TEST_FAULTS_PER_SERVICE:])

        for f in test_faults:
            test_combos.append((svc, f))

        for f in train_faults:
            train_combos.append((svc, f))

    return sorted(train_combos), sorted(test_combos)


def main():

    print("=" * 100)
    print("BLAST — TRAIN/TEST SPLIT (frozen before modelling, ADR-012)")
    print("=" * 100)

    train_combos, test_combos = build_split()

    print(f"\nSeed: {SEED}")
    print(f"Total (service, fault) combinations: {len(TARGET_SERVICES) * len(FAULT_TYPES)}")
    print(f"Train combinations: {len(train_combos)}")
    print(f"Test combinations: {len(test_combos)}")

    print("\nTrain (service, fault):")
    for svc, f in train_combos:
        print(f"  {svc:<24} {f}")

    print("\nTest (service, fault):")
    for svc, f in test_combos:
        print(f"  {svc:<24} {f}")

    # ----------------------------------------------------
    # Sanity: every service and every fault type must
    # appear in BOTH splits, or edge-probability estimation
    # / evaluation coverage silently degenerates for that
    # dimension.
    # ----------------------------------------------------

    train_services = {s for s, _ in train_combos}
    test_services = {s for s, _ in test_combos}
    train_faults = {f for _, f in train_combos}
    test_faults = {f for _, f in test_combos}

    print("\n")
    print("=" * 100)
    print("COVERAGE CHECK")
    print("=" * 100)

    ok = True

    missing_train_services = set(TARGET_SERVICES) - train_services
    missing_test_services = set(TARGET_SERVICES) - test_services
    missing_train_faults = set(FAULT_TYPES) - train_faults
    missing_test_faults = set(FAULT_TYPES) - test_faults

    if missing_train_services:
        print(f"FAIL: services missing from train: {missing_train_services}")
        ok = False
    if missing_test_services:
        print(f"FAIL: services missing from test: {missing_test_services}")
        ok = False
    if missing_train_faults:
        print(f"FAIL: fault types missing from train: {missing_train_faults}")
        ok = False
    if missing_test_faults:
        print(f"FAIL: fault types missing from test: {missing_test_faults}")
        ok = False

    if ok:
        print("PASS: every service and every fault type appears in both train and test.")
    else:
        raise RuntimeError("Split coverage check failed -- adjust seed or stratification.")

    # ----------------------------------------------------
    # Expand to case-level manifest (informational --
    # exclusions from run_full_re2ob_pipeline.py are
    # resolved at load time, NOT baked into this frozen
    # manifest, so the type-level assignment never changes
    # after the fact).
    # ----------------------------------------------------

    manifest = {
        "version": 1,
        "seed": SEED,
        "split_unit": "(service, fault_type)",
        "rationale": (
            "Stratified by service and fault type, at the (service, fault) "
            "combination level, not the case level -- repetitions of the same "
            "combination stay together to prevent leakage (ADR-012)."
        ),
        "train": [{"service": s, "fault_type": f} for s, f in train_combos],
        "test": [{"service": s, "fault_type": f} for s, f in test_combos],
    }

    with open(OUTPUT_FILE, "w") as fh:
        yaml.safe_dump(manifest, fh, sort_keys=False)

    print("\n")
    print("=" * 100)
    print("FILE SAVED")
    print("=" * 100)
    print(str(OUTPUT_FILE))

    print("\nTrain/test split frozen.")


if __name__ == "__main__":
    main()
