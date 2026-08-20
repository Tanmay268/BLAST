import random
from pathlib import Path

import yaml


# ======================================================
# BLAST — TRAIN TICKET TRAIN/TEST SPLIT
# ======================================================
# Same stratification rule as build_train_test_split.py
# (ADR-012): split at the (service, fault) combination
# level, every service and fault type represented in both.
# ======================================================

SEED = 20260820

TARGET_SERVICES = [
    "ts-auth-service", "ts-order-service", "ts-route-service",
    "ts-train-service", "ts-travel-service",
]
FAULT_TYPES = ["cpu", "delay", "disk", "loss", "mem", "socket"]
TEST_FAULTS_PER_SERVICE = 2

OUTPUT_FILE = Path("config/splits/split_re2tt_v1.yaml")


def build_split():
    rng = random.Random(SEED)
    train_combos, test_combos = [], []

    for svc in TARGET_SERVICES:
        faults = list(FAULT_TYPES)
        rng.shuffle(faults)
        test_faults = sorted(faults[:TEST_FAULTS_PER_SERVICE])
        train_faults = sorted(faults[TEST_FAULTS_PER_SERVICE:])
        test_combos += [(svc, f) for f in test_faults]
        train_combos += [(svc, f) for f in train_faults]

    return sorted(train_combos), sorted(test_combos)


def main():

    print("=" * 100)
    print("BLAST — TRAIN TICKET TRAIN/TEST SPLIT")
    print("=" * 100)

    train_combos, test_combos = build_split()

    print(f"\nTrain: {len(train_combos)} combos, Test: {len(test_combos)} combos")

    train_services = {s for s, _ in train_combos}
    test_services = {s for s, _ in test_combos}
    train_faults = {f for _, f in train_combos}
    test_faults = {f for _, f in test_combos}

    ok = (
        set(TARGET_SERVICES) <= train_services and set(TARGET_SERVICES) <= test_services
        and set(FAULT_TYPES) <= train_faults and set(FAULT_TYPES) <= test_faults
    )
    print(f"Coverage check (every service/fault in both splits): {'PASS' if ok else 'FAIL'}")
    if not ok:
        raise RuntimeError("Split coverage check failed.")

    manifest = {
        "version": 1, "system": "train-ticket", "seed": SEED,
        "split_unit": "(service, fault_type)",
        "train": [{"service": s, "fault_type": f} for s, f in train_combos],
        "test": [{"service": s, "fault_type": f} for s, f in test_combos],
    }

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w") as f:
        yaml.safe_dump(manifest, f, sort_keys=False)

    print(f"\nSaved: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
