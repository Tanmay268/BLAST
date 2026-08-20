import pandas as pd
from pathlib import Path


# ======================================================
# BLAST — BUSINESS CAPABILITY MAPPING
# ======================================================

TRACE_FILE = Path(
    "./data/re2ob_checkoutservice_delay_1/traces.parquet"
)

OUTPUT_FILE = "business_capabilities.csv"


# ======================================================
# LOAD TRACE DATA
# ======================================================

print("=" * 110)
print("BLAST — BUSINESS CAPABILITY DISCOVERY")
print("=" * 110)

print("\nLoading trace data...")

df = pd.read_parquet(
    TRACE_FILE
)

print(
    f"Total spans: {len(df):,}"
)


# ======================================================
# SERVICE / OPERATION INVENTORY
# ======================================================

print("\n")
print("=" * 110)
print("SERVICE → OPERATION INVENTORY")
print("=" * 110)

inventory = (
    df[
        [
            "serviceName",
            "methodName",
            "operationName"
        ]
    ]
    .drop_duplicates()
    .sort_values(
        [
            "serviceName",
            "operationName"
        ]
    )
)

for service, group in inventory.groupby(
    "serviceName"
):

    print("\n" + "-" * 100)
    print(f"SERVICE: {service}")
    print("-" * 100)

    operations = (
        group["operationName"]
        .dropna()
        .unique()
    )

    for operation in operations:

        print(
            f"  {operation}"
        )


# ======================================================
# OPERATION FREQUENCY
# ======================================================

print("\n")
print("=" * 110)
print("TOP OPERATIONS BY SPAN VOLUME")
print("=" * 110)

operation_counts = (
    df[
        [
            "serviceName",
            "operationName"
        ]
    ]
    .dropna()
    .groupby(
        [
            "serviceName",
            "operationName"
        ]
    )
    .size()
    .reset_index(
        name="span_count"
    )
    .sort_values(
        "span_count",
        ascending=False
    )
)

print(
    operation_counts
    .head(50)
    .to_string(
        index=False
    )
)


# ======================================================
# ROOT OPERATIONS
# ======================================================

print("\n")
print("=" * 110)
print("ROOT / ENTRY OPERATIONS")
print("=" * 110)

roots = df[
    df["parentSpanID"].isna()
].copy()

root_operations = (
    roots[
        [
            "serviceName",
            "methodName",
            "operationName"
        ]
    ]
    .value_counts()
    .reset_index(
        name="trace_count"
    )
    .sort_values(
        "trace_count",
        ascending=False
    )
)

print(
    root_operations
    .head(50)
    .to_string(
        index=False
    )
)


# ======================================================
# CANDIDATE BUSINESS CAPABILITY MAPPING
# ======================================================
#
# IMPORTANT:
#
# These are candidate semantic labels derived from
# the observed Hipster Shop operations.
#
# They are NOT claims that the dataset explicitly
# provides business labels.
#
# We will validate/revise this mapping before using
# it as ground truth.
#
# ======================================================

CAPABILITY_MAP = {

    # --------------------------------------------------
    # Product discovery
    # --------------------------------------------------

    "GetProduct":
        "Product Browsing",

    "ListProducts":
        "Product Browsing",

    "ListRecommendations":
        "Product Recommendations",

    "GetAds":
        "Advertisement Retrieval",

    # --------------------------------------------------
    # Cart
    # --------------------------------------------------

    "AddItem":
        "Cart Management",

    "GetCart":
        "Cart Management",

    "EmptyCart":
        "Cart Management",

    # --------------------------------------------------
    # Currency
    # --------------------------------------------------

    "Convert":
        "Currency Conversion",

    "GetSupportedCurrencies":
        "Currency Conversion",

    # --------------------------------------------------
    # Order
    # --------------------------------------------------

    "PlaceOrder":
        "Order Placement",

    # --------------------------------------------------
    # Payment
    # --------------------------------------------------

    "Charge":
        "Payment Processing",

    # --------------------------------------------------
    # Confirmation
    # --------------------------------------------------

    "SendOrderConfirmation":
        "Order Confirmation",

    # --------------------------------------------------
    # Shipping
    # --------------------------------------------------

    "GetQuote":
        "Shipping",

    "ShipOrder":
        "Shipping",
}

# ======================================================
# BUILD MAPPING FROM ACTUAL OPERATIONS
# ======================================================

mapping_rows = []


for _, row in inventory.iterrows():

    service = row[
        "serviceName"
    ]

    method = row[
        "methodName"
    ]

    operation = row[
        "operationName"
    ]

    capability = None

    # --------------------------------------------------
    # Exact method match
    # --------------------------------------------------

    if pd.notna(method):

        if method in CAPABILITY_MAP:

            capability = CAPABILITY_MAP[
                method
            ]

    # --------------------------------------------------
    # Operation keyword matching
    # --------------------------------------------------

    if capability is None:

        operation_text = str(
            operation
        ).lower()

        method_text = str(
            method
        ).lower()

        combined = (
            operation_text
            + " "
            + method_text
        )

        if (
            "recommend" in combined
        ):

            capability = (
                "Product Recommendations"
            )

        elif (
            "product" in combined
            or "catalog" in combined
        ):

            capability = (
                "Product Browsing"
            )

        elif (
            "currency" in combined
            or "convert" in combined
        ):

            capability = (
                "Currency Conversion"
            )

        elif (
            "checkout" in combined
            or "order" in combined
        ):

            capability = (
                "Order Placement"
            )

        elif (
            "payment" in combined
            or "charge" in combined
        ):

            capability = (
                "Payment Processing"
            )

        elif (
            "email" in combined
            or "confirmation" in combined
        ):

            capability = (
                "Order Confirmation"
            )

        elif (
            "cart" in combined
        ):

            capability = (
                "Cart Management"
            )

    # --------------------------------------------------
    # Store only mapped operations
    # --------------------------------------------------

    if capability is not None:

        mapping_rows.append({

            "service":
                service,

            "method":
                method,

            "operation":
                operation,

            "business_capability":
                capability,

            "mapping_source":
                "candidate_semantic_mapping",
        })


mapping = pd.DataFrame(
    mapping_rows
)


# ======================================================
# SAVE MAPPING
# ======================================================

mapping.to_csv(
    OUTPUT_FILE,
    index=False
)


# ======================================================
# DISPLAY MAPPING
# ======================================================

print("\n")
print("=" * 110)
print("CANDIDATE BUSINESS CAPABILITY MAPPING")
print("=" * 110)

if mapping.empty:

    print(
        "No candidate mappings were discovered."
    )

else:

    print(
        mapping.to_string(
            index=False
        )
    )


# ======================================================
# CAPABILITY SUMMARY
# ======================================================

print("\n")
print("=" * 110)
print("CAPABILITY SUMMARY")
print("=" * 110)

if not mapping.empty:

    capability_summary = (
        mapping
        .groupby(
            "business_capability"
        )
        .agg(
            services=(
                "service",
                "nunique"
            ),

            operations=(
                "operation",
                "nunique"
            )
        )
        .reset_index()
        .sort_values(
            "business_capability"
        )
    )

    print(
        capability_summary.to_string(
            index=False
        )
    )


# ======================================================
# UNMAPPED OPERATIONS
# ======================================================

print("\n")
print("=" * 110)
print("UNMAPPED OPERATIONS")
print("=" * 110)

mapped_operations = set(
    mapping["operation"]
    if not mapping.empty
    else []
)

unmapped = inventory[
    ~inventory["operationName"].isin(
        mapped_operations
    )
]

if unmapped.empty:

    print(
        "All operations were mapped."
    )

else:

    print(
        unmapped.to_string(
            index=False
        )
    )


# ======================================================
# SERVICE → CAPABILITY SUMMARY
# ======================================================

print("\n")
print("=" * 110)
print("SERVICE → BUSINESS CAPABILITY")
print("=" * 110)

if not mapping.empty:

    service_capabilities = (
        mapping
        .groupby(
            "service"
        )[
            "business_capability"
        ]
        .unique()
    )

    for service, capabilities in (
        service_capabilities.items()
    ):

        print(
            f"\n{service}:"
        )

        for capability in capabilities:

            print(
                f"  → {capability}"
            )


# ======================================================
# FINAL
# ======================================================

print("\n")
print("=" * 110)
print("RESULT SAVED")
print("=" * 110)

print(
    f"File: {OUTPUT_FILE}"
)

print(
    "\nBusiness capability discovery complete."
)