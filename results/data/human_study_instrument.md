# BLAST Human Validation Study — Instrument

Generated from real RE2-OB corpus data (12 scenarios, seed=20260820). This is a ready-to-run instrument, not collected responses — running the study requires recruiting 10-20 participants with production on-call/SRE experience (context/03_RESEARCH_DESIGN.md §3.4) and, depending on your institution, ethics approval. Check that requirement in week 1 of running this — it can take 4-8 weeks and will silently block the study if left late.

## Consent / instructions text (read to every participant)

> You are being asked to review a series of scenarios from a research study on incident prioritization in microservice systems. Each scenario describes 5 concurrent incidents in an e-commerce application (Online Boutique). For each scenario, rank the 5 incidents from "fix first" to "fix last", based on your professional judgement of business impact. There are no right or wrong answers — we are interested in how experienced engineers reason about this. Your responses are anonymous. Participation is voluntary and you may stop at any time. This should take approximately 20-30 minutes.

## System context (show once, before the first scenario)

Online Boutique is an e-commerce demo application. Users browse products, view recommendations and ads, manage a cart, check out, and receive order confirmations. The following 9 business capabilities are relevant across all scenarios: Advertisement Retrieval, Cart Management, Currency Conversion, Order Confirmation, Order Placement, Payment Processing, Product Browsing, Product Recommendations, Shipping.

---

## Scenario 1 (k=5)

Five incidents are currently open. You have one engineer available. Rank them 1 (fix first) through 5 (fix last).

**Incident A.** Service **currencyservice** is responding with added network delay on its calls. The 'Place Order' user journey is measurably degraded (95th-percentile latency 15.5x normal).  
*Capabilities touched: Advertisement Retrieval, Cart Management, Currency Conversion, Order Placement, Product Browsing, Product Recommendations, Shipping*

**Incident B.** Service **emailservice** is experiencing disk I/O contention. The 'Place Order' user journey is measurably degraded (95th-percentile latency 1.1x normal).  
*Capabilities touched: Currency Conversion, Order Placement, Product Browsing, Product Recommendations*

**Incident C.** Service **emailservice** is dropping a fraction of its network packets. The 'Place Order' user journey is measurably degraded (95th-percentile latency 1.9x normal).  
*Capabilities touched: Currency Conversion, Order Placement, Product Browsing, Product Recommendations*

**Incident D.** Service **recommendationservice** is responding with added network delay on its calls. The 'Cart View' user journey is measurably degraded (95th-percentile latency 3.1x normal).  
*Capabilities touched: Advertisement Retrieval, Cart Management, Currency Conversion, Order Placement, Product Browsing, Product Recommendations, Shipping*

**Incident E.** Service **recommendationservice** is under memory pressure. The 'Product Detail View' user journey is measurably degraded (95th-percentile latency 15.9x normal).  
*Capabilities touched: Advertisement Retrieval, Cart Management, Currency Conversion, Order Placement, Product Browsing, Product Recommendations, Shipping*


**Your ranking (fix-first to fix-last):** ___, ___, ___, ___, ___

*[Internal — do not show participant before they answer] scenario_id=scenario_k5_030, case letters map to case IDs in order A=re2ob_currencyservice_delay_2, B=re2ob_emailservice_disk_2, C=re2ob_emailservice_loss_3, D=re2ob_recommendationservice_delay_2, E=re2ob_recommendationservice_mem_2*

---

## Scenario 2 (k=5)

Five incidents are currently open. You have one engineer available. Rank them 1 (fix first) through 5 (fix last).

**Incident A.** Service **checkoutservice** has exhausted available network sockets. The 'Place Order' user journey is measurably degraded (95th-percentile latency 2.1x normal).  
*Capabilities touched: Currency Conversion, Order Placement, Product Browsing, Product Recommendations*

**Incident B.** Service **currencyservice** is responding with added network delay on its calls. The 'Place Order' user journey is measurably degraded (95th-percentile latency 15.5x normal).  
*Capabilities touched: Advertisement Retrieval, Cart Management, Currency Conversion, Order Placement, Product Browsing, Product Recommendations, Shipping*

**Incident C.** Service **emailservice** is experiencing disk I/O contention. The 'Place Order' user journey is measurably degraded (95th-percentile latency 1.1x normal).  
*Capabilities touched: Currency Conversion, Order Placement, Product Browsing, Product Recommendations*

**Incident D.** Service **productcatalogservice** has exhausted available network sockets. The 'Cart View' user journey is measurably degraded (95th-percentile latency 3.9x normal).  
*Capabilities touched: Advertisement Retrieval, Cart Management, Currency Conversion, Order Placement, Product Browsing, Product Recommendations, Shipping*

**Incident E.** Service **recommendationservice** is under memory pressure. The 'Product Detail View' user journey is measurably degraded (95th-percentile latency 15.9x normal).  
*Capabilities touched: Advertisement Retrieval, Cart Management, Currency Conversion, Order Placement, Product Browsing, Product Recommendations, Shipping*


**Your ranking (fix-first to fix-last):** ___, ___, ___, ___, ___

*[Internal — do not show participant before they answer] scenario_id=scenario_k5_016, case letters map to case IDs in order A=re2ob_checkoutservice_socket_3, B=re2ob_currencyservice_delay_2, C=re2ob_emailservice_disk_1, D=re2ob_productcatalogservice_socket_3, E=re2ob_recommendationservice_mem_2*

---

## Scenario 3 (k=5)

Five incidents are currently open. You have one engineer available. Rank them 1 (fix first) through 5 (fix last).

**Incident A.** Service **currencyservice** is responding with added network delay on its calls. The 'Place Order' user journey is measurably degraded (95th-percentile latency 15.5x normal).  
*Capabilities touched: Advertisement Retrieval, Cart Management, Currency Conversion, Order Placement, Product Browsing, Product Recommendations, Shipping*

**Incident B.** Service **productcatalogservice** is running at sustained high CPU usage. The 'Product Detail View' user journey is measurably degraded (95th-percentile latency 3.1x normal).  
*Capabilities touched: Advertisement Retrieval, Cart Management, Currency Conversion, Order Placement, Product Browsing, Product Recommendations, Shipping*

**Incident C.** Service **productcatalogservice** has exhausted available network sockets. The 'Cart View' user journey is measurably degraded (95th-percentile latency 3.9x normal).  
*Capabilities touched: Advertisement Retrieval, Cart Management, Currency Conversion, Order Placement, Product Browsing, Product Recommendations, Shipping*

**Incident D.** Service **recommendationservice** is responding with added network delay on its calls. The 'Cart View' user journey is measurably degraded (95th-percentile latency 3.1x normal).  
*Capabilities touched: Advertisement Retrieval, Cart Management, Currency Conversion, Order Placement, Product Browsing, Product Recommendations, Shipping*

**Incident E.** Service **recommendationservice** is under memory pressure. The 'Product Detail View' user journey is measurably degraded (95th-percentile latency 15.9x normal).  
*Capabilities touched: Advertisement Retrieval, Cart Management, Currency Conversion, Order Placement, Product Browsing, Product Recommendations, Shipping*


**Your ranking (fix-first to fix-last):** ___, ___, ___, ___, ___

*[Internal — do not show participant before they answer] scenario_id=scenario_k5_019, case letters map to case IDs in order A=re2ob_currencyservice_delay_2, B=re2ob_productcatalogservice_cpu_1, C=re2ob_productcatalogservice_socket_1, D=re2ob_recommendationservice_delay_2, E=re2ob_recommendationservice_mem_3*

---

## Scenario 4 (k=5)

Five incidents are currently open. You have one engineer available. Rank them 1 (fix first) through 5 (fix last).

**Incident A.** Service **emailservice** is experiencing disk I/O contention. The 'Place Order' user journey is measurably degraded (95th-percentile latency 1.1x normal).  
*Capabilities touched: Currency Conversion, Order Placement, Product Browsing, Product Recommendations*

**Incident B.** Service **emailservice** is dropping a fraction of its network packets. The 'Place Order' user journey is measurably degraded (95th-percentile latency 1.9x normal).  
*Capabilities touched: Currency Conversion, Order Placement, Product Browsing, Product Recommendations*

**Incident C.** Service **productcatalogservice** is running at sustained high CPU usage. The 'Product Detail View' user journey is measurably degraded (95th-percentile latency 3.1x normal).  
*Capabilities touched: Advertisement Retrieval, Cart Management, Currency Conversion, Order Placement, Product Browsing, Product Recommendations, Shipping*

**Incident D.** Service **recommendationservice** is responding with added network delay on its calls. The 'Cart View' user journey is measurably degraded (95th-percentile latency 3.1x normal).  
*Capabilities touched: Advertisement Retrieval, Cart Management, Currency Conversion, Order Placement, Product Browsing, Product Recommendations, Shipping*

**Incident E.** Service **recommendationservice** is under memory pressure. The 'Product Detail View' user journey is measurably degraded (95th-percentile latency 15.9x normal).  
*Capabilities touched: Advertisement Retrieval, Cart Management, Currency Conversion, Order Placement, Product Browsing, Product Recommendations, Shipping*


**Your ranking (fix-first to fix-last):** ___, ___, ___, ___, ___

*[Internal — do not show participant before they answer] scenario_id=scenario_k5_022, case letters map to case IDs in order A=re2ob_emailservice_disk_2, B=re2ob_emailservice_loss_2, C=re2ob_productcatalogservice_cpu_1, D=re2ob_recommendationservice_delay_1, E=re2ob_recommendationservice_mem_1*

---

## Scenario 5 (k=5)

Five incidents are currently open. You have one engineer available. Rank them 1 (fix first) through 5 (fix last).

**Incident A.** Service **currencyservice** is running at sustained high CPU usage. The 'Home Page View' user journey is measurably degraded (95th-percentile latency 2.7x normal).  
*Capabilities touched: Advertisement Retrieval, Cart Management, Currency Conversion, Order Placement, Product Browsing, Product Recommendations, Shipping*

**Incident B.** Service **currencyservice** is responding with added network delay on its calls. The 'Place Order' user journey is measurably degraded (95th-percentile latency 15.5x normal).  
*Capabilities touched: Advertisement Retrieval, Cart Management, Currency Conversion, Order Placement, Product Browsing, Product Recommendations, Shipping*

**Incident C.** Service **productcatalogservice** has exhausted available network sockets. The 'Cart View' user journey is measurably degraded (95th-percentile latency 3.9x normal).  
*Capabilities touched: Advertisement Retrieval, Cart Management, Currency Conversion, Order Placement, Product Browsing, Product Recommendations, Shipping*

**Incident D.** Service **recommendationservice** is responding with added network delay on its calls. The 'Cart View' user journey is measurably degraded (95th-percentile latency 3.1x normal).  
*Capabilities touched: Advertisement Retrieval, Cart Management, Currency Conversion, Order Placement, Product Browsing, Product Recommendations, Shipping*

**Incident E.** Service **recommendationservice** is under memory pressure. The 'Product Detail View' user journey is measurably degraded (95th-percentile latency 15.9x normal).  
*Capabilities touched: Advertisement Retrieval, Cart Management, Currency Conversion, Order Placement, Product Browsing, Product Recommendations, Shipping*


**Your ranking (fix-first to fix-last):** ___, ___, ___, ___, ___

*[Internal — do not show participant before they answer] scenario_id=scenario_k5_008, case letters map to case IDs in order A=re2ob_currencyservice_cpu_2, B=re2ob_currencyservice_delay_1, C=re2ob_productcatalogservice_socket_3, D=re2ob_recommendationservice_delay_3, E=re2ob_recommendationservice_mem_2*

---

## Scenario 6 (k=5)

Five incidents are currently open. You have one engineer available. Rank them 1 (fix first) through 5 (fix last).

**Incident A.** Service **checkoutservice** is running at sustained high CPU usage. The 'Place Order' user journey is measurably degraded (95th-percentile latency 2.1x normal).  
*Capabilities touched: Advertisement Retrieval, Cart Management, Currency Conversion, Order Placement, Product Browsing, Product Recommendations*

**Incident B.** Service **checkoutservice** has exhausted available network sockets. The 'Place Order' user journey is measurably degraded (95th-percentile latency 2.1x normal).  
*Capabilities touched: Currency Conversion, Order Placement, Product Browsing, Product Recommendations*

**Incident C.** Service **emailservice** is dropping a fraction of its network packets. The 'Place Order' user journey is measurably degraded (95th-percentile latency 1.9x normal).  
*Capabilities touched: Currency Conversion, Order Placement, Product Browsing, Product Recommendations*

**Incident D.** Service **recommendationservice** is responding with added network delay on its calls. The 'Cart View' user journey is measurably degraded (95th-percentile latency 3.1x normal).  
*Capabilities touched: Advertisement Retrieval, Cart Management, Currency Conversion, Order Placement, Product Browsing, Product Recommendations, Shipping*

**Incident E.** Service **recommendationservice** is under memory pressure. The 'Product Detail View' user journey is measurably degraded (95th-percentile latency 15.9x normal).  
*Capabilities touched: Advertisement Retrieval, Cart Management, Currency Conversion, Order Placement, Product Browsing, Product Recommendations, Shipping*


**Your ranking (fix-first to fix-last):** ___, ___, ___, ___, ___

*[Internal — do not show participant before they answer] scenario_id=scenario_k5_023, case letters map to case IDs in order A=re2ob_checkoutservice_cpu_1, B=re2ob_checkoutservice_socket_3, C=re2ob_emailservice_loss_1, D=re2ob_recommendationservice_delay_1, E=re2ob_recommendationservice_mem_2*

---

## Scenario 7 (k=5)

Five incidents are currently open. You have one engineer available. Rank them 1 (fix first) through 5 (fix last).

**Incident A.** Service **checkoutservice** has exhausted available network sockets. The 'Place Order' user journey is measurably degraded (95th-percentile latency 2.1x normal).  
*Capabilities touched: Currency Conversion, Order Placement, Product Browsing, Product Recommendations*

**Incident B.** Service **emailservice** is experiencing disk I/O contention. The 'Place Order' user journey is measurably degraded (95th-percentile latency 1.1x normal).  
*Capabilities touched: Currency Conversion, Order Placement, Product Browsing, Product Recommendations*

**Incident C.** Service **productcatalogservice** is running at sustained high CPU usage. The 'Product Detail View' user journey is measurably degraded (95th-percentile latency 3.1x normal).  
*Capabilities touched: Advertisement Retrieval, Cart Management, Currency Conversion, Order Placement, Product Browsing, Product Recommendations, Shipping*

**Incident D.** Service **productcatalogservice** has exhausted available network sockets. The 'Cart View' user journey is measurably degraded (95th-percentile latency 3.9x normal).  
*Capabilities touched: Advertisement Retrieval, Cart Management, Currency Conversion, Order Placement, Product Browsing, Product Recommendations, Shipping*

**Incident E.** Service **recommendationservice** is under memory pressure. The 'Product Detail View' user journey is measurably degraded (95th-percentile latency 15.9x normal).  
*Capabilities touched: Advertisement Retrieval, Cart Management, Currency Conversion, Order Placement, Product Browsing, Product Recommendations, Shipping*


**Your ranking (fix-first to fix-last):** ___, ___, ___, ___, ___

*[Internal — do not show participant before they answer] scenario_id=scenario_k5_014, case letters map to case IDs in order A=re2ob_checkoutservice_socket_3, B=re2ob_emailservice_disk_3, C=re2ob_productcatalogservice_cpu_2, D=re2ob_productcatalogservice_socket_1, E=re2ob_recommendationservice_mem_1*

---

## Scenario 8 (k=5)

Five incidents are currently open. You have one engineer available. Rank them 1 (fix first) through 5 (fix last).

**Incident A.** Service **checkoutservice** has exhausted available network sockets. The 'Place Order' user journey is measurably degraded (95th-percentile latency 2.1x normal).  
*Capabilities touched: Currency Conversion, Order Placement, Product Browsing, Product Recommendations*

**Incident B.** Service **currencyservice** is responding with added network delay on its calls. The 'Place Order' user journey is measurably degraded (95th-percentile latency 15.5x normal).  
*Capabilities touched: Advertisement Retrieval, Cart Management, Currency Conversion, Order Placement, Product Browsing, Product Recommendations, Shipping*

**Incident C.** Service **emailservice** is experiencing disk I/O contention. The 'Place Order' user journey is measurably degraded (95th-percentile latency 1.1x normal).  
*Capabilities touched: Currency Conversion, Order Placement, Product Browsing, Product Recommendations*

**Incident D.** Service **productcatalogservice** has exhausted available network sockets. The 'Cart View' user journey is measurably degraded (95th-percentile latency 3.9x normal).  
*Capabilities touched: Advertisement Retrieval, Cart Management, Currency Conversion, Order Placement, Product Browsing, Product Recommendations, Shipping*

**Incident E.** Service **recommendationservice** is responding with added network delay on its calls. The 'Cart View' user journey is measurably degraded (95th-percentile latency 3.1x normal).  
*Capabilities touched: Advertisement Retrieval, Cart Management, Currency Conversion, Order Placement, Product Browsing, Product Recommendations, Shipping*


**Your ranking (fix-first to fix-last):** ___, ___, ___, ___, ___

*[Internal — do not show participant before they answer] scenario_id=scenario_k5_020, case letters map to case IDs in order A=re2ob_checkoutservice_socket_2, B=re2ob_currencyservice_delay_2, C=re2ob_emailservice_disk_3, D=re2ob_productcatalogservice_socket_3, E=re2ob_recommendationservice_delay_2*

---

## Scenario 9 (k=5)

Five incidents are currently open. You have one engineer available. Rank them 1 (fix first) through 5 (fix last).

**Incident A.** Service **checkoutservice** is running at sustained high CPU usage. The 'Place Order' user journey is measurably degraded (95th-percentile latency 2.1x normal).  
*Capabilities touched: Advertisement Retrieval, Cart Management, Currency Conversion, Order Placement, Product Browsing, Product Recommendations*

**Incident B.** Service **checkoutservice** has exhausted available network sockets. The 'Place Order' user journey is measurably degraded (95th-percentile latency 2.1x normal).  
*Capabilities touched: Currency Conversion, Order Placement, Product Browsing, Product Recommendations*

**Incident C.** Service **currencyservice** is running at sustained high CPU usage. The 'Home Page View' user journey is measurably degraded (95th-percentile latency 2.7x normal).  
*Capabilities touched: Advertisement Retrieval, Cart Management, Currency Conversion, Order Placement, Product Browsing, Product Recommendations, Shipping*

**Incident D.** Service **emailservice** is dropping a fraction of its network packets. The 'Place Order' user journey is measurably degraded (95th-percentile latency 1.9x normal).  
*Capabilities touched: Currency Conversion, Order Placement, Product Browsing, Product Recommendations*

**Incident E.** Service **recommendationservice** is under memory pressure. The 'Product Detail View' user journey is measurably degraded (95th-percentile latency 15.9x normal).  
*Capabilities touched: Advertisement Retrieval, Cart Management, Currency Conversion, Order Placement, Product Browsing, Product Recommendations, Shipping*


**Your ranking (fix-first to fix-last):** ___, ___, ___, ___, ___

*[Internal — do not show participant before they answer] scenario_id=scenario_k5_027, case letters map to case IDs in order A=re2ob_checkoutservice_cpu_2, B=re2ob_checkoutservice_socket_2, C=re2ob_currencyservice_cpu_1, D=re2ob_emailservice_loss_3, E=re2ob_recommendationservice_mem_2*

---

## Scenario 10 (k=5)

Five incidents are currently open. You have one engineer available. Rank them 1 (fix first) through 5 (fix last).

**Incident A.** Service **checkoutservice** is running at sustained high CPU usage. The 'Place Order' user journey is measurably degraded (95th-percentile latency 2.1x normal).  
*Capabilities touched: Advertisement Retrieval, Cart Management, Currency Conversion, Order Placement, Product Browsing, Product Recommendations*

**Incident B.** Service **checkoutservice** has exhausted available network sockets. The 'Place Order' user journey is measurably degraded (95th-percentile latency 2.1x normal).  
*Capabilities touched: Currency Conversion, Order Placement, Product Browsing, Product Recommendations*

**Incident C.** Service **emailservice** is experiencing disk I/O contention. The 'Place Order' user journey is measurably degraded (95th-percentile latency 1.1x normal).  
*Capabilities touched: Currency Conversion, Order Placement, Product Browsing, Product Recommendations*

**Incident D.** Service **productcatalogservice** has exhausted available network sockets. The 'Cart View' user journey is measurably degraded (95th-percentile latency 3.9x normal).  
*Capabilities touched: Advertisement Retrieval, Cart Management, Currency Conversion, Order Placement, Product Browsing, Product Recommendations, Shipping*

**Incident E.** Service **recommendationservice** is responding with added network delay on its calls. The 'Cart View' user journey is measurably degraded (95th-percentile latency 3.1x normal).  
*Capabilities touched: Advertisement Retrieval, Cart Management, Currency Conversion, Order Placement, Product Browsing, Product Recommendations, Shipping*


**Your ranking (fix-first to fix-last):** ___, ___, ___, ___, ___

*[Internal — do not show participant before they answer] scenario_id=scenario_k5_024, case letters map to case IDs in order A=re2ob_checkoutservice_cpu_2, B=re2ob_checkoutservice_socket_2, C=re2ob_emailservice_disk_2, D=re2ob_productcatalogservice_socket_1, E=re2ob_recommendationservice_delay_1*

---

## Scenario 11 (k=5)

Five incidents are currently open. You have one engineer available. Rank them 1 (fix first) through 5 (fix last).

**Incident A.** Service **currencyservice** is running at sustained high CPU usage. The 'Home Page View' user journey is measurably degraded (95th-percentile latency 2.7x normal).  
*Capabilities touched: Advertisement Retrieval, Cart Management, Currency Conversion, Order Placement, Product Browsing, Product Recommendations, Shipping*

**Incident B.** Service **currencyservice** is responding with added network delay on its calls. The 'Place Order' user journey is measurably degraded (95th-percentile latency 15.5x normal).  
*Capabilities touched: Advertisement Retrieval, Cart Management, Currency Conversion, Order Placement, Product Browsing, Product Recommendations, Shipping*

**Incident C.** Service **productcatalogservice** is running at sustained high CPU usage. The 'Product Detail View' user journey is measurably degraded (95th-percentile latency 3.1x normal).  
*Capabilities touched: Advertisement Retrieval, Cart Management, Currency Conversion, Order Placement, Product Browsing, Product Recommendations, Shipping*

**Incident D.** Service **productcatalogservice** has exhausted available network sockets. The 'Cart View' user journey is measurably degraded (95th-percentile latency 3.9x normal).  
*Capabilities touched: Advertisement Retrieval, Cart Management, Currency Conversion, Order Placement, Product Browsing, Product Recommendations, Shipping*

**Incident E.** Service **recommendationservice** is responding with added network delay on its calls. The 'Cart View' user journey is measurably degraded (95th-percentile latency 3.1x normal).  
*Capabilities touched: Advertisement Retrieval, Cart Management, Currency Conversion, Order Placement, Product Browsing, Product Recommendations, Shipping*


**Your ranking (fix-first to fix-last):** ___, ___, ___, ___, ___

*[Internal — do not show participant before they answer] scenario_id=scenario_k5_015, case letters map to case IDs in order A=re2ob_currencyservice_cpu_1, B=re2ob_currencyservice_delay_2, C=re2ob_productcatalogservice_cpu_1, D=re2ob_productcatalogservice_socket_2, E=re2ob_recommendationservice_delay_2*

---

## Scenario 12 (k=5)

Five incidents are currently open. You have one engineer available. Rank them 1 (fix first) through 5 (fix last).

**Incident A.** Service **checkoutservice** is running at sustained high CPU usage. The 'Place Order' user journey is measurably degraded (95th-percentile latency 2.1x normal).  
*Capabilities touched: Advertisement Retrieval, Cart Management, Currency Conversion, Order Placement, Product Browsing, Product Recommendations*

**Incident B.** Service **emailservice** is dropping a fraction of its network packets. The 'Place Order' user journey is measurably degraded (95th-percentile latency 1.9x normal).  
*Capabilities touched: Currency Conversion, Order Placement, Product Browsing, Product Recommendations*

**Incident C.** Service **productcatalogservice** is running at sustained high CPU usage. The 'Product Detail View' user journey is measurably degraded (95th-percentile latency 3.1x normal).  
*Capabilities touched: Advertisement Retrieval, Cart Management, Currency Conversion, Order Placement, Product Browsing, Product Recommendations, Shipping*

**Incident D.** Service **recommendationservice** is responding with added network delay on its calls. The 'Cart View' user journey is measurably degraded (95th-percentile latency 3.1x normal).  
*Capabilities touched: Advertisement Retrieval, Cart Management, Currency Conversion, Order Placement, Product Browsing, Product Recommendations, Shipping*

**Incident E.** Service **recommendationservice** is under memory pressure. The 'Product Detail View' user journey is measurably degraded (95th-percentile latency 15.9x normal).  
*Capabilities touched: Advertisement Retrieval, Cart Management, Currency Conversion, Order Placement, Product Browsing, Product Recommendations, Shipping*


**Your ranking (fix-first to fix-last):** ___, ___, ___, ___, ___

*[Internal — do not show participant before they answer] scenario_id=scenario_k5_013, case letters map to case IDs in order A=re2ob_checkoutservice_cpu_1, B=re2ob_emailservice_loss_2, C=re2ob_productcatalogservice_cpu_2, D=re2ob_recommendationservice_delay_2, E=re2ob_recommendationservice_mem_1*

---

## Post-scenario questions (ask after ALL scenarios)

1. For each scenario, you will be shown BLAST's computed ordering and a severity-based baseline's ordering, in randomised order and unlabelled (blind A/B). Which do you agree with more?
2. On a 5-point scale (1=not at all useful, 5=very useful), how useful would a written explanation of *why* an incident was ranked where it was be to your work?
3. Free text: for any scenario where your ranking disagreed sharply with either ordering, what would you want the tool to have known that it apparently didn't?

## Analysis plan (once responses exist)

- Inter-rater agreement: Kendall's W across participants per scenario.
- Expert-consensus ranking (median rank per incident) as a second, independent ground truth.
- Kendall's τ between BLAST's ranking, the baseline's ranking, and the expert-consensus ranking — reuses `kendalls_tau()` in `scripts/pipeline/blast_eval_lib.py`, already implemented.
- Report the blind-agreement rate (question 1) and Likert scores (question 2) directly, with free-text responses (question 3) analysed thematically for the discussion section.
