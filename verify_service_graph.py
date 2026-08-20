import shutil
from pathlib import Path

import pandas as pd
import networkx as nx
from huggingface_hub import snapshot_download


# ======================================================
# BLAST — SERVICE GRAPH VERIFICATION / EXPANSION
# ======================================================
#
# The existing service_graph.csv (build_service_graph.py)
# was built from a single trace file
# (re2ob_checkoutservice_delay_1), all under a checkout
# fault. Online Boutique's call topology is static -- it
# does not depend on which service is later fault-injected
# -- so a single trace SHOULD already capture the full
# topology as long as it exercises the whole app (home,
# product, cart, checkout), which delay_1 does (see
# JOURNEY_TYPING_RULE.md's signature catalog: all 5 page/
# action types present).
#
# This script verifies that by sampling one small trace per
# RE2-OB target service and re-extracting service-to-service
# edges, unioning with the existing graph. Confirms Gate 3
# ("graph matches known architecture") on more than a single
# sample, at the cost of 5 small downloads
# (deleted immediately after, ADR-004).
# ======================================================

REPO_ID = "phamquiluan/RCAEval"
BASE_DIR = Path("./data")
GRAPH_FILE = "service_graph.csv"

SAMPLE_CASES = [
    "re2ob_checkoutservice_delay_1",       # already known
    "re2ob_currencyservice_cpu_1",
    "re2ob_emailservice_cpu_1",
    "re2ob_productcatalogservice_cpu_1",
    "re2ob_recommendationservice_cpu_1",
]


def extract_edges(case):

    case_dir = BASE_DIR / case

    if not (case_dir / "traces.parquet").exists():
        snapshot_download(
            repo_id=REPO_ID,
            repo_type="dataset",
            allow_patterns=[f"{case}/traces.parquet"],
            local_dir=str(BASE_DIR),
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
    print("BLAST — SERVICE GRAPH VERIFICATION")
    print("=" * 100)

    existing = pd.read_csv(GRAPH_FILE)
    existing_edges = set(zip(existing["source"], existing["target"]))

    print(f"\nExisting graph: {len(existing_edges)} edges")

    all_counts = []

    for case in SAMPLE_CASES:
        print(f"\nSampling {case}...")
        counts = extract_edges(case)
        all_counts.append(counts)
        new_edges = set(zip(counts["source"], counts["target"])) - existing_edges
        if new_edges:
            print(f"  NEW edges not in existing graph: {new_edges}")
        else:
            print(f"  No new edges ({len(counts)} edges, all already known).")

    merged = pd.concat(all_counts, ignore_index=True)
    merged = merged.groupby(["source", "target"], as_index=False)["calls"].sum()

    merged_edges = set(zip(merged["source"], merged["target"]))

    print("\n")
    print("=" * 100)
    print("VERIFICATION RESULT")
    print("=" * 100)

    only_in_existing = existing_edges - merged_edges
    only_in_sample = merged_edges - existing_edges

    print(f"\nEdges in existing graph but not seen in this 5-case sample: {only_in_existing}")
    print(f"Edges seen in this 5-case sample but not in existing graph: {only_in_sample}")

    if not only_in_sample:
        print("\nCONFIRMED: existing service_graph.csv already captures the full topology "
              "observed across all 5 RE2-OB target services. No update needed.")
    else:
        print(f"\nUPDATING service_graph.csv with {len(only_in_sample)} newly discovered edge(s).")
        merged.to_csv(GRAPH_FILE, index=False)
        print(f"Saved: {GRAPH_FILE}")

    print(f"\nFinal node count: {len(set(merged['source']) | set(merged['target']))}")
    print(f"Final edge count: {len(merged_edges)}")


if __name__ == "__main__":
    main()
