import pandas as pd
import numpy as np

# ============================================================
# CONFIG
# ============================================================

IMPAIRMENT_FILE = "impairment_detection_results.csv"
CAPABILITY_FILE = "business_capabilities.csv"

OUTPUT_IMPACTS = "capability_impacts.csv"
OUTPUT_MATRIX = "incident_capability_matrix.csv"
OUTPUT_OVERLAP = "incident_capability_overlap.csv"


# ============================================================
# LOAD
# ============================================================

print("=" * 110)
print("BLAST — BUSINESS CAPABILITY IMPACT CONSTRUCTION")
print("=" * 110)

print("\nLoading impairment observations...")
imp = pd.read_csv(IMPAIRMENT_FILE)

print(f"Impairment rows: {len(imp)}")

print("\nLoading capability mapping...")
cap = pd.read_csv(CAPABILITY_FILE)

print(f"Capability mappings: {len(cap)}")


# ============================================================
# NORMALIZE COLUMN NAMES
# ============================================================

imp.columns = imp.columns.str.strip()
cap.columns = cap.columns.str.strip()

# Expected impairment columns:
# case, fault_type, service, impaired, impairment_score

required_imp = [
    "case",
    "fault_type",
    "service",
    "impaired",
    "impairment_score"
]

missing = [
    c for c in required_imp
    if c not in imp.columns
]

if missing:
    raise ValueError(
        f"Missing impairment columns: {missing}"
    )


# ============================================================
# CAPABILITY MAPPING
# ============================================================

print("\nCapability mapping columns:")
print(list(cap.columns))

# Automatically detect likely columns.
service_col = None
capability_col = None

for c in cap.columns:
    lc = c.lower()

    if lc in ["service", "servicename", "service_name"]:
        service_col = c

    if lc in [
        "business_capability",
        "capability",
        "business_capabilities"
    ]:
        capability_col = c

if service_col is None or capability_col is None:
    raise ValueError(
        "Could not identify service/capability columns "
        f"in {list(cap.columns)}"
    )

cap = cap[
    [service_col, capability_col]
].drop_duplicates()

cap.columns = [
    "service",
    "business_capability"
]


# ============================================================
# BUILD INCIDENT-CAPABILITY IMPACTS
# ============================================================

rows = []

for _, r in imp.iterrows():

    incident_id = r["case"]
    fault_type = r["fault_type"]
    service = r["service"]

    impaired = bool(r["impaired"])
    score = float(r["impairment_score"])

    mappings = cap[
        cap["service"] == service
    ]

    # --------------------------------------------------------
    # Every mapped capability gets a row.
    #
    # But capability_impact is ONLY non-zero when the
    # service itself is empirically impaired.
    # --------------------------------------------------------

    for _, m in mappings.iterrows():

        capability = m["business_capability"]

        capability_impaired = impaired

        capability_impact = (
            score
            if capability_impaired
            else 0.0
        )

        rows.append({
            "incident_id": incident_id,
            "case": incident_id,
            "fault_type": fault_type,
            "service": service,
            "business_capability": capability,
            "impaired": impaired,
            "capability_impaired": capability_impaired,
            "impairment_score": score,
            "capability_impact": capability_impact
        })


impact = pd.DataFrame(rows)


# ============================================================
# INCIDENT → CAPABILITY IMPACT
# ============================================================

print("\n")
print("=" * 110)
print("INCIDENT → BUSINESS CAPABILITY IMPACT")
print("=" * 110)

print(
    impact.to_string(index=False)
)


# ============================================================
# IMPORTANT:
# DEDUPLICATE INCIDENT-CAPABILITY PAIRS
# ============================================================

# An incident may have multiple service observations that map
# to the same capability.
#
# For probability estimation we must count an incident only
# once per capability.

incident_capability = (
    impact
    .groupby(
        [
            "incident_id",
            "fault_type",
            "business_capability"
        ],
        as_index=False
    )
    .agg(
        capability_impact=(
            "capability_impact",
            "max"
        ),
        capability_impaired=(
            "capability_impaired",
            "max"
        )
    )
)


# ============================================================
# CAPABILITY IMPACT SUMMARY
# ============================================================

summary = (
    incident_capability
    .groupby(
        [
            "fault_type",
            "business_capability"
        ],
        as_index=False
    )
    .agg(
        incidents=(
            "incident_id",
            "nunique"
        ),
        impaired_incidents=(
            "capability_impaired",
            "sum"
        ),
        mean_impact=(
            "capability_impact",
            "mean"
        ),
        max_impact=(
            "capability_impact",
            "max"
        )
    )
)

# This is now guaranteed to be <= 1.
summary[
    "empirical_impact_probability"
] = (
    summary["impaired_incidents"]
    / summary["incidents"]
)


print("\n")
print("=" * 110)
print("CAPABILITY IMPACT SUMMARY")
print("=" * 110)

print(
    summary.to_string(index=False)
)


# ============================================================
# INCIDENT × CAPABILITY MATRIX
# ============================================================

matrix = (
    incident_capability
    .pivot_table(
        index=[
            "incident_id",
            "fault_type"
        ],
        columns="business_capability",
        values="capability_impaired",
        aggfunc="max",
        fill_value=False
    )
    .astype(int)
    .reset_index()
)

print("\n")
print("=" * 110)
print("INCIDENT × CAPABILITY COVERAGE MATRIX")
print("=" * 110)

print(
    matrix.to_string(index=False)
)


# ============================================================
# JACCARD OVERLAP
# ============================================================

sets = {}

for _, row in matrix.iterrows():

    incident = row["incident_id"]

    capabilities = {
        c
        for c in matrix.columns
        if c not in ["incident_id", "fault_type"]
        and row[c] == 1
    }

    sets[incident] = capabilities


overlap_rows = []

incident_ids = list(sets.keys())

for i in range(len(incident_ids)):

    for j in range(i + 1, len(incident_ids)):

        a = incident_ids[i]
        b = incident_ids[j]

        A = sets[a]
        B = sets[b]

        intersection = A & B
        union = A | B

        jaccard = (
            len(intersection) / len(union)
            if union
            else 0.0
        )

        overlap_rows.append({
            "incident_a": a,
            "incident_b": b,
            "intersection_size": len(intersection),
            "union_size": len(union),
            "jaccard_overlap": jaccard,
            "overlapping_capabilities":
                ";".join(sorted(intersection))
        })


overlap = pd.DataFrame(overlap_rows)


print("\n")
print("=" * 110)
print("INCIDENT CAPABILITY OVERLAP")
print("=" * 110)

if len(overlap) > 0:
    print(
        overlap.sort_values(
            "jaccard_overlap",
            ascending=False
        ).to_string(index=False)
    )


# ============================================================
# CAPABILITY REDUNDANCY
# ============================================================

redundancy = (
    incident_capability[
        incident_capability["capability_impaired"] == True
    ]
    .groupby(
        "business_capability"
    )["incident_id"]
    .nunique()
    .reset_index(
        name="number_of_incidents"
    )
    .sort_values(
        "number_of_incidents",
        ascending=False
    )
)

print("\n")
print("=" * 110)
print("CAPABILITY REDUNDANCY")
print("=" * 110)

print(
    redundancy.to_string(index=False)
)


# ============================================================
# SAVE
# ============================================================

summary.to_csv(
    OUTPUT_IMPACTS,
    index=False
)

matrix.to_csv(
    OUTPUT_MATRIX,
    index=False
)

overlap.to_csv(
    OUTPUT_OVERLAP,
    index=False
)

print("\n")
print("=" * 110)
print("FILES SAVED")
print("=" * 110)

print(f"Capability impacts: {OUTPUT_IMPACTS}")
print(f"Incident-capability matrix: {OUTPUT_MATRIX}")
print(f"Incident-capability overlap: {OUTPUT_OVERLAP}")

print("\nCapability impact construction complete.")