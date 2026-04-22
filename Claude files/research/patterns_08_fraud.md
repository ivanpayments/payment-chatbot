# Fraud, Chargebacks, Disputes & Representments — Quantified Patterns for SaaS Subscription Billing

**Scope:** 40 quantified patterns across fraud rates, chargeback distributions, reason codes, network thresholds, representment outcomes, and behavioral signals — calibrated for low-fraud SaaS MCCs (5734, 7372, 5968) with cross-comparisons to higher-risk verticals.

**Target columns:** `risk_score, risk_decision, chargeback_amount, chargeback_count, decline_category, fraud_screening_status, representment_status, three_ds_status, network_token_used, customer_country, sku_tier`.

---

## 1. Chargeback rate by MCC (SaaS vs. benchmarks)

| # | Pattern | Quantified value | Source |
|---|---|---|---|
| 1 | **SaaS / computer software (MCC 5734, 7372) baseline chargeback rate** | 0.04% – 0.12% of approved attempts (median ~0.07%) | Chargebacks911 2023 Cardholder Dispute Index; Stripe Radar benchmarks; Adyen RevenueProtect 2023 |
| 2 | **Direct marketing / continuity / subscription merchants (MCC 5968)** | 0.3% – 0.9% of approved attempts — ~5–10x pure SaaS because of trial-to-paid friction and "forgot to cancel" disputes | Visa VAMP historical disclosures; Ethoca 2022 subscription report |
| 3 | **Adult / digital goods (MCC 5967) comparator** | 2% – 5% chargeback rate; often breaches VDMP at the standard-program level | Visa VIRP bulletins; Chargebacks911 High-Risk 2023 |
| 4 | **Travel / airlines (MCC 4722, 4511) comparator** | 0.5% – 1.5% of approved attempts; spikes to 2%+ during disruption events | Mastercard ECP annual data; Verifi Travel Insights 2023 |
| 5 | **Gambling / crypto on-ramps (MCC 7995, 6051) comparator** | 1.5% – 3.5% chargeback rate; Visa treats as High-Brand-Risk — all transactions must be 3DS authenticated | Visa Integrity Risk Program 2021 update |

## 2. Card network dispute/fraud thresholds

| # | Pattern | Quantified value | Source |
|---|---|---|---|
| 6 | **Visa VDMP (Dispute Monitoring Program) Early Warning** | 0.65% dispute rate AND 75+ disputes/month — monitoring tier, no fine | Visa Core Rules, April 2023 edition |
| 7 | **Visa VDMP Standard threshold** | 0.9% dispute rate AND 100+ disputes/month; fines $50/dispute months 1–6, $75/dispute months 7–12 | Visa VDMP guide |
| 8 | **Visa VDMP Excessive threshold** | 1.8% dispute rate AND 1,000+ disputes/month; fines $25K/month on top of per-dispute fines | Visa VDMP guide |
| 9 | **Visa VAMP (new integrated program, Apr 2025)** | Ratio = (TC40 fraud + non-fraud disputes) / settled transactions. Above-standard: >0.9% acquirer-level; Excessive: >1.5%. Replaces VDMP + VFMP | Visa AI #AI10467, Jan 2025 |
| 10 | **Mastercard ECP (Excessive Chargeback Program)** | 1.5% chargeback-to-sales ratio AND 100+ chargebacks/month → Tier 1; fines start $1K/month, escalating to $200K+ after 12 months | Mastercard Chargeback Guide 2023 |
| 11 | **Mastercard Excessive Fraud Merchant (EFM) program** | >$50K monthly fraud AND ≥0.50% fraud ratio AND ≥10% e-commerce fraud 3DS-unauthenticated → $500–$1,000/month assessments | Mastercard Security Rules and Procedures |

## 3. Fraud concentration by country

| # | Pattern | Quantified value | Source |
|---|---|---|---|
| 12 | **Top-5 fraud origin concentration** | In global merchant portfolios, 5–8 countries produce 60–70% of card-not-present fraud losses; tail of 100+ countries produces <5% each | Sift Q4 2023 Digital Trust Index; Signifyd 2023 State of Fraud |
| 13 | **Highest-risk origin countries for SaaS** | BR, MX, RU (sanctions-adjusted), ID, PH, NG, VN, IN — fraud rates 3–8x portfolio average on self-serve signups | Ravelin Global Fraud Trends 2023; Kount 2023 eCommerce Fraud Report |
| 14 | **IP/country mismatch signal** | Billing country ≠ IP country = 4–7x fraud rate vs. matched | Sift fraud heuristics; Stripe Radar documentation |
| 15 | **Sanctions / high-risk regions** | ~0.3–0.6% of SaaS signups attempt from sanctioned ASNs (VPN-routed); ~12–18% of those that slip through become fraud disputes | Treasury OFAC SDN matching + vendor benchmarks (Sardine, Unit21) |

## 4. Fraud by product / SKU tier

| # | Pattern | Quantified value | Source |
|---|---|---|---|
| 16 | **PLG / Starter self-serve vs. Enterprise** | Starter tier: 0.15–0.40% fraud rate. Enterprise (sales-assisted, invoiced, ACH): 0.01–0.03%. **3–5x, sometimes 10x, delta** | Stripe SaaS benchmarks 2023; internal PSP portfolio data (Adyen, Checkout.com case studies) |
| 17 | **Trial tier vs. paid tier** | Free-trial signups: 5–15% flagged as fraud or abuse (synthetic identity, disposable emails, prepaid/BIN-cycled cards) | Kount 2022 Trial Abuse Report; Verifi subscription insights |
| 18 | **Usage-based (metered) vs. flat subscription** | Usage tiers have 30–50% higher dispute incidence (bill-shock disputes, "didn't authorize overage") — maps to reason code 13.2 (Cancelled Recurring) | Ethoca 2023 Dispute Causes |

## 5. Dispute reason code distribution (Visa taxonomy)

| # | Pattern | Quantified value | Source |
|---|---|---|---|
| 19 | **Visa 10.x "Fraud" bucket share** | 55–70% of SaaS disputes; dominated by **10.4 (Other Fraud — Card Absent)** ~45–55% of all disputes | Visa Dispute Resolution Manual; Verifi Order Insight 2023 |
| 20 | **Visa 13.x "Consumer Disputes" bucket share** | 20–30% of SaaS disputes. Dominated by **13.1 (Merchandise/Services Not Received)** and **13.2 (Cancelled Recurring)** | Chargebacks911 Reason Code Encyclopedia 2023 |
| 21 | **Visa 12.x "Processing Errors" bucket** | 3–7% of SaaS disputes — **12.5 (Incorrect Amount)** and **12.6.2 (Duplicate Processing)** dominate; low representment difficulty | Visa DRM |
| 22 | **Visa 11.x "Authorization" bucket** | 2–5% — mostly **11.3 (No Authorization)** on legacy/expired mandates; preventable with network tokens + account updater | Visa DRM; Mastercard equivalent codes 4807/4808 |
| 23 | **Mastercard reason code mapping** | 4837 (No Cardholder Authorization) ≈ Visa 10.4; 4855 (Goods/Services Not Provided) ≈ 13.1; 4841 (Cancelled Recurring) = explicit subscription code | Mastercard Chargeback Guide |

## 6. First-party / friendly fraud

| # | Pattern | Quantified value | Source |
|---|---|---|---|
| 24 | **Share of disputes that are first-party fraud** | **50–70% of SaaS disputes** are first-party — cardholder used the service but disputes the charge. Cross-industry average ~40–50%; SaaS/digital higher because no shipping evidence | Visa Compelling Evidence 3.0 announcement; Sift 1st-Party Fraud Report 2023; Mastercard First-Party Trust 2023 |
| 25 | **Visa Compelling Evidence 3.0 (CE3.0) flip rate** | With 2 prior undisputed transactions of same merchant+cardholder in 120–365 days, 60–75% of 10.4 disputes flip pre-arbitration | Visa CE3.0 rule April 2023; Verifi CE3.0 results |
| 26 | **Mastercard First-Party Trust (FPT) program** | Launched 2023, enables merchants to submit device/IP/login evidence at dispute entry. Early adopter merchants report 20–35% reduction in first-party chargebacks | Mastercard FPT 2023 press materials |

## 7. Subscription-specific dispute patterns

| # | Pattern | Quantified value | Source |
|---|---|---|---|
| 27 | **"Forgot to cancel" disputes** | 25–40% of subscription chargebacks map to cardholder forgetting cancellation or misunderstanding trial-to-paid conversion (13.2 / 4841) | FTC ROSCA enforcement data; Ethoca 2022 subscription study |
| 28 | **Post-renewal dispute spike** | Disputes cluster **7–21 days after annual renewal charge**; 40–60% of annual-plan disputes fall in that window | Chargebacks911 subscription bulletin 2023 |
| 29 | **Cancel-to-keep pattern** | 8–15% of trial users cancel within 24h of conversion charge, then dispute anyway for "not authorized" — requires cancellation flow audit logs as evidence | Recurly Subscription Commerce Index 2023 |
| 30 | **Price-increase disputes** | After >10% price hike, dispute volume rises 1.5–2.5x for 60 days; mitigable with 30-day pre-notification email receipts | Adyen RevenueProtect 2022 |

## 8. Representment win rates

| # | Pattern | Quantified value | Source |
|---|---|---|---|
| 31 | **SaaS overall representment win rate** | **20–35%** merchant win rate on fought disputes. Skews higher (35–50%) with Compelling Evidence 3.0 or FPT; lower (10–20%) without digital usage evidence | Midigator Dispute Benchmarks 2023; Verifi 2023 |
| 32 | **Win rate by reason code (SaaS)** | 10.4 Other Fraud: 25–40% (with CE3.0 evidence). 13.1 Not Received: 40–55% (login logs are decisive). 13.2 Cancelled Recurring: 15–25% (hard to win without clear cancel policy proof). 12.x Processing: 60–80% | Verifi Win Rate Benchmarks 2023; Chargebacks911 |
| 33 | **Compelling evidence that moves the needle** | Top 3 for SaaS: (1) login timestamps post-transaction, (2) IP+device match to prior transactions, (3) cancellation flow screenshots. Inclusion of all 3 → ~2x win rate vs. bare receipt | Verifi CE3.0 playbook; Ethoca representment insights |
| 34 | **Pre-dispute deflection** | Ethoca Alerts + Verifi RDR (Rapid Dispute Resolution) deflect 20–40% of disputes **before** they become chargebacks; net cost per deflection ~$4–8 vs. $15–100 chargeback fee + lost revenue | Ethoca/Verifi product sheets 2023 |

## 9. Velocity / behavioral fraud signals

| # | Pattern | Quantified value | Source |
|---|---|---|---|
| 35 | **New customer + new card + new country (triple-new)** | 5–10x baseline fraud rate vs. returning customer on known card/country | Sift Digital Trust Index 2023; Ravelin ML feature importance |
| 36 | **Velocity: >3 cards tried / email / hour** | 15–30x fraud rate — classic card-testing signature; typical decline_category = "do_not_honor" or "pickup_card" cascading | Stripe Radar heuristics; Kount card-testing benchmark |
| 37 | **Disposable email domain signal** | 3–6x fraud rate on signups from Mailinator/Guerrilla/Temp-Mail domains; 10–20% of trial abuse traffic | Ravelin 2023; Sardine fraud benchmarks |

## 10. 3DS authentication impact

| # | Pattern | Quantified value | Source |
|---|---|---|---|
| 38 | **3DS2 frictionless authenticated vs. non-3DS fraud rate** | 60–80% lower fraud on 3DS2-authenticated transactions; liability shifts to issuer for authenticated fraud disputes (reason code 10.4 cannot be raised for "fully authenticated" when Visa) | EMVCo 3DS2 benchmark 2023; Adyen 3DS performance report |
| 39 | **3DS2 authorization uplift** | 2–6 percentage-point uplift in approval rates vs. non-3DS in EEA PSD2-regulated flows; on challenge flow, 10–15% abandonment | Checkout.com 2023 3DS report |
| 40 | **Liability shift coverage** | For 3DS2 fully-authenticated transactions: issuer bears fraud chargeback (Visa 10.4) ~95% of the time; merchant still liable for consumer disputes (13.x) | Visa/Mastercard 3DS liability-shift rules |

## 11. Network tokens & fraud

| # | Pattern | Quantified value | Source |
|---|---|---|---|
| 41 | **Network-tokenized transactions fraud rate** | ~40% lower fraud rate vs. PAN-based transactions (Visa VTS + Mastercard MDES benchmarks); also 2–3pp higher authorization rate | Visa Token Service 2023 report; Mastercard MDES 2023 |
| 42 | **Account updater effect on involuntary churn** | Network token lifecycle + account updater reduces decline_category = "expired_card" by 60–80%, removing a large source of 11.x disputes | Visa VAU; Mastercard ABU product data |

## 12. BIN-level fraud concentration

| # | Pattern | Quantified value | Source |
|---|---|---|---|
| 43 | **80/20 BIN concentration** | ~20% of BINs in a SaaS portfolio generate ~80% of fraud disputes. Prepaid + certain non-reloadable gift BINs dominate | Kount BIN risk data; Sift BIN analysis 2023 |
| 44 | **Prepaid BIN fraud rate** | 3–8x fraud rate of standard consumer credit; often used for trial abuse and card testing | Ravelin 2023 |
| 45 | **Commercial/corporate BINs** | 50–70% lower fraud rate than consumer — an enterprise-SKU proxy signal | Visa commercial card data |

## 13. Free-trial abuse

| # | Pattern | Quantified value | Source |
|---|---|---|---|
| 46 | **Trial fraud/abuse rate** | 5–15% of free-trial signups are fraud or multi-account abuse (same user, new card, new email cycling trials) | Kount 2022; Recurly 2023 |
| 47 | **Synthetic identity share of trial fraud** | 30–50% of caught trial-abuse accounts involve synthetic identities (real SSN fragments + fake names) in US market | FTC 2023 synthetic ID fraud report; Sardine benchmarks |

## 14. Card-testing attacks

| # | Pattern | Quantified value | Source |
|---|---|---|---|
| 48 | **Card-testing signature** | Bursts of $0.50–$5.00 authorizations, 80–95% declined, from few IPs across many BINs. Often probing stolen card lists before use elsewhere | Stripe Radar card-testing guide 2023 |
| 49 | **Attack volume spike** | A single card-testing attack can inject 10,000–100,000 attempts in hours; unmitigated merchants face $0.10–$0.25 per attempt in gateway/auth fees — six-figure costs | Stripe; Checkout.com incident reports |
| 50 | **Mitigation impact** | Rate limits + CAPTCHA + AVS hard-fail reduce card-testing cost by 90–99%; typical SaaS card-testing-to-fraud conversion ~0.5–2% of successful test auths | Sift anti-card-testing playbook |

## 15. Account takeover (ATO)

| # | Pattern | Quantified value | Source |
|---|---|---|---|
| 51 | **SaaS ATO incidence** | 0.05–0.3% of monthly active accounts experience credential-stuffing attempts; 5–15% success rate on reused passwords absent MFA | Auth0/Okta 2023 State of Secure Identity; Sift ATO Index 2023 |
| 52 | **ATO → chargeback path** | ~10–20% of successful ATOs lead to fraudulent subscription changes / API key exfiltration / add-seat abuse that later becomes a dispute (often 13.1) | Ravelin ATO benchmarks |

## 16. Chargeback fees and total cost

| # | Pattern | Quantified value | Source |
|---|---|---|---|
| 53 | **Per-dispute fees** | $15–$100 per chargeback depending on processor/network. Typical: Stripe $15, Adyen €7.50–€25, Braintree $15, high-risk processors $75–$100 | Processor public pricing pages |
| 54 | **Representment filing fee** | $25–$50 additional when merchant disputes; lost representment compounds to $40–$150 total fees | Midigator 2023 cost study |
| 55 | **True cost multiplier** | Industry rule-of-thumb: true cost of a chargeback = **2.5x–3.5x the transaction value** (reversal + fees + lost goods/service + ops time + program-fee risk) | LexisNexis True Cost of Fraud 2023 |
| 56 | **Program fees if thresholds breached** | VDMP/ECP program fines: $25K–$200K per month of non-compliance, scaling with chargeback count and months in program | Visa/Mastercard rules |

---

## Data-model mapping (target columns)

- **`risk_score`**: expected 0–100 distribution with long right tail; 95th percentile correlates with patterns 35–37, 43
- **`risk_decision`**: typically {approve, review, decline, step_up_3ds}; step-up usage should be 5–15% of risky traffic (pattern 38–40)
- **`chargeback_count` / `chargeback_amount`**: aggregate to merchant-month for VDMP/VAMP ratio calc (patterns 6–10)
- **`decline_category`**: card-testing (pattern 48), expired_card drop via account updater (42), do_not_honor (36)
- **`fraud_screening_status`**: {passed, review, blocked, 3ds_required}; map to reason-code downstream (19–23)
- **`representment_status`**: {not_fought, fought_won, fought_lost, pending, deflected_pre_dispute}; benchmark 20–35% win (31)
- **`three_ds_status`**: {none, attempted, frictionless_auth, challenge_auth, failed}; fraud-rate delta pattern 38
- **`network_token_used`**: boolean; pattern 41
- **`customer_country`**: concentration patterns 12–15
- **`sku_tier`**: {trial, starter, pro, enterprise}; pattern 16–18

---

## Primary source index

- **Visa**: Dispute Resolution Manual (public core rules excerpts); VDMP/VAMP/VIRP guides; Compelling Evidence 3.0 (April 2023); Visa Token Service 2023 report
- **Mastercard**: Chargeback Guide; Security Rules and Procedures; First-Party Trust (FPT) 2023; MDES
- **Fraud vendors**: Sift Digital Trust Index 2023; Signifyd State of Fraud 2023; Kount eCommerce Fraud Report; Ravelin Global Fraud Trends 2023; Sardine risk benchmarks
- **Dispute/representment vendors**: Chargebacks911 Cardholder Dispute Index; Midigator Dispute Benchmarks; Verifi Order Insight + CE3.0 playbook; Ethoca Alerts insights
- **PSPs**: Stripe Radar documentation + card-testing guide; Adyen RevenueProtect whitepapers; Checkout.com 2023 3DS report; Recurly Subscription Commerce Index
- **Regulators / research**: FTC ROSCA enforcement; FTC synthetic ID 2023; LexisNexis True Cost of Fraud 2023; EMVCo 3DS2 benchmarks; Auth0/Okta State of Secure Identity
