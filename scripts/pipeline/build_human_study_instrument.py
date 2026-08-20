import json
import random

import pandas as pd
import yaml


# ======================================================
# BLAST — HUMAN VALIDATION STUDY INSTRUMENT (RQ5)
# ======================================================
#
# context/03_RESEARCH_DESIGN.md §3.4. This script generates
# the actual materials -- it does NOT and cannot collect
# real responses, since that requires recruiting real SREs
# (10-20 people, possibly IRB approval), which is outside
# what can be executed autonomously. What it CAN do: build
# a ready-to-deploy instrument grounded in REAL corpus data
# (never invented incidents), so running the study is a
# recruitment problem, not also a materials-design problem.
#
# 12 scenarios (research design's 10-15 range), each with 5
# concurrent incidents (matching "5 concurrent incidents
# with realistic descriptions"), sampled from the REAL
# k=5 test scenarios already used for the Gate 4 evaluation
# -- so a human's judgement is checkable against the exact
# same measured ground truth and BLAST/baseline orderings
# already computed, not a separate invented dataset.
# ======================================================

SCENARIOS_FILE = "results/data/ground_truth_scenarios.json"
OVERLAY_FILE = "business_overlay/online_boutique_v2.yaml"
JOURNEY_FILE = "results/data/journey_impairment_full.csv"

OUTPUT_FILE = "results/data/human_study_instrument.md"

N_SCENARIOS = 12
SEED = 20260820

FAULT_TYPE_DESCRIPTIONS = {
    "cpu": "is running at sustained high CPU usage",
    "delay": "is responding with added network delay on its calls",
    "disk": "is experiencing disk I/O contention",
    "loss": "is dropping a fraction of its network packets",
    "mem": "is under memory pressure",
    "socket": "has exhausted available network sockets",
}


def load_overlay():
    with open(OVERLAY_FILE) as f:
        overlay = yaml.safe_load(f)
    return {c["id"]: c["display"] for c in overlay["capabilities"]}


def describe_incident(letter, case_id, incident_type, journeys, capability_display):

    service, fault_type = incident_type.split("::")

    case_journeys = journeys[
        (journeys["target_service"] == service) & (journeys["fault_type"] == fault_type)
    ]
    impaired = case_journeys[case_journeys["impaired"]]

    fault_desc = FAULT_TYPE_DESCRIPTIONS.get(fault_type, f"has a '{fault_type}' fault")

    if impaired.empty:
        symptom = "No user-facing journey showed a statistically significant slowdown or failure."
        capabilities_hit = []
    else:
        worst = impaired.sort_values("impairment_magnitude", ascending=False).iloc[0]
        symptom = (
            f"The '{worst['journey_label']}' user journey is measurably degraded "
            f"(95th-percentile latency {worst['p95_ratio']:.1f}x normal)."
        )
        realised_by = load_overlay_realised_by()
        touched = set()
        for _, row in impaired.iterrows():
            ops = [o for o in str(row["signature"]).split("+") if o]
            for cid, ops_list in realised_by.items():
                if any(op in ops_list for op in ops):
                    touched.add(cid)
        capabilities_hit = sorted(capability_display[c] for c in touched)

    return {
        "letter": letter,
        "case_id": case_id,
        "service": service,
        "fault_type": fault_type,
        "description": f"Service **{service}** {fault_desc}. {symptom}",
        "capabilities": capabilities_hit,
    }


def load_overlay_realised_by():
    with open(OVERLAY_FILE) as f:
        overlay = yaml.safe_load(f)
    return {c["id"]: c["realised_by"] for c in overlay["capabilities"]}


def main():

    with open(SCENARIOS_FILE) as f:
        scenarios = json.load(f)

    journeys = pd.read_csv(JOURNEY_FILE)
    capability_display = load_overlay()

    k5_scenarios = [s for s in scenarios if s["k"] == 5]

    rng = random.Random(SEED)
    chosen = rng.sample(k5_scenarios, min(N_SCENARIOS, len(k5_scenarios)))

    lines = []

    lines.append("# BLAST Human Validation Study — Instrument\n")
    lines.append(
        "Generated from real RE2-OB corpus data "
        f"({N_SCENARIOS} scenarios, seed={SEED}). This is a ready-to-run instrument, not "
        "collected responses — running the study requires recruiting 10-20 participants "
        "with production on-call/SRE experience "
        "(context/03_RESEARCH_DESIGN.md §3.4) and, depending on your institution, ethics "
        "approval. Check that requirement in week 1 of running this — it can take 4-8 weeks "
        "and will silently block the study if left late.\n"
    )

    lines.append("## Consent / instructions text (read to every participant)\n")
    lines.append(
        "> You are being asked to review a series of scenarios from a research study on "
        "incident prioritization in microservice systems. Each scenario describes 5 "
        "concurrent incidents in an e-commerce application (Online Boutique). For each "
        "scenario, rank the 5 incidents from \"fix first\" to \"fix last\", based on your "
        "professional judgement of business impact. There are no right or wrong answers — "
        "we are interested in how experienced engineers reason about this. Your responses "
        "are anonymous. Participation is voluntary and you may stop at any time. This "
        "should take approximately 20-30 minutes.\n"
    )

    lines.append("## System context (show once, before the first scenario)\n")
    lines.append(
        "Online Boutique is an e-commerce demo application. Users browse products, view "
        "recommendations and ads, manage a cart, check out, and receive order confirmations. "
        "The following 9 business capabilities are relevant across all scenarios: "
        + ", ".join(sorted(capability_display.values())) + ".\n"
    )

    for idx, sc in enumerate(chosen, start=1):

        lines.append(f"---\n\n## Scenario {idx} (k={sc['k']})\n")
        lines.append(
            "Five incidents are currently open. You have one engineer available. "
            "Rank them 1 (fix first) through 5 (fix last).\n"
        )

        letters = "ABCDE"
        incident_descs = []
        for letter, case_id, itype in zip(letters, sc["incident_ids"], sc["incident_types"]):
            desc = describe_incident(letter, case_id, itype, journeys, capability_display)
            incident_descs.append(desc)

        for d in incident_descs:
            caps = ", ".join(d["capabilities"]) if d["capabilities"] else "none identified"
            lines.append(f"**Incident {d['letter']}.** {d['description']}  \n"
                          f"*Capabilities touched: {caps}*\n")

        lines.append(
            "\n**Your ranking (fix-first to fix-last):** ___, ___, ___, ___, ___\n"
        )
        lines.append(
            "*[Internal — do not show participant before they answer] "
            f"scenario_id={sc['scenario_id']}, case letters map to case IDs in order "
            + ", ".join(f"{d['letter']}={d['case_id']}" for d in incident_descs) + "*\n"
        )

    lines.append("---\n\n## Post-scenario questions (ask after ALL scenarios)\n")
    lines.append(
        "1. For each scenario, you will be shown BLAST's computed ordering and a severity-"
        "based baseline's ordering, in randomised order and unlabelled (blind A/B). "
        "Which do you agree with more?\n"
        "2. On a 5-point scale (1=not at all useful, 5=very useful), how useful would a "
        "written explanation of *why* an incident was ranked where it was be to your work?\n"
        "3. Free text: for any scenario where your ranking disagreed sharply with either "
        "ordering, what would you want the tool to have known that it apparently didn't?\n"
    )

    lines.append("## Analysis plan (once responses exist)\n")
    lines.append(
        "- Inter-rater agreement: Kendall's W across participants per scenario.\n"
        "- Expert-consensus ranking (median rank per incident) as a second, independent "
        "ground truth.\n"
        "- Kendall's τ between BLAST's ranking, the baseline's ranking, and the expert-"
        "consensus ranking — reuses `kendalls_tau()` in `scripts/pipeline/blast_eval_lib.py`, "
        "already implemented.\n"
        "- Report the blind-agreement rate (question 1) and Likert scores (question 2) "
        "directly, with free-text responses (question 3) analysed thematically for the "
        "discussion section.\n"
    )

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"Generated {len(chosen)} scenarios into {OUTPUT_FILE}")
    print("\nThis is the instrument only. Running the actual study requires recruiting "
          "real participants -- see context/03_RESEARCH_DESIGN.md §3.4 for the recruitment "
          "channels already identified (university alumni in SRE roles, LinkedIn outreach, "
          "r/devops, r/sre, DevOps Discord/Slack communities).")


if __name__ == "__main__":
    main()
