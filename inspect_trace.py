import pandas as pd

TRACE_FILE = r".\data\re2ob_checkoutservice_delay_1\traces.parquet"

print("=" * 70)
print("BLAST GATE 0 — TRACE INSPECTION")
print("=" * 70)

print("\nLoading trace data...")

df = pd.read_parquet(TRACE_FILE)

print(f"Rows: {len(df):,}")
print(f"Columns: {len(df.columns)}")

# --------------------------------------------------
# 1. COLUMN NAMES
# --------------------------------------------------

print("\n" + "=" * 70)
print("1. COLUMNS")
print("=" * 70)

for i, col in enumerate(df.columns, 1):
    print(f"{i:2}. {col}")

# --------------------------------------------------
# 2. DATA TYPES
# --------------------------------------------------

print("\n" + "=" * 70)
print("2. DATA TYPES")
print("=" * 70)

print(df.dtypes.to_string())

# --------------------------------------------------
# 3. FIRST 10 ROWS
# --------------------------------------------------

print("\n" + "=" * 70)
print("3. FIRST 10 ROWS")
print("=" * 70)

print(df.head(10).to_string())

# --------------------------------------------------
# 4. TRACE / SPAN / PARENT COLUMNS
# --------------------------------------------------

print("\n" + "=" * 70)
print("4. TRACE RELATIONSHIP COLUMNS")
print("=" * 70)

keywords = [
    "trace",
    "span",
    "parent",
    "root"
]

relationship_columns = [
    col for col in df.columns
    if any(keyword in col.lower() for keyword in keywords)
]

for col in relationship_columns:
    print(col)

# --------------------------------------------------
# 5. SERVICE / OPERATION COLUMNS
# --------------------------------------------------

print("\n" + "=" * 70)
print("5. SERVICE / OPERATION COLUMNS")
print("=" * 70)

service_operation_columns = [
    col for col in df.columns
    if any(
        keyword in col.lower()
        for keyword in [
            "service",
            "operation",
            "method"
        ]
    )
]

for col in service_operation_columns:
    print(col)

# --------------------------------------------------
# 6. TIME / DURATION COLUMNS
# --------------------------------------------------

print("\n" + "=" * 70)
print("6. TIME / DURATION COLUMNS")
print("=" * 70)

time_columns = [
    col for col in df.columns
    if any(
        keyword in col.lower()
        for keyword in [
            "time",
            "duration",
            "latency",
            "timestamp"
        ]
    )
]

for col in time_columns:
    print(col)

# --------------------------------------------------
# 7. UNIQUE SERVICES
# --------------------------------------------------

service_columns = [
    col for col in df.columns
    if "service" in col.lower()
]

for col in service_columns:

    print("\n" + "=" * 70)
    print(f"7. UNIQUE VALUES — {col}")
    print("=" * 70)

    print(
        df[col]
        .dropna()
        .value_counts()
        .head(30)
        .to_string()
    )

# --------------------------------------------------
# 8. MISSING VALUES
# --------------------------------------------------

print("\n" + "=" * 70)
print("8. MISSING VALUES")
print("=" * 70)

missing = df.isna().sum()

print(
    missing[missing > 0]
    .sort_values(ascending=False)
    .to_string()
)

print("\n" + "=" * 70)
print("INSPECTION COMPLETE")
print("=" * 70)