import pandas as pd

TRACE_FILE = r".\data\re2ob_checkoutservice_delay_1\traces.parquet"

print("=" * 70)
print("BLAST GATE 0 — TRACE TREE VALIDATION")
print("=" * 70)

df = pd.read_parquet(TRACE_FILE)

print(f"\nTotal spans: {len(df):,}")

# --------------------------------------------------
# 1. Basic identifiers
# --------------------------------------------------

print("\n" + "=" * 70)
print("1. IDENTIFIER STATISTICS")
print("=" * 70)

print(f"Unique traces : {df['traceID'].nunique():,}")
print(f"Unique spans  : {df['spanID'].nunique():,}")
print(f"Missing parent: {df['parentSpanID'].isna().sum():,}")

# --------------------------------------------------
# 2. Duplicate span IDs
# --------------------------------------------------

print("\n" + "=" * 70)
print("2. DUPLICATE SPAN IDs")
print("=" * 70)

duplicate_span_ids = df["spanID"].duplicated().sum()

print(f"Duplicate span rows: {duplicate_span_ids:,}")

# --------------------------------------------------
# 3. Parent span existence
# --------------------------------------------------

print("\n" + "=" * 70)
print("3. PARENT SPAN VALIDATION")
print("=" * 70)

span_ids = set(df["spanID"].dropna())

has_parent = df["parentSpanID"].notna()

valid_parent = (
    has_parent &
    df["parentSpanID"].isin(span_ids)
)

invalid_parent = has_parent & ~valid_parent

print(
    f"Spans with parent        : {has_parent.sum():,}"
)

print(
    f"Valid parent references   : {valid_parent.sum():,}"
)

print(
    f"Invalid parent references : {invalid_parent.sum():,}"
)

# --------------------------------------------------
# 4. Parent belongs to same trace
# --------------------------------------------------

print("\n" + "=" * 70)
print("4. SAME-TRACE PARENT VALIDATION")
print("=" * 70)

# Map spanID -> traceID
span_to_trace = (
    df[["spanID", "traceID"]]
    .drop_duplicates("spanID")
    .set_index("spanID")["traceID"]
)

child_df = df[has_parent].copy()

child_df["parentTraceID"] = (
    child_df["parentSpanID"]
    .map(span_to_trace)
)

same_trace = (
    child_df["parentTraceID"] ==
    child_df["traceID"]
)

print(
    f"Parent references checked : {len(child_df):,}"
)

print(
    f"Same-trace parents        : {same_trace.sum():,}"
)

print(
    f"Cross-trace parents       : {(~same_trace).sum():,}"
)

# --------------------------------------------------
# 5. Root spans
# --------------------------------------------------

print("\n" + "=" * 70)
print("5. ROOT SPANS")
print("=" * 70)

root_spans = df[df["parentSpanID"].isna()]

print(f"Root spans: {len(root_spans):,}")

print("\nRoot services:")

print(
    root_spans["serviceName"]
    .value_counts()
    .head(20)
    .to_string()
)

# --------------------------------------------------
# 6. Service transitions
# --------------------------------------------------

print("\n" + "=" * 70)
print("6. SERVICE-TO-SERVICE EDGES")
print("=" * 70)

# Map parent span -> service
span_to_service = (
    df[["spanID", "serviceName"]]
    .drop_duplicates("spanID")
    .set_index("spanID")["serviceName"]
)

edges = df[has_parent].copy()

edges["parentService"] = (
    edges["parentSpanID"]
    .map(span_to_service)
)

edges = edges.dropna(
    subset=["parentService", "serviceName"]
)

# Only cross-service calls
edges = edges[
    edges["parentService"] != edges["serviceName"]
]

service_edges = (
    edges[
        ["parentService", "serviceName"]
    ]
    .drop_duplicates()
    .sort_values(
        ["parentService", "serviceName"]
    )
)

print(
    f"\nUnique service-to-service edges: "
    f"{len(service_edges)}"
)

print()

for _, row in service_edges.iterrows():
    print(
        f"{row['parentService']} "
        f"-> "
        f"{row['serviceName']}"
    )

# --------------------------------------------------
# 7. Summary
# --------------------------------------------------

print("\n" + "=" * 70)
print("GATE 0 SUMMARY")
print("=" * 70)

if invalid_parent.sum() == 0:
    print("✓ All non-null parentSpanIDs reference existing spans")
else:
    print("⚠ Some parentSpanIDs do not reference existing spans")

if (~same_trace).sum() == 0:
    print("✓ All parent-child relationships stay within the same trace")
else:
    print("⚠ Cross-trace parent relationships detected")

print(
    f"✓ {len(service_edges)} service dependency edges discovered"
)

print("\nValidation complete.")