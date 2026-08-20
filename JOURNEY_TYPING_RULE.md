# Journey-typing rule

Written after `build_journey_impairment.py`, Step 2 of `context/07_NEXT_PHASE_PLAN.md`.
Basis for ADR-014 / ADR-015.

## The rule

A journey is one trace, identified by its root span (`parentSpanID` is null).

1. **Infrastructure noise is dropped.** Root operations matching `Health/Check` (gRPC
   health probes) or `TraceService/Export` (OTel telemetry export) are not journeys.
   Verified: every such root is the sole span in its trace (no fan-out), confirming
   they are not truncated/incomplete user requests.

2. **Journey type is keyed on the root's direct-children operation signature, never
   on serviceName.** Online Boutique's `frontendservice` wraps every page view and
   user action in one generic root span literally named `"frontend"` — 19,119 of
   24,810 root spans (77%) in this pilot. Keying journey type on that root
   `operationName` directly would collapse every journey into one type, reproducing
   the saturation bug in a new form.

   The plan's original fallback was "the deepest distinguishing operation in the
   trace." Inspection of an actual `"frontend"`-rooted trace showed this doesn't
   apply here: the frontend issues a **fan-out** of parallel backend calls per page
   (e.g. the home page calls `ListProducts` + `GetAds` + `GetCart` + `Convert` all
   as direct children of the root), not a single child that identifies the request.
   There is no one "deepest" operation to pick.

   The rule is generalised accordingly: for a `"frontend"`-rooted trace, journey
   type = the sorted, deduplicated set of `methodName` values among the root span's
   **direct children**. Empirically (verified stable across a `delay` case and a
   `cpu` case) this recovers exactly five real Online Boutique request types:

   | Signature | Label | Volume (6-case pilot) |
   |---|---|---|
   | `Convert+GetAds+GetCart+GetProduct+GetSupportedCurrencies+ListRecommendations` | Product Detail View | 47,553 |
   | `Convert+GetCart+GetProduct+GetQuote+GetSupportedCurrencies+ListRecommendations` | Cart View | 21,912 |
   | `AddItem+GetProduct` | Add To Cart | 11,052 |
   | `Convert+GetAds+GetCart+GetSupportedCurrencies+ListProducts` | Home Page View | 10,853 |
   | `GetProduct+GetSupportedCurrencies+ListRecommendations+PlaceOrder` | Place Order | 3,664 |

   A long tail of rare/singleton signatures also appears (see
   `journey_signature_catalog.csv`). These are kept as their own journey types
   rather than merged, and naturally fail the minimum-sample-size gate
   (`MIN_JOURNEY_SAMPLES = 10`) for significance testing.

3. **Orphaned direct-RPC roots are kept separate, not merged.** ~2,400 traces per
   case are rooted directly at `checkoutservice` issuing
   `hipstershop.CurrencyService/Convert` as its *own* root span — a two-span trace
   (`checkoutservice -> currencyservice`) with no parent context. This is a broken
   trace-context-propagation artifact in the checkout flow's currency-conversion
   call (the call is really part of `PlaceOrder`, but the tracing instrumentation
   loses the parent span ID for it). It is labelled `orphaned::...` and treated as
   its own journey type rather than folded into `Place Order`, since that folding
   would be an unverified assumption about which user request it belongs to.

## Why this prevents the amplifier bug from recurring

The old service-level attribution (`build_business_capabilities.py`) mapped an
operation to a business capability, then attributed that mapping to whichever
service's `serviceName` the span happened to carry. Because `checkoutservice` is
both the fault-injection target *and* the caller for most of the checkout flow's
downstream RPCs, being flagged "impaired" (correctly, since it's the fault target)
pulled in capability mappings for every operation it happens to call, regardless of
whether that specific downstream call was actually affected.

Journey typing removes the service as the unit of attribution entirely. A checkout
fault degrades the `Place Order` journey (and the orphaned currency-conversion
journey it's entangled with) because those journeys' own end-to-end durations are
measurably slower — not because some unrelated service was globally flagged
impaired. `Home Page View`, `Cart View`, `Add To Cart`, and (mostly) `Product
Detail View` are correctly left unimpaired across all six pilot cases.

## A limitation this surfaces, not hides

`cpu_3` shows `Product Detail View` as statistically impaired (Holm-corrected
p ≈ 3.6e-34) but with a small practical effect (Cliff's delta = 0.152, just past
the "small" threshold of 0.147). This is very likely a large-N statistical-
significance artifact rather than a real effect — `Product Detail View`'s
constituent calls (`GetAds`, `GetCart`, `GetProduct`, `Convert`,
`ListRecommendations`) don't route through `checkoutservice` at all. It survives
the practical-effect-size gate by a small margin and should be flagged as a
threat-to-validity footnote rather than treated as a genuine cross-capability
propagation finding.

## Files produced

- `journey_impairment.csv` — one row per (case, journey_type): counts, latency
  percentiles, failure/degraded rates, significance test results, `impaired`.
- `journey_signature_catalog.csv` — every distinct direct-children signature
  observed, with trace counts, for audit.
