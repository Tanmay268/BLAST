import json
from pathlib import Path

import pandas as pd
import yaml
import networkx as nx
import streamlit as st

# Repo root, regardless of where `streamlit run` is invoked from.
ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results" / "data"


@st.cache_data
def load_overlay():
    with open(ROOT / "business_overlay" / "online_boutique_v2.yaml") as f:
        overlay = yaml.safe_load(f)
    capability_ids = [c["id"] for c in overlay["capabilities"]]
    display = {c["id"]: c["display"] for c in overlay["capabilities"]}
    weights = {c["id"]: c["value_per_min"] for c in overlay["capabilities"]}
    realised_by = {c["id"]: c["realised_by"] for c in overlay["capabilities"]}
    return overlay, capability_ids, display, weights, realised_by


@st.cache_data
def load_split():
    with open(ROOT / "config" / "splits" / "split_v1.yaml") as f:
        return yaml.safe_load(f)


@st.cache_data
def load_service_graph():
    df = pd.read_csv(RESULTS / "service_graph.csv")
    G = nx.DiGraph()
    for _, row in df.iterrows():
        G.add_edge(row["source"], row["target"], calls=int(row["calls"]))
    return df, G


@st.cache_data
def load_incident_probabilities():
    return pd.read_csv(RESULTS / "incident_capability_probabilities.csv")


@st.cache_data
def load_incident_magnitude():
    return pd.read_csv(RESULTS / "incident_capability_magnitude.csv")


@st.cache_data
def load_case_magnitude():
    return pd.read_csv(RESULTS / "case_capability_magnitude.csv")


@st.cache_data
def load_footprint():
    return pd.read_csv(RESULTS / "incident_type_capability_footprint.csv")


@st.cache_data
def load_evaluation():
    per_scenario = pd.read_csv(RESULTS / "evaluation_per_scenario.csv")
    aggregate = pd.read_csv(RESULTS / "evaluation_aggregate.csv")
    stats = pd.read_csv(RESULTS / "evaluation_statistics.csv")
    return per_scenario, aggregate, stats


@st.cache_data
def load_scenarios():
    with open(RESULTS / "ground_truth_scenarios.json") as f:
        return json.load(f)


@st.cache_data
def load_heterogeneity_sweep():
    return pd.read_csv(RESULTS / "heterogeneity_sweep_results.csv")


@st.cache_data
def load_propagation_prevalence():
    detail = pd.read_csv(RESULTS / "propagation_prevalence.csv")
    summary = pd.read_csv(RESULTS / "propagation_prevalence_summary.csv")
    return detail, summary


@st.cache_data
def load_journey_impairment():
    return pd.read_csv(RESULTS / "journey_impairment_full.csv")


@st.cache_data
def load_excluded_cases():
    path = RESULTS / "excluded_cases.csv"
    if path.exists():
        return pd.read_csv(path)
    return pd.DataFrame()
