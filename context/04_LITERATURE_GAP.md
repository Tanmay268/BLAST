# 04 — Literature Map & Gap Analysis

**Project:** BLAST — Business-Loss Aware Structural Triage for Microservice Incidents
**Status:** Living document. Update at every literature pass.
**Owner:** Tanmay
**Last updated:** 2026-08-17

> ⚠️ **Citation discipline.** Every entry below is tagged with a confidence marker.
> `[VERIFIED]` = I confirmed venue/year in this session.
> `[VERIFY]` = I am recalling this from training and you **must** confirm venue, year, and authors on DBLP or Google Scholar before it enters the paper.
> Do not copy a `[VERIFY]` citation into a submission unchecked. Reviewers catch this and it costs credibility.

---

## 1. Why this section decides whether the project is publishable

Your project document asserts a gap ("existing systems don't answer *which incident to fix first*"). Reviewers will not take that on trust. The single most common rejection reason for AIOps papers from student authors is **an unconvincing related-work section that fails to distinguish the contribution from adjacent published work.**

So this document does three things:
1. Establishes what the field *has* solved (so we don't claim it).
2. Establishes what it has *not* solved (the gap).
3. States precisely what makes BLAST different, in a form you can paste into the paper's Section 2.

---

## 2. The four research territories

The literature splits into four clusters. Your contribution lives in cluster **D**, and clusters A–C are *upstream inputs* you consume rather than compete with.

### Cluster A — Anomaly Detection (AD)

Detects that something is wrong. Time-series and multimodal models over metrics/logs/traces.

| Work | Venue/Year | What it does | Relation to us |
|---|---|---|---|
| Eadro | ICSE 2023 `[VERIFY]` | End-to-end anomaly detection + RCA on multi-source data for microservices | **Upstream.** Produces incident candidates we consume. |
| DiagFusion | TSE 2023 `[VERIFY]` | Multimodal failure diagnosis fusing metrics/logs/traces via embeddings | **Upstream.** |
| Various deep AD (LSTM/VAE/GNN-AD) | 2019–2025 | Detect anomalous service behaviour | **Upstream.** |

**Do not compete here.** Your project document is explicit that another anomaly detector is not the contribution. Agreed — this space is saturated and marginal gains are unpublishable at good venues.

### Cluster B — Root Cause Localization (RCL)

Given an anomaly, find *which* service/metric caused it. This is the most crowded space in microservice AIOps.

| Work | Venue/Year | What it does | Relation to us |
|---|---|---|---|
| MicroRank | WWW 2021 `[VERIFY]` | PageRank-style spectrum analysis over traces to rank root-cause candidates | **Closest methodological cousin.** Uses graph ranking — but ranks *causes*, not *business consequences*. Must be discussed explicitly. |
| Groot | ASE 2021 `[VERIFY]` | Event-graph-based RCA deployed at eBay | **Upstream + comparison point** for graph construction. |
| Sage | ASPLOS 2021 `[VERIFY]` | Causal Bayesian network for root cause of QoS violations | **Upstream.** Causal graph, not business graph. |
| Nezha | FSE 2023 `[VERIFY]` | Interpretable multimodal RCA via pattern comparison | **Upstream.** |
| DynaCausal | 2025, arXiv `[VERIFIED — exists]` | Dynamic causality-aware RCA for distributed microservices | Recent; cite as current state of RCL. |
| TrioXpert | 2025 `[VERIFY]` | Named in your project doc; confirm it is a real, citable, peer-reviewed work before citing | Your doc names it as a baseline — **verify it exists and is citable.** |
| ART | 2025 `[VERIFY]` | Named in your project doc; same caveat | Same caveat. |

> 🚩 **Action item — do this in week 1.** Your project document lists TrioXpert and ART as baselines. I could not confirm either as established, peer-reviewed, publicly-available systems in this session. If they have no public implementation, **you cannot use them as baselines** — you'd be reporting numbers you can't reproduce. Confirm: (a) they exist, (b) code is released, (c) they solve *prioritization* not *localization*. If any answer is no, drop them and say so in the paper.

### Cluster C — Alert Management (aggregation, deduplication, severity)

This is the cluster **closest to your work** and the one most likely to be used against you in review.

| Work | Venue/Year | What it does | **Why it is not us** |
|---|---|---|---|
| AlertRank | ISSRE 2020 `[VERIFIED — paper exists]` | Identifies *severe* alerts automatically and adaptively using textual + monetary + temporal features, XGBoost-based | **The critical prior work.** It scores alerts individually with flat features. It has **no dependency graph, no propagation model, and treats alerts as independent.** Our contribution is precisely the structural + set-level reasoning it lacks. |
| Alert prioritisation in SOCs — systematic survey | ACM Computing Surveys 2024 `[VERIFIED]` | Surveys criteria and methods for alert prioritisation in security operations | Establishes that prioritisation is a recognised research problem. **Security domain**, not microservice reliability — a useful adjacent framing to cite, and a place where "impact-aware" ideas already exist that we must not re-invent. |
| Survey on intelligent alert/incident management in IT services | JNCA 2024 (vol. 224, 103842) `[VERIFIED]` | Comprehensive survey of alert & incident management | **Use this as your framing citation** for "the field organises itself as AD → RCA → mitigation, with prioritisation under-served." |
| Chain-of-Event | 2024 `[VERIFY]` | Interpretable RCA via learned weighted event causal graph | Learned edge weights on a causal graph — **methodologically adjacent to our learned transmission probabilities.** Must be distinguished carefully. |

### Cluster D — Business-impact-aware prioritization ← **our territory**

Findings from this session's searches:
- Substantial **practitioner** material exists (ITIL priority matrices, PagerDuty/ServiceNow policies, service-criticality frameworks). All are **static, manually-configured rule matrices**. This is your straw-man baseline and it is a fair one — it is what industry actually does.
- **No academic work found** that ranks a *set of concurrent* microservice incidents by *predicted downstream business consequence* using a learned failure-propagation model over a business-capability graph.
- The mathematical machinery we intend to borrow is mature and well-cited but lives in a **different field** (social network analysis):
  - Kempe, Kleinberg & Tardos, *Maximizing the Spread of Influence through a Social Network*, KDD 2003 `[VERIFIED]` — independent cascade model, submodularity of influence spread, greedy (1−1/e) guarantee.
  - Nemhauser, Wolsey & Fisher 1978 `[VERIFY]` — the (1−1/e) greedy bound for monotone submodular maximization.
  - Krause & Golovin, *Submodular Function Maximization* survey `[VERIFIED]` — standard reference.
  - Chen et al., *Scalable Influence Maximization under the Linear Threshold Model* `[VERIFIED]` — scalability techniques if graphs grow.

---

## 3. The gap, stated precisely

> Existing microservice reliability research answers **"what broke and where?"** Existing alert-management research answers **"is this one alert severe?"** Neither answers **"given N incidents open right now and one on-call engineer, what is the optimal order to fix them so as to minimise total business loss?"**
>
> Three specific sub-gaps:
>
> **G1 — Structure is ignored in prioritization.** Severity models (AlertRank and industry rule matrices) score each incident from local features. They cannot express "this incident looks mild but sits upstream of checkout."
>
> **G2 — Topological importance is not failure importance.** Where graph structure *is* used (MicroRank, Groot), it is used for *cause* attribution, and importance is topological (PageRank/centrality). Topological centrality assumes failure flows along every edge equally. Real systems have retries, timeouts, circuit breakers, cache fallbacks and async queues — **some edges transmit failure and some absorb it.** No existing work learns per-edge failure-transmission propensity for the purpose of impact estimation.
>
> **G3 — Incidents are scored independently, but they are not independent.** If incident A and incident B both take down the checkout capability, the business loss of the *set* {A,B} is far less than loss(A) + loss(B), because fixing either one restores checkout. Every existing prioritization method double-counts this overlap. **Prioritization is a set-selection problem, not a scoring problem** — and to our knowledge nobody in AIOps has framed it that way.
>
> G3 is the sharpest and most defensible of the three.

---

## 4. Positioning statement (paste-ready for Section 2 of the paper)

> Prior work in microservice reliability has largely targeted detection and diagnosis. Anomaly detectors (Eadro, DiagFusion) identify that a failure occurred; root-cause localizers (MicroRank, Groot, Sage, Nezha) identify where it originated. Both produce *incident candidates* and stop there. Alert-management work such as AlertRank addresses severity but scores each alert from local, unstructured features, without a dependency model. Industrial practice (ITIL priority matrices, PagerDuty escalation policies) relies on statically-configured severity tiers.
>
> BLAST is positioned strictly downstream of detection and diagnosis. It takes incident candidates as input and addresses an orthogonal question: the *order* in which they should be resolved to minimise business loss. It differs from prior art in three respects. First, it estimates impact by propagation over a heterogeneous business-dependency graph rather than from local features. Second, it learns per-edge failure-transmission probabilities from telemetry rather than assuming uniform topological influence. Third, it formulates prioritization as **stochastic submodular coverage of business capabilities**, which correctly handles overlapping blast radii among concurrent incidents and admits a (1−1/e) approximation guarantee — a property no existing prioritization method provides.

---

## 5. Papers you must read (ordered, week 1–3)

**Tier 1 — read fully, you will cite all of these**
1. JNCA 2024 survey on alert & incident management — your framing.
2. AlertRank (ISSRE 2020) — your closest competitor; know its features and its evaluation cold.
3. RCAEval (WWW 2025 / FSE 2026) — your data source and evaluation norms.
4. Kempe, Kleinberg & Tardos (KDD 2003) — your theoretical backbone.
5. ACM CSUR 2024 alert-prioritisation survey — proves prioritisation is a real research problem.

**Tier 2 — read method sections, cite as related**
6. MicroRank (WWW 2021) — graph ranking for RCA.
7. Groot (ASE 2021) — industrial graph construction.
8. Eadro (ICSE 2023), DiagFusion (TSE 2023) — upstream modules.
9. Comprehensive RCA survey (arXiv 2408.00803) — taxonomy.

**Tier 3 — skim, cite if relevant**
10. Sage, Nezha, DynaCausal, Chain-of-Event.
11. Krause & Golovin submodularity survey.

**Reading protocol.** For each Tier 1/2 paper record, in a shared BibTeX + notes file: problem solved, inputs, outputs, evaluation dataset, metrics, and **one sentence on why it does not solve your problem.** That last sentence is literally your related-work paragraph.

---

## 6. Standing risk: someone publishes this first

AIOps moves fast. Set a monthly arXiv alert for: `microservice incident prioritization`, `business impact AIOps`, `alert ranking dependency graph`, `blast radius estimation`. If a close paper appears, the response is to sharpen the differentiator (usually the submodular set formulation, which is the hardest to independently arrive at), not to abandon.

---

## Sources consulted this session

- [RCAEval: A Benchmark for Root Cause Analysis of Microservice Systems with Telemetry Data](https://arxiv.org/html/2412.17015v5)
- [RCAEval GitHub](https://github.com/phamquiluan/RCAEval)
- [AlertRank: Automatically and Adaptively Identifying Severe Alerts](https://netman.aiops.org/wp-content/uploads/2020/07/alertrank_camera-ready.pdf)
- [A survey on intelligent management of alerts and incidents in IT services (JNCA 2024)](https://netman.aiops.org/wp-content/uploads/2024/08/A-survey-on-intelligent-management-of-alerts-and-incidents-in-IT-services.pdf)
- [Alert Prioritisation in Security Operations Centres: A Systematic Survey (ACM CSUR)](https://dl.acm.org/doi/10.1145/3695462)
- [AIOps Solutions for Incident Management: Literature Review](https://arxiv.org/html/2404.01363v1)
- [A Comprehensive Survey on Root Cause Analysis in (Micro) Services](https://arxiv.org/html/2408.00803v1)
- [Maximizing the Spread of Influence through a Social Network (KDD 2003)](https://www.cs.cornell.edu/home/kleinber/kdd03-inf.pdf)
- [Submodular Function Maximization (Krause & Golovin)](https://viterbi-web.usc.edu/~shanghua/teaching/Fall2025-670/krause12survey.pdf)
- [DynaCausal: Dynamic Causality-Aware Root Cause Analysis](https://arxiv.org/html/2510.22613v1)
