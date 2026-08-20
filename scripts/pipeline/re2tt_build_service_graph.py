import shutil
from pathlib import Path

import pandas as pd
import networkx as nx
from huggingface_hub import snapshot_download


# ======================================================
# BLAST — TRAIN TICKET SERVICE GRAPH
# ======================================================
#
# Same edge-extraction logic as build_service_graph.py /
# verify_service_graph.py, applied to Train Ticket. Unlike
# Online Boutique (verified complete from a SINGLE trace,
# since one user session touches the whole app), Train
# Ticket's 27 services and lack of a single frontend gateway
# means sampling from just one target service's traces risks
# missing edges reachable only from a different entry point --
# so this samples one case per target service (5 samples,
# not 1) before taking the union.
# ======================================================

REPO_ID = "phamquiluan/RCAEval"
BASE_DIR = Path("./data")

SAMPLE_CASES = [
    "re2tt_ts-auth-service_cpu_1",
    "re2tt_ts-order-service_cpu_1",
    "re2tt_ts-route-service_cpu_1",
    "re2tt_ts-train-service_cpu_1",
    "re2tt_ts-travel-service_cpu_1",
]

OUTPUT_FILE = "results/data/re2tt_service_graph.csv"


def extract_edges(case):

    case_dir = BASE_DIR / case

    if not (case_dir / "traces.parquet").exists():
        snapshot_download(
            repo_id=REPO_ID, repo_type="dataset",
            allow_patterns=[f"{case}/traces.parquet"], local_dir=str(BASE_DIR),
        )

    df = pd.read_parquet(case_dir / "traces.parquet")

    span_lookup = (
        df[["spanID", "traceID", "serviceName"]]
        .drop_duplicates("spanID")
        .set_index("spanID")
    )

    edges = df[df["parentSpanID"].notna()].copy()
    edges["parent_traceID"] = edges["parentSpanID"].map(span_lookup["traceID"])
    edges["parent_service"] = edges["parentSpanID"].map(span_lookup["serviceName"])
    edges = edges.dropna(subset=["parent_traceID", "parent_service"])
    edges = edges[edges["traceID"] == edges["parent_traceID"]]
    edges = edges[edges["parent_service"] != edges["serviceName"]]

    counts = (
        edges.groupby(["parent_service", "serviceName"])
        .size()
        .reset_index(name="calls")
        .rename(columns={"parent_service": "source", "serviceName": "target"})
    )

    shutil.rmtree(case_dir, ignore_errors=True)

    return counts


def main():

    print("=" * 100)
    print("BLAST — TRAIN TICKET SERVICE GRAPH CONSTRUCTION")
    print("=" * 100)

    all_counts = []

    for case in SAMPLE_CASES:
        print(f"\nSampling {case}...")
        counts = extract_edges(case)
        print(f"  {len(counts)} edges, {counts[['source','target']].values.tolist()[:3]}...")
        all_counts.append(counts)

    merged = pd.concat(all_counts, ignore_index=True)
    merged = merged.groupby(["source", "target"], as_index=False)["calls"].sum()

    G = nx.DiGraph()
    for _, row in merged.iterrows():
        G.add_edge(row["source"], row["target"], calls=int(row["calls"]))

    print("\n")
    print("=" * 100)
    print("GRAPH SUMMARY")
    print("=" * 100)
    print(f"Services (nodes): {G.number_of_nodes()}")
    print(f"Edges: {G.number_of_edges()}")

    isolated_targets = [
        s for s in ["ts-auth-service", "ts-order-service", "ts-route-service",
                     "ts-train-service", "ts-travel-service"]
        if s not in G
    ]
    if isolated_targets:
        print(f"\nWARNING: target service(s) not appearing in the sampled graph at all: "
              f"{isolated_targets} -- check these services' traces directly if propagation "
              f"testing later can't find them.")

    merged.to_csv(OUTPUT_FILE, index=False)
    print(f"\nSaved: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
