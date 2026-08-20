import pandas as pd
import yaml
from pathlib import Path


# ======================================================
# BLAST — VALUE MODEL SENSITIVITY SWEEP: OVERLAY GENERATION
# ======================================================
#
# context/03_RESEARCH_DESIGN.md §3.3 (A6 ablation), explicitly
# required by 07_NEXT_PHASE_PLAN.md Step 5a and never built
# this session until now: ">=5 alternative business overlays
# ... including a uniform model as one of the five, so you
# can *show* what uniform weighting does rather than
# accidentally living in it."
#
# online_boutique_v2.yaml (revenue_weighted, declared) is
# model 1 of 5. This script generates the other four,
# reusing its exact capability list and realised_by mapping
# (the STRUCTURE of the overlay is not part of the
# sensitivity question -- only the weights are):
#
#   2. uniform            -- every capability weighted equally
#   3. user_volume        -- weighted by REAL observed baseline
#                             request volume per capability
#                             (data-derived, not declared)
#   4. sla_urgency        -- a declared alternative assumption:
#                             weight by response-urgency instead
#                             of revenue-criticality (payment/auth
#                             -style capabilities up, discovery-
#                             style capabilities down)
#   5. adversarial_inverted -- revenue_weighted's ranking
#                             mechanically reversed, per research
#                             design's own suggested list
# ======================================================

BASE_OVERLAY = "business_overlay/online_boutique_v2.yaml"
JOURNEY_FILE = "results/data/journey_impairment_full.csv"

OUTPUT_DIR = Path("business_overlay/sensitivity_sweep")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def load_base():
    with open(BASE_OVERLAY) as f:
        return yaml.safe_load(f)


def write_overlay(base, value_model, weights, path, note):

    capabilities = []
    for c in base["capabilities"]:
        capabilities.append({
            "id": c["id"],
            "display": c["display"],
            "value_per_min": round(float(weights[c["id"]]), 4),
            "realised_by": c["realised_by"],
        })

    out = {
        "version": 2,
        "system": "online-boutique",
        "value_model": value_model,
        "note": note,
        "capabilities": capabilities,
    }

    with open(path, "w") as f:
        yaml.safe_dump(out, f, sort_keys=False)

    print(f"Wrote {path} ({value_model})")


def main():

    base = load_base()
    cap_ids = [c["id"] for c in base["capabilities"]]
    base_weights = {c["id"]: c["value_per_min"] for c in base["capabilities"]}

    # ------------------------------------------------------
    # 2. Uniform
    # ------------------------------------------------------
    uniform_weights = {cid: 1.0 for cid in cap_ids}
    write_overlay(
        base, "uniform", uniform_weights,
        OUTPUT_DIR / "uniform.yaml",
        "Every capability weighted equally -- the sensitivity sweep's "
        "explicit null model, per 03_RESEARCH_DESIGN.md A6.",
    )

    # ------------------------------------------------------
    # 3. User volume -- DATA-DERIVED, not declared
    # ------------------------------------------------------
    journeys = pd.read_csv(JOURNEY_FILE)
    realised_by = {c["id"]: c["realised_by"] for c in base["capabilities"]}

    volume = {cid: 0 for cid in cap_ids}
    for _, row in journeys.iterrows():
        ops = [o for o in str(row["signature"]).split("+") if o]
        for cid, ops_list in realised_by.items():
            if any(op in ops_list for op in ops):
                volume[cid] += row["n_baseline"]

    # floor at a small epsilon so a capability with zero observed
    # standalone traffic (payment_processing, order_confirmation --
    # see online_boutique_v2.yaml's own "known coverage gaps" note)
    # isn't given a literal zero weight, only a near-zero one.
    max_volume = max(volume.values()) or 1
    volume_weights = {cid: max(1.0, 100.0 * v / max_volume) for cid, v in volume.items()}

    write_overlay(
        base, "user_volume_weighted", volume_weights,
        OUTPUT_DIR / "user_volume_weighted.yaml",
        "Weighted by REAL observed baseline request volume per capability "
        "(summed n_baseline across journey types realising it, "
        "journey_impairment_full.csv), scaled to the same 0-100 range as "
        "the revenue-weighted model. Not declared -- measured. Note the "
        "structural limitation this exposes: payment_processing and "
        "order_confirmation were never observed as independent journey "
        "roots (see online_boutique_v2.yaml), so a pure volume model "
        "floors them near zero despite plausibly being business-critical.",
    )

    # ------------------------------------------------------
    # 4. SLA / urgency -- a second DECLARED alternative
    #    assumption, distinct from revenue-criticality
    # ------------------------------------------------------
    urgency_weights = {
        "payment_processing": 100.0,
        "order_placement": 90.0,
        "cart_management": 40.0,
        "currency_conversion": 35.0,
        "shipping": 30.0,
        "order_confirmation": 20.0,
        "product_browsing": 15.0,
        "product_recommendations": 8.0,
        "advertisement_retrieval": 5.0,
    }
    write_overlay(
        base, "sla_urgency_weighted", urgency_weights,
        OUTPUT_DIR / "sla_urgency_weighted.yaml",
        "A second DECLARED alternative assumption (no real SLA data "
        "exists for this project -- see the requirements matrix's "
        "'SLA Violation Risk: not modeled' entry): weights response "
        "urgency instead of revenue-criticality. Payment/order-placement "
        "capabilities rank highest here for the same reason a real SLA "
        "would (financial-transaction correctness is time-critical), but "
        "browsing/recommendation capabilities rank lower than in the "
        "revenue model, since urgency and revenue-contribution are not "
        "the same axis.",
    )

    # ------------------------------------------------------
    # 5. Adversarial / inverted
    # ------------------------------------------------------
    max_w = max(base_weights.values())
    min_w = min(base_weights.values())
    inverted_weights = {cid: (max_w + min_w - w) for cid, w in base_weights.items()}
    write_overlay(
        base, "adversarial_inverted", inverted_weights,
        OUTPUT_DIR / "adversarial_inverted.yaml",
        "revenue_weighted's ranking mechanically reversed (highest <-> "
        "lowest) -- 03_RESEARCH_DESIGN.md §3.3's suggested 5th model, "
        "a stress test: if BLAST's advantage (where it exists) survives "
        "even under a value model chosen to be maximally wrong, that is "
        "strong evidence the advantage isn't an artifact of the weights.",
    )

    print(f"\n5 value models total: revenue_weighted (existing) + 4 generated here.")


if __name__ == "__main__":
    main()
