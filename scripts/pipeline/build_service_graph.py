import pandas as pd
import networkx as nx

TRACE_FILE = r".\data\re2ob_checkoutservice_delay_1\traces.parquet"

df = pd.read_parquet(TRACE_FILE)

print("=" * 70)
print("BLAST — SERVICE DEPENDENCY GRAPH")
print("=" * 70)

# --------------------------------------------------
# Create span lookup
# --------------------------------------------------

span_lookup = (
    df[
        [
            "spanID",
            "traceID",
            "serviceName"
        ]
    ]
    .drop_duplicates("spanID")
    .set_index("spanID")
)

# --------------------------------------------------
# Keep spans with valid parents
# --------------------------------------------------

edges = df[
    df["parentSpanID"].notna()
].copy()

edges["parent_traceID"] = (
    edges["parentSpanID"]
    .map(span_lookup["traceID"])
)

edges["parent_service"] = (
    edges["parentSpanID"]
    .map(span_lookup["serviceName"])
)

# --------------------------------------------------
# Remove unresolved parents
# --------------------------------------------------

edges = edges.dropna(
    subset=[
        "parent_traceID",
        "parent_service"
    ]
)

# Only retain relationships inside same trace
edges = edges[
    edges["traceID"] ==
    edges["parent_traceID"]
]

# --------------------------------------------------
# Keep service-to-service calls
# --------------------------------------------------

edges = edges[
    edges["parent_service"] !=
    edges["serviceName"]
]

# --------------------------------------------------
# Build graph
# --------------------------------------------------

G = nx.DiGraph()

for _, row in edges.iterrows():

    parent = row["parent_service"]
    child = row["serviceName"]

    if G.has_edge(parent, child):
        G[parent][child]["calls"] += 1
    else:
        G.add_edge(
            parent,
            child,
            calls=1
        )

# --------------------------------------------------
# Print graph
# --------------------------------------------------

print("\nSERVICES")
print("-" * 70)

for service in sorted(G.nodes):
    print(service)

print("\nSERVICE DEPENDENCIES")
print("-" * 70)

for parent, child, data in sorted(
    G.edges(data=True)
):

    print(
        f"{parent:30} -> "
        f"{child:30} "
        f"calls={data['calls']:,}"
    )

# --------------------------------------------------
# Graph statistics
# --------------------------------------------------

print("\n" + "=" * 70)
print("GRAPH STATISTICS")
print("=" * 70)

print(f"Services : {G.number_of_nodes()}")
print(f"Edges    : {G.number_of_edges()}")

print(
    f"Valid cross-service spans: {len(edges):,}"
)

# --------------------------------------------------
# Save graph
# --------------------------------------------------

output = "results/data/service_graph.csv"

graph_rows = []

for parent, child, data in G.edges(data=True):

    graph_rows.append({
        "source": parent,
        "target": child,
        "calls": data["calls"]
    })

graph_df = pd.DataFrame(graph_rows)

graph_df.to_csv(
    output,
    index=False
)

print(f"\nSaved: {output}")

print("\nGraph construction complete.")