import pandas as pd
from pathlib import Path

CASES = [
    "re2ob_checkoutservice_delay_1",
    "re2ob_checkoutservice_cpu_1",
]

BASE_DIR = Path("./data")


for case in CASES:

    print("\n" + "=" * 80)
    print(f"CASE: {case}")
    print("=" * 80)

    case_dir = BASE_DIR / case

    df = pd.read_parquet(
        case_dir / "traces.parquet"
    )

    print("\nTotal spans:", len(df))

    print("\nUnique traces:", df["traceID"].nunique())

    print("\nSpans per trace:")

    trace_counts = df.groupby("traceID").size()

    print(trace_counts.describe())

    print("\nOperation distribution:")

    print(
        df["operationName"]
        .value_counts()
        .head(20)
    )

    print("\nService + operation distribution:")

    print(
        df.groupby(
            ["serviceName", "operationName"]
        )
        .size()
        .sort_values(ascending=False)
        .head(30)
    )

    print("\nRoot service distribution:")

    roots = df[
        df["parentSpanID"].isna()
    ]

    print(
        roots["serviceName"]
        .value_counts()
    )