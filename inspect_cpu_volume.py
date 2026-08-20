import pandas as pd
import numpy as np
from pathlib import Path

CASES = [
    "re2ob_checkoutservice_cpu_1",
    "re2ob_checkoutservice_cpu_2",
    "re2ob_checkoutservice_cpu_3",
]

BASE_DIR = Path("./data")


for case in CASES:

    print("\n" + "=" * 90)
    print(f"CPU CASE: {case}")
    print("=" * 90)

    case_dir = BASE_DIR / case

    df = pd.read_parquet(
        case_dir / "traces.parquet"
    )

    with open(case_dir / "inject_time.txt") as f:
        inject_time = int(f.read().strip())

    inject_ms = inject_time * 1000

    # --------------------------------------------------
    # Relative time
    # --------------------------------------------------

    df["relative_seconds"] = (
        df["startTimeMillis"] - inject_ms
    ) / 1000

    # --------------------------------------------------
    # 10-second windows
    # --------------------------------------------------

    df["window"] = (
        df["relative_seconds"] // 10
    ) * 10

    # --------------------------------------------------
    # Span volume by window
    # --------------------------------------------------

    volume = (
        df
        .groupby(
            ["window", "serviceName"]
        )
        .size()
        .reset_index(
            name="spans"
        )
    )

    print("\n--- Overall volume ---")

    print(
        df.groupby(
            df["relative_seconds"] < 0
        ).size()
    )

    # --------------------------------------------------
    # Per-service normal/faulty counts
    # --------------------------------------------------

    df["period"] = np.where(
        df["startTimeMillis"] < inject_ms,
        "normal",
        "faulty"
    )

    summary = (
        df
        .groupby(
            ["serviceName", "period"]
        )
        .size()
        .unstack(
            fill_value=0
        )
    )

    summary["faulty_to_normal_ratio"] = (
        summary.get("faulty", 0) /
        summary.get("normal", 1)
    )

    print("\n--- Service span volume ---")

    print(
        summary.sort_values(
            "faulty_to_normal_ratio"
        ).to_string()
    )

    # --------------------------------------------------
    # Save
    # --------------------------------------------------

    output = (
        f"{case}_volume.csv"
    )

    volume.to_csv(
        output,
        index=False
    )

    print(
        f"\nSaved: {output}"
    )