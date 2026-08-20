import numpy as np
import pandas as pd
import networkx as nx
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

from data import (
    load_overlay, load_split, load_service_graph, load_incident_probabilities,
    load_incident_magnitude, load_case_magnitude, load_footprint, load_evaluation,
    load_scenarios, load_heterogeneity_sweep, load_propagation_prevalence,
    load_journey_impairment, load_excluded_cases,
)
from ranking import blast_greedy_order, independent_order, evaluate_order


# ======================================================
# VIEW 1 — OVERVIEW & FINDINGS
# ======================================================

def render_overview():

    st.title("BLAST — Business-Loss Aware Structural Triage")
    st.caption(
        "Ranks concurrent microservice incidents by expected business-capability loss, "
        "treating prioritization as set-selection rather than per-incident scoring."
    )

    per_scenario, aggregate, stats = load_evaluation()
    prevalence_detail, prevalence_summary = load_propagation_prevalence()
    footprint = load_footprint()

    ndcg_row = stats[(stats["baseline"] == "B9_independent") & (stats["metric"] == "ndcg_5")].iloc[0]
    cbl_row = stats[(stats["baseline"] == "B9_independent") & (stats["metric"] == "cbl")].iloc[0]

    st.subheader("Gate 4 result: MIXED")
    st.warning(
        "BLAST beats its own independent-scoring ablation (B9) on **ranking quality** "
        "(NDCG@5) with a real, practically significant effect — but the **Cumulative "
        "Business Loss** advantage, while statistically detectable, is practically "
        "negligible. Reported honestly rather than forced into a clean pass. "
        "See `context/01_DECISION_LOG.md`, ADR-019 and ADR-020, for the full diagnosis."
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("NDCG@5 — BLAST", f"{ndcg_row['blast_mean']:.3f}",
              f"{ndcg_row['blast_mean'] - ndcg_row['baseline_mean']:+.3f} vs B9")
    c2.metric("NDCG@5 Cliff's δ", f"{ndcg_row['cliffs_delta']:.3f}", "real effect (≥0.147)")
    c3.metric("CBL Cliff's δ (vs B9)", f"{cbl_row['cliffs_delta']:.3f}", "negligible (<0.147)",
              delta_color="off")
    c4.metric("Propagation prevalence", f"{0:.0%}", "0/20 tested edges (ADR-018)",
              delta_color="off")

    st.subheader("BLAST vs every baseline — NDCG@5 and CBL")

    agg = aggregate.set_index("method")
    fig = go.Figure()
    fig.add_bar(name="NDCG@5", x=agg.index, y=agg["ndcg_5_mean"], yaxis="y1")
    fig.add_bar(name="CBL (lower is better)", x=agg.index, y=agg["cbl_mean"], yaxis="y2")
    fig.update_layout(
        barmode="group",
        yaxis=dict(title="NDCG@5"),
        yaxis2=dict(title="CBL", overlaying="y", side="right"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        height=420,
    )
    st.plotly_chart(fig, width='stretch')

    st.subheader("Capability-footprint saturation across the full corpus")
    n_saturated = int((footprint["capabilities_covered"] == footprint["capabilities_covered"].max()).sum())
    st.write(
        f"Across all 30 (service, fault-type) incident types, mean capability coverage is "
        f"**{footprint['capabilities_covered'].mean():.2f} / 9** capabilities — no incident "
        f"type covers all 9 (was ≥78% saturated under the original service-level attribution "
        f"bug, ADR-014). Footprints are largely **structurally determined by target service**, "
        f"not by fault type — see the Capability Path Viewer tab."
    )

    with st.expander("What this project deliberately does NOT claim"):
        st.markdown(
            "- No real revenue was measured — business values are declared, relative units "
            "(ADR-002), sensitivity-tested, never presented as currency.\n"
            "- Multi-incident scenarios are composed from independently-injected faults "
            "using conservative union/max semantics (TV-2) — not observed simultaneity.\n"
            "- The heterogeneity sweep (ADR-020) tested and did **not** confirm the "
            "hypothesis that footprint diversity alone explains the CBL result — reported "
            "as a genuine negative finding, not hidden."
        )


# ======================================================
# VIEW 2 — RANKED INCIDENT QUEUE (interactive)
# ======================================================

def render_ranker():

    st.title("Ranked incident queue")
    st.caption(
        "Compose a scenario from real RE2-OB incident types and watch BLAST rank them "
        "live, using the same probabilistic objective as the evaluation harness."
    )

    overlay, capability_ids, display, weights, realised_by = load_overlay()
    prob_df = load_incident_probabilities()
    case_mag = load_case_magnitude()

    type_probabilities = {}
    for (svc, ft), g in prob_df.groupby(["service", "fault_type"]):
        type_probabilities[(svc, ft)] = dict(zip(g["capability_id"], g["p_smoothed"]))

    all_types = sorted(type_probabilities.keys())
    type_labels = {t: f"{t[0]} / {t[1]}" for t in all_types}

    selected = st.multiselect(
        "Select 3–10 incident types for this scenario",
        options=all_types,
        default=all_types[:5],
        format_func=lambda t: type_labels[t],
    )

    if len(selected) < 2:
        st.info("Select at least 2 incident types to rank.")
        return

    id_to_type = {f"{s}::{f}": (s, f) for s, f in selected}
    incident_ids = list(id_to_type.keys())

    blast_order, steps = blast_greedy_order(incident_ids, id_to_type, type_probabilities, weights)
    indep_order, indep_score = independent_order(incident_ids, id_to_type, type_probabilities, weights)

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("BLAST (set-selection)")
        for rank, step in enumerate(steps, start=1):
            svc, ft = id_to_type[step["incident"]]
            with st.container(border=True):
                st.markdown(f"**#{rank}. {svc} / {ft}**")
                st.caption(
                    f"marginal gain: {step['marginal_gain']:.2f} · "
                    f"cumulative expected loss: {step['cumulative_F']:.2f}"
                )
                caps = type_probabilities.get(id_to_type[step["incident"]], {})
                top_caps = sorted(caps.items(), key=lambda kv: -kv[1])[:3]
                st.write(", ".join(f"{display.get(c, c)} (p={p:.2f})" for c, p in top_caps))

    with col2:
        st.subheader("B9 — independent scoring")
        for rank, i in enumerate(indep_order, start=1):
            svc, ft = id_to_type[i]
            with st.container(border=True):
                st.markdown(f"**#{rank}. {svc} / {ft}**")
                st.caption(f"standalone score: {indep_score[i]:.2f}")

    if blast_order == indep_order:
        st.info("Both methods produced the same order for this scenario.")
    else:
        st.success("BLAST reordered relative to independent scoring — set-overlap reasoning changed the priority.")


# ======================================================
# VIEW 3 — BUSINESS DEPENDENCY GRAPH (interactive)
# ======================================================

def render_graph():

    st.title("Business dependency graph")
    st.caption(
        "Service call topology, verified against a sample from all 5 RE2-OB target "
        "services (`scripts/pipeline/verify_service_graph.py`)."
    )

    graph_df, G = load_service_graph()
    pagerank = nx.pagerank(G)

    pos = nx.spring_layout(G, seed=20260820)

    edge_x, edge_y = [], []
    for u, v in G.edges():
        edge_x += [pos[u][0], pos[v][0], None]
        edge_y += [pos[u][1], pos[v][1], None]

    edge_trace = go.Scatter(x=edge_x, y=edge_y, line=dict(width=1, color="#888"),
                             hoverinfo="none", mode="lines")

    node_x = [pos[n][0] for n in G.nodes()]
    node_y = [pos[n][1] for n in G.nodes()]
    node_size = [20 + 80 * pagerank[n] for n in G.nodes()]
    node_text = [f"{n}<br>PageRank: {pagerank[n]:.3f}" for n in G.nodes()]

    node_trace = go.Scatter(
        x=node_x, y=node_y, mode="markers+text",
        text=list(G.nodes()), textposition="top center",
        hovertext=node_text, hoverinfo="text",
        marker=dict(size=node_size, color=list(pagerank.values()), colorscale="Blues",
                    showscale=True, colorbar=dict(title="PageRank")),
    )

    fig = go.Figure(data=[edge_trace, node_trace])
    fig.update_layout(showlegend=False, height=500,
                       xaxis=dict(visible=False), yaxis=dict(visible=False))
    st.plotly_chart(fig, width='stretch')

    st.subheader("Propagation prevalence per edge")
    st.caption(
        "Rigorously tested (Mann-Whitney + Holm correction + Cliff's-delta practical floor) "
        "across all 90 corpus cases — ADR-018."
    )

    detail, summary = load_propagation_prevalence()

    edge_summary = (
        detail.groupby(["source", "target"])
        .agg(edges_tested=("propagated", "size"), edges_propagated=("propagated", "sum"))
        .reset_index()
    )
    edge_summary["prevalence"] = edge_summary["edges_propagated"] / edge_summary["edges_tested"]

    st.dataframe(edge_summary, width='stretch', hide_index=True)


# ======================================================
# VIEW 4 — CAPABILITY PATH VIEWER
# ======================================================

def render_propagation():

    st.title("Capability path viewer")
    st.caption(
        "Graph-based multi-hop propagation is essentially absent in this benchmark "
        "(ADR-018) — the path that actually matters is: target service → impaired "
        "journey type → realised business capability."
    )

    overlay, capability_ids, display, weights, realised_by = load_overlay()
    footprint = load_footprint()
    journeys = load_journey_impairment()

    services = sorted(footprint["service"].unique())
    faults = sorted(footprint["fault_type"].unique())

    col1, col2 = st.columns(2)
    svc = col1.selectbox("Target service", services)
    fault = col2.selectbox("Fault type", faults)

    case_journeys = journeys[
        (journeys["target_service"] == svc) & (journeys["fault_type"] == fault)
    ]

    impaired = case_journeys[case_journeys["impaired"]]

    if impaired.empty:
        st.info(f"No journey type was impaired for {svc} / {fault} (across its repetitions) "
                f"beyond the statistical/practical significance floor.")
        return

    st.subheader(f"{svc} / {fault} — impact path")

    for case, group in impaired.groupby("case"):
        for _, row in group.iterrows():
            ops = [o for o in str(row["signature"]).split("+") if o]
            touched_caps = set()
            for op in ops:
                for cap_id, ops_list in realised_by.items():
                    if op in ops_list:
                        touched_caps.add(cap_id)

            with st.container(border=True):
                st.markdown(
                    f"**{svc}** → *{row['journey_label']}* "
                    f"(p95 ratio {row['p95_ratio']:.2f}, effect size {row['effect_size']:.2f}) → "
                    + ", ".join(f"**{display[c]}**" for c in sorted(touched_caps))
                )


# ======================================================
# VIEW 5 — BLAST VS BASELINES
# ======================================================

def render_comparison():

    st.title("BLAST vs every baseline")

    per_scenario, aggregate, stats = load_evaluation()

    k_filter = st.selectbox("Scenario size (k)", options=["All"] + sorted(per_scenario["k"].unique().tolist()))

    df = per_scenario if k_filter == "All" else per_scenario[per_scenario["k"] == k_filter]

    metric = st.radio("Metric", ["ndcg_5", "cbl", "kendalls_tau", "mrr"], horizontal=True)

    fig = px.box(df, x="method", y=metric, points="all", color="method")
    fig.update_layout(height=450, showlegend=False)
    st.plotly_chart(fig, width='stretch')

    st.subheader("Statistical comparison vs BLAST (paired, Holm-corrected)")
    display_stats = stats.copy()
    display_stats["result"] = np.where(
        display_stats["blast_significantly_better"], "BLAST wins (real)",
        np.where(display_stats["statistically_significant_win"], "significant, not practical", "no difference"),
    )
    st.dataframe(
        display_stats[["metric", "baseline", "blast_mean", "baseline_mean",
                        "p_value_holm", "cliffs_delta", "result"]],
        width='stretch', hide_index=True,
    )


# ======================================================
# VIEW 6 — HETEROGENEITY SWEEP
# ======================================================

def render_heterogeneity():

    st.title("Synthetic-topology heterogeneity sweep")
    st.caption(
        "Tests whether BLAST's CBL advantage over independent scoring emerges as "
        "capability-footprint heterogeneity increases. It did not (ADR-020) — reported "
        "as a genuine, diagnosed negative finding."
    )

    sweep = load_heterogeneity_sweep()

    fig = go.Figure()
    fig.add_scatter(x=sweep["heterogeneity"], y=sweep["cbl_blast_mean"], mode="lines+markers", name="BLAST")
    fig.add_scatter(x=sweep["heterogeneity"], y=sweep["cbl_b9_mean"], mode="lines+markers", name="B9 (independent)")
    fig.update_layout(
        xaxis_title="Capability-footprint heterogeneity",
        yaxis_title="Mean Cumulative Business Loss (lower is better)",
        height=420,
    )
    st.plotly_chart(fig, width='stretch')

    st.write(
        "B9 outperforms BLAST on CBL at **every** heterogeneity level tested, including full "
        "heterogeneity (h=1.0) — the opposite of the pre-committed pivot's hypothesis. A "
        "follow-up diagnostic ruled out an objective-formula mismatch as the cause. Working "
        "hypothesis: CBL under uniform repair cost is closer to a weighted-completion-time "
        "*scheduling* problem, for which standalone-value sorting is a strong heuristic — a "
        "different problem than the coverage-maximization the submodular greedy provably "
        "solves well. See ADR-020."
    )

    fig2 = go.Figure()
    fig2.add_scatter(x=sweep["heterogeneity"], y=sweep["cbl_cliffs_delta"], mode="lines+markers")
    fig2.add_hline(y=0.147, line_dash="dot", annotation_text="practical-significance floor")
    fig2.add_hline(y=-0.147, line_dash="dot")
    fig2.add_hline(y=0, line_color="black", line_width=1)
    fig2.update_layout(
        xaxis_title="Capability-footprint heterogeneity",
        yaxis_title="Cliff's delta (BLAST vs B9, CBL)",
        height=350,
    )
    st.plotly_chart(fig2, width='stretch')

    st.dataframe(sweep, width='stretch', hide_index=True)
