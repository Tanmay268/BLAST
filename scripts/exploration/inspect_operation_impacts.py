import pandas as pd

INPUT_FILE = "results/data/impairment_detection_results.csv"

print("=" * 110)
print("BLAST — OPERATION-LEVEL IMPACT INSPECTION")
print("=" * 110)

df = pd.read_csv(INPUT_FILE)

print(f"\nRows: {len(df):,}")
print(f"Columns: {list(df.columns)}")

print("\n")
print("=" * 110)
print("RAW OPERATION-LEVEL DATA")
print("=" * 110)

print(
    df.to_string(
        index=False
    )
)

print("\n")
print("=" * 110)
print("IMPAIRED OPERATIONS")
print("=" * 110)

impaired = df[
    df["impaired"] == True
].copy()

print(
    impaired.to_string(
        index=False
    )
)

print("\n")
print("=" * 110)
print("IMPAIRED OPERATION COUNTS")
print("=" * 110)

print(
    impaired
    .groupby(
        [
            "fault_type",
            "service"
        ]
    )
    .size()
    .reset_index(
        name="impaired_rows"
    )
    .to_string(
        index=False
    )
)

print("\n")
print("=" * 110)
print("OPERATION DISTRIBUTION")
print("=" * 110)

for service, group in (
    impaired.groupby("service")
):

    print(f"\nSERVICE: {service}")

    print(
        group[
            [
                "method",
                "operation",
                "impairment_score"
            ]
        ].to_string(
            index=False
        )
    )

print("\nInspection complete.")