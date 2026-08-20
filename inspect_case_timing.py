import pandas as pd
from pathlib import Path

CASES = [
    "re2ob_checkoutservice_delay_1",
    "re2ob_checkoutservice_delay_2",
    "re2ob_checkoutservice_delay_3",
    "re2ob_checkoutservice_cpu_1",
    "re2ob_checkoutservice_cpu_2",
    "re2ob_checkoutservice_cpu_3",
]

BASE_DIR = Path("./data")


for case in CASES:

    print("\n" + "=" * 90)
    print(f"CASE: {case}")
    print("=" * 90)

    case_dir = BASE_DIR / case

    df = pd.read_parquet(
        case_dir / "traces.parquet"
    )

    with open(case_dir / "inject_time.txt") as f:
        inject_time = int(f.read().strip())

    inject_ms = inject_time * 1000

    min_time = df["startTimeMillis"].min()
    max_time = df["startTimeMillis"].max()

    print(f"Injection timestamp : {inject_time}")
    print(f"Minimum trace time  : {min_time}")
    print(f"Maximum trace time  : {max_time}")

    print(
        f"Time before injection: "
        f"{(inject_ms - min_time) / 1000:.2f} seconds"
    )

    print(
        f"Time after injection: "
        f"{(max_time - inject_ms) / 1000:.2f} seconds"
    )

    print(
        f"Total trace duration: "
        f"{(max_time - min_time) / 1000:.2f} seconds"
    )