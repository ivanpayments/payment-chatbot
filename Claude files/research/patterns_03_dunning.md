# Patterns 03 — Dunning Retry Ladders & Card-Updater Recovery

Quantified public-source patterns for subscription billing retry ladders, optimal retry timing, decline-code-aware strategies, and Visa VAU / Mastercard ABU / network-token recovery. Applied to synthetic SaaS dataset columns: `attempt_number`, `is_retry`, `retry_status`, `retry_count`, `dunning_retry_day`, `account_updater_triggered`, `decline_category`, `is_approved`.

---

## 1. Retry Ladder Lift Curves (Stripe, Recurly, Chargebee)

**P1. Stripe Smart Retries baseline lift.** Stripe reports merchants on Smart Retries recover ~**9% more revenue** than fixed-schedule retries; Stripe's own internal figure is **$9 recovered per $1 of Billing spend** on Smart Retries. Default window is up to 8 retries over 1–2 weeks. (Stripe Docs — *Automate payment retries*; Stripe blog — *How we built it: Smart Retries*.)

**P2. Cumulative recovery curve (attempt 1 → 4).** Across Churnkey / Churn Buster / Recurly public data, baseline retry alone recovers **~55–57%** of failed recurring payments; layering dunning email/SMS pushes this to **70–85%**. Attempt-level decomposition (Slicker Q3 2025 benchmark): attempt 1 recovers **~25–35 pp** of remaining failures, attempt 2 adds **~10–15 pp**, attempt 3 adds **~5–10 pp**, attempt 4 adds **<5 pp** — classic diminishing-returns curve.

**P3. Diminishing-returns cliff at attempt 4–5.** PayRequest and Slicker aggregate data: attempt-1 success ~**40%**, attempt-2 ~**33%**, attempt-3 ~**25%**, attempt-4+ drops **<5%** each. Beyond 5 retries, incremental lift is statistically noise; most platforms cap at 4–8 attempts. Recurly's Revenue Optimization Engine reports average **61% recovery** of failed renewals at full ladder completion.

**P4. Chargebee Smart Dunning lift over static rules.** Chargebee publicly states Smart Dunning lifts recovery rates **up to 25%** vs static retry rules, retrying up to **12 times** with dynamic intervals based on decline-code analysis. (Chargebee — *Retry Management*.)

---

## 2. Optimal Retry Timing (1d / 3d / 7d / EoM)

**P5. Best universal cadence: 1d / 3d / 7d / 14d.** The retry spacing 1 day → 3 days → 7 days → 14 days is the most frequently cited across Paddle / Primer / Chargebee / Solidgate playbooks. 4–6 attempts over 14–30 days produces the best overall recovery in cross-platform SaaS data.

**P6. Payday-aligned retries beat arbitrary intervals.** Slicker's *Intelligent Payday Retries* benchmark: retrying 3–5 days apart, aligned to the **1st or 15th** of the month, achieves a recovery rate of **~65%** for insufficient-funds declines — materially higher than fixed 1/3/7/14 ladders that ignore payroll cycles.

**P7. End-of-month retries underperform for insufficient funds.** Retries landing on the **25th–31st** (before payday) show the lowest approval probability for insufficient_funds — balances are at their monthly trough. Adyen's multi-armed bandit work (*Rescuing failed subscription payments*) confirms BIN × day-of-month × day-of-week is the dominant predictor of retry success.

**P8. First retry within 4–6 hours captures 15–25 pp.** For timeout / issuer downtime / generic soft declines, an immediate retry within hours of first failure recovers **15–25%** of all failures before any scheduled ladder begins. For insufficient_funds specifically, same-day retry is wasted — wait ≥24–48 h.

---

## 3. Retry Timing by Decline Code

**P9. Soft vs hard decline split.** Soft declines = **80–90%** of all declines (Primer, Checkout.com benchmarks); only soft declines should be retried. Retrying hard declines ("lost card", "stolen card", "pickup card", "invalid account") risks scheme fines and MID reputation damage with issuers.

**P10. "Do Not Honor" (code 05) — cautious retry.** DNH is classified soft but is issuer-risk-driven and only partly retryable. Best practice: **1 retry** 24–48 h later; if still DNH, stop and trigger account-updater + customer email. DNH alone accounts for ~25–35% of all CNP declines in published issuer data.

**P11. "Call issuer" / "Pickup card" / "Lost or stolen" — do not retry.** These are hard declines requiring customer action. Retrying these can damage merchant MID scoring. All platforms (Stripe, Recurly, Chargebee, Adyen) block auto-retries on these codes by default.

**P12. Insufficient_funds — retry 3–5 days apart, 5–7 attempts, 30-day window.** Chargeblast and Monetizely recommend up to **5–7 attempts over 30 days** timed around paydays; recovery rates reach ~65% with payday-aligned cadence vs ~40% with naive 1/3/7/14.

**P13. Issuer downtime / network errors — retry in minutes.** For temporary issuer unavailability (codes 91, 96), retries within **5–30 minutes** succeed at very high rates (>80%) because the root cause is transient. Adyen's Auto Retries fires immediately after first decline for exactly this class.

---

## 4. Card-Updater / Account-Updater Services (VAU, ABU)

**P14. 30% of cards change per year.** Visa publishes that on average **~30% of PANs in an issuer portfolio** undergo a change (PAN, expiry, or closure) each year. This is the upper bound of what VAU/ABU can recover without customer intervention. (Visa VAU Merchant Fact Sheet.)

**P15. Mastercard ABU reduces CNP declines by up to 33%.** Mastercard's published benchmark: ABU reduces card-not-present merchant declines by **up to 33%**. ABU is mandated for issuers in UK, US, Canada, all EU except Turkey, APAC (ex-India/China/Korea/Taiwan), LatAm, MEA. (Mastercard ABU Merchant Global documentation.)

**P16. ~15% of recurring transactions decline in the first place.** Visa/Mastercard data cited by Trust Payments: roughly **15% of recurring card transactions are declined**, with expired / reissued / closed cards a leading cause — the exact category VAU/ABU targets.

**P17. Account-updater enrollment is not universal — acquirer-dependent.** VAU requires merchant enrollment via their acquirer; not all acquirers in every region offer it. In APAC, coverage was historically thin until Visa's 2023–2024 Real-Time VAU rollout with Adyen, Checkout.com, Stripe, and Worldpay as launch partners.

---

## 5. Card-Updater Lift on Hard Declines

**P18. Expired-card declines are the #1 recoverable hard decline.** Paddle and Recurly cite expired/reissued cards as the largest single cause of involuntary churn. VAU/ABU silently refresh **~60–80%** of expired-card attempts when both issuer and merchant participate (estimated upper bound given 30% annual change rate × high issuer participation in US/UK/EU).

**P19. Recovery rate of "silent" updater recoveries.** Industry rule of thumb from Recurly/Frisbii: merchants with account-updater enabled recover **~15–25% additional revenue** on what would otherwise be hard-decline churn, with **zero customer friction** (no email, no re-entry).

**P20. Declined-for-expiration before update: retry after VAU refresh succeeds 70%+.** Once VAU/ABU pushes the new PAN/expiry to the merchant, the immediately subsequent authorization on the refreshed credential approves at issuer-standard rates (**70–85%**), comparable to first-time auth on a valid card.

---

## 6. Network Tokens vs VAU

**P21. Network tokens auto-update on reissue — no batch lag.** Unlike VAU/ABU which refresh on merchant batch inquiry (weekly/monthly), network tokens stay valid when the underlying PAN changes. Stripe and Visa position this as *real-time* equivalence vs VAU's *eventual consistency*.

**P22. Visa network-token authorization lift: +4.6 pp globally.** Visa publishes that CNP token transactions approve at **+4.6%** higher rates than PAN. Mastercard publishes a **+2.1%** lift on tokenized vs PAN. Solidgate merchant data shows up to **+15%** acceptance improvement in some segments.

**P23. Token penetration is growing fast.** Juniper/Visa projections (cited Glenbrook 2025): tokenized transactions rise from **283 B in 2025 → 574 B by 2029** (~2x). Stripe reported enabling network tokens by default for all Stripe Payments merchants in 2024.

**P24. Tokens + VAU are complementary, not substitutes.** Pagos and VGS position: network tokens prevent lifecycle declines (reissue), while VAU handles closures, account changes not covered by tokens, and non-tokenized credentials. Merchants using **both** see the highest lift. One large Stripe merchant: **$1M+/year** interchange savings from network tokens alone.

---

## 7. Proactive Pre-Expiry Update

**P25. 30-day pre-expiry refresh is industry standard.** VAU/ABU inquiry batches typically run **every 7–30 days**; Stripe, Recurly, Chargebee all batch-check stored cards 30 days before their stored expiry date. This proactively refreshes cards before any authorization fails.

**P26. Proactive refresh cuts expired-card failures by 50–70%.** Frisbii/Chargebee public data: merchants running monthly proactive VAU/ABU batches eliminate **50–70%** of would-be expired-card authorization failures, converting them into silent refreshes invisible to the customer.

**P27. Real-Time VAU (Visa 2023+) closes the batch-lag gap.** Historically VAU was daily/weekly batch; Visa's Real-Time VAU API (APAC launch 2023, expanding) allows authorization-time inquiry, eliminating the delta between network-token refresh and updater refresh. Stripe and Adyen use it.

---

## 8. Retry Mechanics by PSP

**P28. Stripe default — 4 retries over ~4 weeks, configurable to 8 over 1–2 weeks.** Stripe Smart Retries default is conservative (4 attempts, 3–5 days apart). Configurable up to 8 retries in a 1-week, 2-week, 3-week, 1-month, or 2-month window. Recommended setting per Stripe: 8 retries in 2 weeks.

**P29. Recurly — configurable 1–10 retries, ML-driven timing.** Recurly's Revenue Optimization Engine lets merchants configure 1–10 retries; ML model picks timing per invoice based on decline code + BIN + history. Public result: **61% average recovery** of failed renewals; **72% of at-risk subscribers saved**; median extension **141 days**.

**P30. Chargebee — up to 12 retries, dual-layer real-time + scheduled.** Chargebee Pay runs a dual-layer strategy: real-time retries for transient errors + scheduled retries for decline codes. Cap is 12 retries. Smart Dunning adds **+25%** recovery vs static rules.

**P31. Adyen RevenueAccelerate — contextual multi-armed bandit.** Adyen's Auto Rescue uses BIN + country + decline-reason + time-of-day features in a bandit model. Published lift: **+4% recovery on retried transactions**, with expected ceiling up to **+10%**. Separates immediate Auto Retries from longer-window Auto Rescue.

**P32. Braintree/PayPal — basic static retry, no ML published.** Braintree offers rules-based retry without published ML/bandit model or public lift benchmark. Generally viewed (Hubifi, Slicker) as behind Stripe/Adyen/Recurly on optimization sophistication.

---

## 9. Involuntary Churn Benchmarks

**P33. Paddle — ~9% of MRR lost to involuntary churn.** Paddle publishes: SaaS companies lose **~9% of MRR** annually to involuntary churn; 20–48% of all churn is involuntary (card failures, expiry, lost cards).

**P34. Recurly 2025 report — 0.8% monthly involuntary churn for B2B SaaS.** Recurly's 2025 Churn Report: B2B SaaS average monthly churn **3.5%** = voluntary **2.6%** + involuntary **0.8%**. ChartMogul benchmark: healthy SaaS keeps involuntary <**1–2% monthly**.

**P35. ProfitWell — 20–40% of total churn is involuntary.** ProfitWell research: 20–40% of churn in subscription businesses is involuntary. Matches Paddle range.

**P36. Slicker / Recurly 2025 forecast: $129B global involuntary-churn exposure.** Recurly's 2025 forecast cited by Slicker: the global subscription economy faces a **$129 B involuntary churn problem** annually — the TAM for recovery tooling.

---

## 10. Geographic Variation

**P37. North America + UK + EU: near-full VAU/ABU coverage.** Both Visa VAU and Mastercard ABU are mandated for US, Canada, UK, and all EU-ex-Turkey. Near-full issuer participation in these markets; merchant coverage constrained only by acquirer enrollment.

**P38. APAC: historically low, now expanding.** Mastercard ABU excludes India, China, Korea, Taiwan. Visa Real-Time VAU launched in APAC 2023–2024 with Adyen, Checkout.com, Stripe, Worldpay. Pre-2023 merchants in APAC had no effective card-updater for Visa.

**P39. Turkey and some LatAm markets: no updater equivalent.** Turkey is excluded from both Visa and Mastercard programs in Europe region. Retry-only is the recovery path for card-expiry declines in these markets — materially higher involuntary churn baseline.

**P40. Network tokens rolling out faster than updater in emerging APAC.** Glenbrook 2025: in markets without mature VAU/ABU (parts of APAC, MEA), network tokens are the primary lifecycle-decline mitigation because token provisioning bypasses the issuer's updater feed.

---

## 11. Card-Type Effects (Debit vs Credit)

**P41. Credit cards ~15% failure rate on recurring; ACH 3–5%.** Monetizely benchmark: credit-card recurring failure rate ~**15%**; ACH/direct-debit is ~**3–5%**. Debit sits between — high insufficient-funds rate but fewer lifecycle declines than credit.

**P42. Debit recovers worse on insufficient_funds retries.** Debit cards hit insufficient_funds more often (real-time balance check) and recover more slowly than credit (which has revolving credit line headroom). Payday-aligned retries matter disproportionately for debit.

**P43. Debit cards expire less frequently than credit.** Debit reissue cycles are typically longer; expired-card decline rates are lower for debit, so VAU/ABU lift is proportionally smaller on debit-heavy portfolios.

---

## 12. Cross-Cutting Modeling Notes for the Synthetic Dataset

**P44. `attempt_number` distribution should be heavy-tailed.** In public benchmarks, ~55–65% of successful recoveries happen by attempt 1; ~80–85% by attempt 2; ~95% by attempt 3. Tail beyond attempt 4 should be <5% of successful recoveries.

**P45. `account_updater_triggered=true` should correlate with `decline_category='expired'` or `'reissued'`.** Realistic synthetic data: when updater is triggered, subsequent `is_approved` rate should jump to **70–85%** (post-refresh authorization), vs **<20%** on non-updater retry of the same expired-card category.

**P46. `dunning_retry_day` should cluster on day-of-month 1, 2, 15, 16.** For insufficient_funds declines, approval probability spikes on and immediately after payday (1st / 15th in US; end-of-month in many EU markets). Modeling retry success conditional on day-of-month is the single highest-leverage feature.

---

## Sources

- [Stripe — Automate payment retries (Smart Retries docs)](https://docs.stripe.com/billing/revenue-recovery/smart-retries)
- [Stripe Blog — How we built it: Smart Retries](https://stripe.com/blog/how-we-built-it-smart-retries)
- [Stripe Newsroom — Expanding network tokens & card account updater](https://stripe.com/newsroom/news/network-tokens-card-account-updater)
- [Stripe — Understanding benefits of network tokens](https://stripe.com/guides/understanding-benefits-of-network-tokens)
- [Recurly — Churn Management product page](https://recurly.com/product/churn-management/)
- [Recurly — Subscriber retention benchmarks](https://recurly.com/research/subscriber-retention-benchmarks/)
- [Recurly — Churn rate benchmarks](https://recurly.com/research/churn-rate-benchmarks/)
- [Recurly — Top payment decline reasons](https://recurly.com/research/subscription-benchmarks-top-payment-decline-reasons/)
- [Recurly — 6 data-based strategies for fighting involuntary churn](https://recurly.com/blog/subscriber-retention-and-understanding-involuntary-vs-voluntary-churn/)
- [Chargebee — Retry Management / Dunning](https://www.chargebee.com/recurring-payments/dunning-management/)
- [Chargebee Docs — Dunning v2](https://www.chargebee.com/docs/payments/2.0/dunning/dunning-v2)
- [Chargebee — SaaS failed payments guide](https://www.chargebee.com/blog/saas-failed-payments/)
- [Paddle — Voluntary vs involuntary churn](https://www.paddle.com/resources/reduce-voluntary-and-involuntary-churn)
- [Paddle — How to prevent soft declines](https://www.paddle.com/blog/how-to-prevent-soft-declines-fltr)
- [Paddle — Payment failure recovery](https://www.paddle.com/resources/payment-failure)
- [Adyen — Announcing RevenueAccelerate](https://www.adyen.com/knowledge-hub/announcing-adyen-revenueaccelerate)
- [Adyen — Rescuing failed subscription payments using contextual multi-armed bandits](https://www.adyen.com/knowledge-hub/rescuing-failed-subscription-payments-using-contextual-multi-armed-bandits)
- [Adyen — Auto Rescue making subscriptions unstoppable](https://www.adyen.com/knowledge-hub/auto-rescue-making-subscriptions-unstoppable)
- [Visa — Account Updater Overview (developer.visa.com)](https://developer.visa.com/capabilities/vau)
- [Visa — VAU FAQ](https://developer.visa.com/capabilities/vau/vau-faq)
- [Visa USA — VAU Merchant Fact Sheet (PDF)](https://usa.visa.com/dam/VCOM/download/merchants/visa-account-updater-product-information-fact-sheet-for-merchants.pdf)
- [Visa — Real-Time VAU launch in APAC](https://www.prnewswire.com/apac/news-releases/visa-launches-real-time-visa-account-updater-in-asia-pacific-to-streamline-payment-experiences-301981023.html)
- [Mastercard — Automatic Billing Updater Merchant Global (PDF)](https://www.mastercard.us/content/dam/public/mastercardcom/na/us/en/documents/Mastercard-Automatic-Billing-Updater-Merchant-Global-2017.pdf)
- [Mastercard Developers — ABU](https://developer.mastercard.com/product/automatic-billing-updater-abu/)
- [Trust Payments — VAU & ABU for recurring payments](https://www.trustpayments.com/blog/how-to-master-recurring-payments-for-your-subscription-services-by-using-vau-and-abu/)
- [Solidgate — Network tokenization & authorization rates](https://solidgate.com/blog/network-tokenization-authorization-rates/)
- [Solidgate — Card decline recovery guide](https://solidgate.com/blog/how-to-manage-card-declines-and-recover-lost-revenue/)
- [Pagos — Using Account Updater and Network Tokenization together](https://pagos.ai/blog/not-one-or-the-other-but-both-using-account-updater-and-network-tokenization-to-optimize-payments-performance)
- [VGS — Do merchants need both network tokens and account updater?](https://www.verygoodsecurity.com/blog/posts/do-merchants-need-both-network-tokens-and-account-updater)
- [Glenbrook — We (Really) Can't Stop Talking About Tokenization: 2025 Update](https://glenbrook.com/payments_views/we-really-cant-stop-talking-about-tokenization-a-2025-update/)
- [Frisbii — How tokens provide automatic credit-card updates & reduce churn](https://frisbii.com/blog/tokenization-token-credit-card-updates/)
- [Primer — How to manage soft declines](https://primer.io/blog/soft-declines)
- [Checkout.com — Soft declines](https://www.checkout.com/blog/when-should-merchants-prepare-for-soft-declines)
- [Churnkey — Hard vs Soft Declines](https://churnkey.co/blog/hard-soft-declines/)
- [Churnkey — Stripe Smart Retries FAQs](https://churnkey.co/blog/stripe-smart-retries/)
- [Slicker — Smart Retries vs Rules-Based Dunning 2025 benchmarks](https://www.slickerhq.com/resources/blog/smart-retries-vs-rules-based-dunning-2025-stripe-recurly-slicker-ai-benchmarks)
- [Slicker — How many retries for soft declines? Q3 2025 guide](https://www.slickerhq.com/blog/soft-decline-retry-strategies-saas-cfos-q3-2025-guide)
- [Slicker — Intelligent Payday Retries](https://www.slickerhq.com/blog/intelligent-payday-retries-scheduling-failed-subscription-payments-slash-passive-churn)
- [Slicker — $129B involuntary churn forecast (Recurly 2025)](https://www.slickerhq.com/blog/129-billion-problem-recurly-2025-involuntary-churn-forecast-ai-recovery-engines)
- [Slicker — Chargebee payment-failure recovery playbook 2025](https://www.slickerhq.com/blog/chargebee-payment-failure-recovery-playbook-2025-intelligent-retries-slicker-cut-churn-40-percent)
- [Slicker — Dynamic retry schedules for soft declines](https://www.slickerhq.com/resources/blog/dynamic-retry-schedules-soft-declines-stripe-chargebee-slicker)
- [Monetizely — Involuntary churn: the silent revenue killer](https://www.getmonetizely.com/articles/understanding-involuntary-churn-the-silent-revenue-killer-in-saas)
- [Monetizely — Payment failure and retry rates](https://www.getmonetizely.com/articles/understanding-payment-failure-and-retry-rates-critical-saas-metrics-for-revenue-health)
- [ChartMogul — SaaS Benchmarks Report 2023](https://chartmogul.com/reports/saas-benchmarks-report/)
- [Spreedly — Account Updater expands global coverage](https://www.spreedly.com/blog/account-updater-expands-global-coverage)
- [Chargeblast — How to fix insufficient-funds declines](https://www.chargeblast.com/blog/how-to-fix-insufficient-funds-payment-declines)
- [PayRequest — Dunning management guide 2026](https://payrequest.io/blog/dunning-management-subscription-recovery-guide-2026)
