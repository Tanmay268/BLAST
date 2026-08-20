import sys
from pathlib import Path

import streamlit as st

# Robust regardless of invocation context (streamlit run adds this
# automatically, but test harnesses / other launchers may not).
sys.path.insert(0, str(Path(__file__).resolve().parent))

from views import (
    render_overview, render_ranker, render_graph,
    render_propagation, render_comparison, render_heterogeneity,
)

st.set_page_config(
    page_title="BLAST — Business-Loss Aware Structural Triage",
    page_icon="🚨",
    layout="wide",
)

st.sidebar.title("BLAST")
st.sidebar.caption("Business-Loss Aware Structural Triage for Microservice Incidents")

VIEWS = {
    "Overview & Findings": render_overview,
    "Ranked Incident Queue": render_ranker,
    "Business Dependency Graph": render_graph,
    "Capability Path Viewer": render_propagation,
    "BLAST vs Baselines": render_comparison,
    "Heterogeneity Sweep": render_heterogeneity,
}

choice = st.sidebar.radio("View", list(VIEWS.keys()))

st.sidebar.divider()
st.sidebar.caption(
    "Deliberately thin (ADR-008) — a results explorer and live-ranking demo, "
    "not a production tool. Full methodology in `context/`."
)
st.sidebar.markdown("[GitHub repo](https://github.com/Tanmay268/BLAST)")

VIEWS[choice]()
