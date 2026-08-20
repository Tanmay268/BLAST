import pandas as pd

TRACE_FILE = r".\data\re2ob_checkoutservice_delay_1\traces.parquet"

df = pd.read_parquet(TRACE_FILE)

print("=" * 70)
print("BLAST — INVALID PARENT INVESTIGATION")
print("=" * 70)

# --------------------------------------------------
# Find invalid parents
# --------------------------------------------------

span_ids = set(df["spanID"])

has_parent = df["parentSpanID"].notna()

invalid = df[
    has_parent &
    ~df["parentSpanID"].isin(span_ids)
].copy()

print(f"\nInvalid parent references: {len(invalid)}")

# --------------------------------------------------
# Display them
# --------------------------------------------------

columns = [
    "traceID",
    "spanID",
    "parentSpanID",
    "serviceName",
    "methodName",
    "operationName",
    "startTimeMillis",
    "duration",
    "statusCode"
]

columns = [
    c for c in columns
    if c in df.columns
]

print("\n" + "=" * 70)
print("INVALID PARENT ROWS")
print("=" * 70)

print(
    invalid[columns]
    .to_string(index=False)
)

# --------------------------------------------------
# Trace-level summary
# --------------------------------------------------

print("\n" + "=" * 70)
print("AFFECTED TRACES")
print("=" * 70)

affected_traces = invalid["traceID"].unique()

print(
    f"Affected traces: {len(affected_traces)}"
)

for trace_id in affected_traces:

    trace = df[
        df["traceID"] == trace_id
    ]

    print("\n" + "-" * 70)
    print(f"TRACE: {trace_id}")
    print("-" * 70)

    print(
        trace[columns]
        .sort_values("startTimeMillis")
        .to_string(index=False)
    )

# --------------------------------------------------
# Parent IDs themselves
# --------------------------------------------------

print("\n" + "=" * 70)
print("INVALID PARENT IDs")
print("=" * 70)

print(
    invalid["parentSpanID"]
    .value_counts()
    .to_string()
)

# --------------------------------------------------
# Root count by trace
# --------------------------------------------------

print("\n" + "=" * 70)
print("TRACES WITH NO ROOT SPAN")
print("=" * 70)

root_counts = (
    df["parentSpanID"]
    .isna()
    .groupby(df["traceID"])
    .sum()
)

no_root = root_counts[
    root_counts == 0
]

print(
    f"Traces with zero root spans: {len(no_root)}"
)

print(no_root.to_string())

print("\nInvestigation complete.")