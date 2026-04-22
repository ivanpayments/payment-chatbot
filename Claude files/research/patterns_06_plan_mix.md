# Patterns 06 — SaaS Plan Mix, Trials, and Billing Cadence

**Purpose**: Realistic benchmarks for a synthetic SaaS billing dataset with 3 tiers (Starter / Pro / Enterprise) × 3 cadences (Monthly / Annual / Usage).
**Target columns**: `sku_tier`, `billing_cadence`, `plan_mrr_usd`, `plan_list_price_usd`, `trial_end`, `billing_reason`, `proration_amount_usd`, `charge_type`.
**Sources**: OpenView PLG Benchmarks (2020–2023), SaaStr, ChartMogul SaaS Growth Report, Bessemer State of the Cloud, SaaS Capital, Paddle/ProfitWell PLG studies, public 10-Ks (Snowflake, Datadog, Twilio, Zoom, HubSpot, Atlassian, MongoDB), Price Intelligently studies, 37signals pricing posts.

---

## 1. Plan tier mix by subscriber count (logo count)

| # | Pattern | Quantified value | Source / company |
|---|---|---|---|
| 1.1 | PLG SaaS skews heavily Starter by logos | Starter 55–65% / Pro 25–32% / Enterprise 8–15% of paying logos | OpenView 2022 PLG Benchmarks; Atlassian FY23 (Standard+Free ~60% of instances) |
| 1.2 | Sales-led SaaS has flatter mid-tier | Starter 20–30% / Pro 45–55% / Enterprise 20–30% | Salesforce, Workday customer mix (10-K disclosures) |
| 1.3 | "Team" / Pro tier is the modal plan for mid-market PLG | Pro = 28–34% of logos but ~40% of net-new MRR in month 3 | ChartMogul 2023 benchmark, Notion/Figma public comments |
| 1.4 | Enterprise-heavy vendors (infra, security) flip the triangle | Enterprise ≥ 40% of logos at Snowflake, CrowdStrike, Datadog Pro+ | 10-K segment data 2023 |
| 1.5 | Free-plan logos dwarf paid 10–40× in freemium SaaS | Slack historically ~70% free workspaces; Dropbox ~500M free vs ~18M paid (~3%) | Dropbox 10-K 2023; Slack S-1 2019 |

---

## 2. Plan tier mix by revenue (ARR share)

| # | Pattern | Quantified value | Source |
|---|---|---|---|
| 2.1 | Revenue mix inverts the logo mix | Enterprise 40–55% of ARR despite 10–15% of logos | OpenView 2023; HubSpot 10-K (Enterprise Hub revenue share) |
| 2.2 | Pro tier = "cash cow" band | Pro 30–40% of ARR, highest gross margin contribution | SaaS Capital 2023 survey |
| 2.3 | Starter tier ARR share is small but predictable | Starter 8–15% of ARR, <3% monthly volatility | ProfitWell 2022 |
| 2.4 | ARPA ratio Starter : Pro : Enterprise ≈ 1 : 4–6 : 15–30 | Typical list: $25 / $120 / $600+ per seat/month | Price Intelligently 2021 |
| 2.5 | Top 10% of customers = 50–65% of ARR in sales-led SaaS | Snowflake top 10 customers = ~17% of FY23 revenue; top decile ≥ 55% | Snowflake 10-K FY23 |

---

## 3. Monthly vs annual vs usage cadence split

| # | Pattern | Quantified value | Source |
|---|---|---|---|
| 3.1 | Annual-billed subs are a minority by count, majority by revenue | 25–40% of subs on annual, but 50–65% of ARR | OpenView 2022 |
| 3.2 | Usage-based revenue rising | ~45% of top-100 SaaS companies now have ≥20% usage revenue (up from 27% in 2018) | OpenView/Kyle Poyar 2023 |
| 3.3 | Pure-usage vendors | Snowflake ~95% consumption revenue, Twilio ~75%, MongoDB Atlas ~65% | 10-Ks 2023 |
| 3.4 | Hybrid seat+usage | Datadog ≈ 70% usage / 30% platform fee; HubSpot <5% usage | 10-Ks 2023 |
| 3.5 | Monthly-billed plans over-index on Starter | 70–80% of Starter subs pay monthly; only 20–35% of Enterprise | ChartMogul 2023 |
| 3.6 | Annual prepay is standard at Enterprise | 85–95% of Enterprise contracts are annual (or multi-year) prepaid | Bessemer SOTC 2023 |

---

## 4. Free plan / trial / freemium conversion economics

| # | Pattern | Quantified value | Source |
|---|---|---|---|
| 4.1 | Freemium free→paid conversion | 2–5% long-run (Dropbox ~2.5%, Notion ~4%, Evernote ~3%) | 10-Ks, founder interviews |
| 4.2 | Team-level freemium converts higher than individual | Slack team conversion ~30% of qualified teams; individual free→paid <5% | Slack S-1 |
| 4.3 | Opt-in free trial (no freemium) conversion | 15–25% typical for PLG SaaS on 14-day trial | Totango, ProfitWell benchmarks |
| 4.4 | Reverse-trial (auto-downgrade to free) | 15–20% conversion — ~2× a pure time-limited trial | Kyle Poyar / OpenView 2022 |
| 4.5 | Self-serve freemium LTV:CAC | 3–4× for PLG, vs 2–3× for sales-led trial motions | OpenView 2023 |

---

## 5. Trial length effects

| # | Pattern | Quantified value | Source |
|---|---|---|---|
| 5.1 | Shorter trials often convert better | 14-day trial converts ~20–25%, 30-day ~15–18% when tested head-to-head | Price Intelligently 2020 A/B studies |
| 5.2 | Median activation happens in first 3 days | ~60% of trial activations occur within 72h of signup | Amplitude + Pendo 2022 PLG report |
| 5.3 | Extending trial past 14 days yields diminishing returns | <3pp incremental conversion from day 15–30 | OpenView 2022 |
| 5.4 | 7-day trials work for simple tools only | Sub-$30 MRR single-seat tools see 18–22% conversion at 7 days | Paddle 2022 |

---

## 6. No-credit-card vs card-captured trials

| # | Pattern | Quantified value | Source |
|---|---|---|---|
| 6.1 | Card-captured trial converts 2–3× higher | Card-required ~40–60% trial→paid vs 15–25% card-optional | ProfitWell 2019; Totango |
| 6.2 | Card-required trials generate far fewer starts | 60–75% fewer trial signups — top-of-funnel filter | Paddle 2022 |
| 6.3 | Net paying customers are comparable or higher with card-required | Card-required nets 5–15% more paid customers per marketing $ | Price Intelligently 2020 |
| 6.4 | Involuntary churn on auto-converted card trials | 4–8% of auto-converted subs churn in the first billing cycle | ChartMogul payments report 2023 |

---

## 7. Usage-based revenue share

| # | Pattern | Quantified value | Source |
|---|---|---|---|
| 7.1 | Snowflake: pure consumption | ~95% of revenue is usage (credits); <5% services | Snowflake 10-K FY24 |
| 7.2 | Twilio | ~75–90% usage (messages, minutes); <10% platform fees | Twilio 10-K FY23 |
| 7.3 | Datadog | ~70% usage (host-hours, log GB) + 30% base platform/seat | Datadog 10-K FY23 |
| 7.4 | MongoDB Atlas | ~65% of total revenue is Atlas consumption, growing ~35% YoY | MongoDB 10-K FY24 |
| 7.5 | Zoom, HubSpot | <5% usage — seat-dominant | 10-Ks 2023 |
| 7.6 | Usage SaaS NRR premium | Consumption vendors median NRR 120–130% vs 105–115% seat-only | Bessemer SOTC 2023 |

---

## 8. PLG conversion funnel (signup → activation → paid)

| # | Pattern | Quantified value | Source |
|---|---|---|---|
| 8.1 | Signup → activation | 25–40% of signups reach the "aha" event within 7 days | Amplitude PLG 2022 |
| 8.2 | Activation → paid | 15–25% of activated users convert to paid (freemium) | OpenView 2022 |
| 8.3 | End-to-end signup → paid | Median 4–8% for freemium; 15–25% for trial-only | ProfitWell 2022 |
| 8.4 | Time-to-paid median | 21 days for PLG SaaS; 90+ days for sales-assisted | Paddle 2023 |

---

## 9. Sales-assisted vs self-serve conversion

| # | Pattern | Quantified value | Source |
|---|---|---|---|
| 9.1 | Enterprise sales-touch closes 25–35% of qualified trials | vs 4–8% pure self-serve | OpenView 2022 |
| 9.2 | PQL→opportunity→closed-won | ~50% PQL→oppty, 30–40% oppty→closed-won | HubSpot, Gainsight PLS data 2023 |
| 9.3 | Sales-assist lifts ACV 3–8× | Self-serve Pro ACV ~$1.2K; sales-assisted Enterprise ~$8K+ | OpenView 2023 |
| 9.4 | Sales cycle length | Starter <7 days, Pro 14–30 days, Enterprise 60–120 days | Bessemer SOTC 2023 |

---

## 10. Annual discount rate

| # | Pattern | Quantified value | Source |
|---|---|---|---|
| 10.1 | Typical annual discount | 15–25% off monthly list — median 20% | Price Intelligently 2021 |
| 10.2 | Notable examples | HubSpot ~10%, Zoom ~16%, Notion ~20%, Atlassian ~17%, Figma 20% | Published pricing pages 2024 |
| 10.3 | Aggressive discounts at Enterprise | 25–40% off via multi-year + volume | Bessemer SOTC 2023 |
| 10.4 | Annual reduces churn ~2–3× | Annual churn 5–8% vs monthly 12–20% for comparable SKUs | ChartMogul 2023 |

---

## 11. Upgrade / downgrade frequency

| # | Pattern | Quantified value | Source |
|---|---|---|---|
| 11.1 | Tier change rate | 3–8% of customers change tier per quarter | OpenView 2022 |
| 11.2 | Upgrade:downgrade ratio | Healthy PLG 3–5 upgrades per downgrade; struggling 1–1.5 | ChartMogul 2023 |
| 11.3 | Starter→Pro is most common jump | ~60% of upgrades in PLG SaaS | Notion, Figma public comments |
| 11.4 | Seat expansion dominates $ expansion | Seat additions = 55–70% of expansion MRR in seat-based SaaS | Gainsight 2023 |

---

## 12. Proration dynamics

| # | Pattern | Quantified value | Source |
|---|---|---|---|
| 12.1 | Mid-cycle upgrade proration | 40–60% of upgrade charges are prorated credits/debits | Stripe Billing benchmarks 2023 |
| 12.2 | Median proration amount | ~35–50% of a month's delta (i.e., ~mid-cycle upgrade) | Recurly Insights 2022 |
| 12.3 | Downgrade credits typically deferred | 70%+ of SaaS defers downgrade credit to next cycle rather than refunding | Paddle 2022 |
| 12.4 | Seat add-ons under annual plans | Usually prorated at per-seat/month rate, not annual discount rate | Stripe Billing docs / common practice |

---

## 13. Price increases and grandfathering

| # | Pattern | Quantified value | Source |
|---|---|---|---|
| 13.1 | Typical SaaS price increase | 5–15% per round; Zoom +9% (2023), Atlassian +5–15% annually, HubSpot +12% (2023) | Company press releases |
| 13.2 | Grandfathering reduces churn spike | Grandfathered cohorts churn +1–2pp vs control; non-grandfathered +4–8pp | Price Intelligently 2021 |
| 13.3 | Willingness-to-pay loss | ~30% of SaaS firms under-price by 20%+ (leave 5–15% ARR on the table) | ProfitWell 2020 |
| 13.4 | Annual price-raise cadence | 38% of SaaS now raise prices annually vs 8% in 2018 | OpenView 2023 |

---

## 14. Add-on / module attach

| # | Pattern | Quantified value | Source |
|---|---|---|---|
| 14.1 | Enterprise modules per customer | 1.5–2.5 add-ons/modules attached on average | HubSpot 10-K (multi-hub attach) |
| 14.2 | HubSpot multi-hub attach | ~35% of customers on 2+ Hubs in FY23, up from ~25% FY20 | HubSpot 10-K FY23 |
| 14.3 | Salesforce cloud attach | Top 25% of customers use 5+ clouds; average ~2.5 | Salesforce investor day 2023 |
| 14.4 | Datadog product attach | ~47% of customers use 4+ products, ~83% use 2+ (FY23) | Datadog 10-K FY23 |
| 14.5 | Add-on ARPU lift | Each attached module adds ~15–25% to customer ARR | Bessemer SOTC 2023 |

---

## 15. Minimum commits and overages (usage plans)

| # | Pattern | Quantified value | Source |
|---|---|---|---|
| 15.1 | Enterprise commit structure | Typical 80% committed / 20% overage headroom on usage contracts | Snowflake, Datadog customer contracts (public analyses) |
| 15.2 | Commit utilization | Median 85–95% of committed credits consumed; 10–15% of customers over-commit | Snowflake investor commentary FY23 |
| 15.3 | Overage billing prevalence | ~20–30% of usage-SaaS customers incur overage in a given quarter | Datadog 10-K commentary |
| 15.4 | Overage uplift premium | Overage rates typically 1.0–1.3× committed rate (few SaaS charge penalty multiples) | Public pricing pages |
| 15.5 | True-ups for seat commits | Quarterly true-up on 60–70% of Enterprise seat contracts; annual on rest | Salesforce, Workday MSAs (public) |

---

## 16. Billing reasons — distribution for data generation

| # | Pattern | Quantified value | Source |
|---|---|---|---|
| 16.1 | `subscription_cycle` (renewal) | 70–80% of all charge rows | Stripe Billing aggregate 2023 |
| 16.2 | `subscription_create` | 3–6% of rows | Stripe Billing |
| 16.3 | `subscription_update` (upgrade/downgrade/seat add) | 8–15% — correlates with proration rows | Recurly Insights 2022 |
| 16.4 | `manual` / one-time (services, setup fees) | 2–5% | Paddle 2022 |
| 16.5 | `usage_overage` | 10–20% in usage-heavy SaaS; <2% in seat-only | Datadog, Snowflake operational metrics |

---

## 17. Charge type mix

| # | Pattern | Quantified value | Source |
|---|---|---|---|
| 17.1 | `recurring` charges | 80–90% of total charge rows in seat SaaS | Stripe Billing |
| 17.2 | `metered` charges | 40–60% of rows for usage SaaS (Snowflake, Twilio) | 10-Ks |
| 17.3 | `one_time` (setup, services, add-ons) | 3–8% of rows, 5–12% of revenue | Bessemer SOTC 2023 |
| 17.4 | `proration_credit` / `proration_debit` | 6–12% of rows during active expansion phase | Recurly Insights 2022 |

---

## Dataset generation guidance

For a 3×3 synthetic SaaS dataset, a realistic blend (PLG-leaning mid-market vendor):

- **Tier mix (logos)**: Starter 58% / Pro 30% / Enterprise 12%
- **Tier mix (ARR)**: Starter 12% / Pro 36% / Enterprise 52%
- **Cadence (subs)**: Monthly 55% / Annual 32% / Usage 13%
- **Cadence (ARR)**: Monthly 28% / Annual 47% / Usage 25%
- **List prices**: Starter $29/mo, Pro $99/seat/mo, Enterprise $20K+/yr base
- **Annual discount**: 20% off list
- **Trial**: 14 days, ~40% card-captured, trial→paid 18% overall
- **Proration**: ~10% of rows carry `proration_amount_usd ≠ 0`; median $18, tail to $1,200
- **Billing reasons**: renewal 75% / create 5% / update 10% / overage 7% / manual 3%

---

## Summary

**One-line summary**: Synthetic SaaS billing data should reproduce the PLG "inverted triangle" (Starter dominates logos, Enterprise dominates ARR), put 25–40% of subs on annual (but 50–65% of revenue), blend seat + usage charges consistent with Datadog/Snowflake public ratios, and embed a 14-day trial with ~15–25% conversion and ~10% of rows carrying non-zero proration.

**Top 5 findings**:
1. Logo-to-revenue inversion: Starter ~60% of logos but ~12% of ARR; Enterprise ~12% of logos but ~50% of ARR (OpenView, HubSpot/Datadog 10-Ks).
2. Annual plans are 25–40% of subs yet 50–65% of revenue and churn 2–3× less than monthly (ChartMogul 2023).
3. Usage revenue share is now bimodal — pure usage (Snowflake ~95%, Twilio ~80%, Datadog ~70%) vs seat-only (Zoom/HubSpot <5%); hybrids cluster at 30–50% usage.
4. Trial mechanics dominate conversion: card-captured trials convert 2–3× higher than card-optional; reverse-trials beat pure time-limited by ~2×; 14 days beats 30 days in head-to-head tests.
5. Enterprise contracts follow an 80/20 commit/overage pattern with 85–95% commit utilization and 1.0–1.3× overage multiples — very different charge-type fingerprint than Starter/Pro rows.
