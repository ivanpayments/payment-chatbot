# Selected 150 — Generator Encoding List

Scope: 150 highest-impact patterns for the SaaS billing synthetic-data generator. Target dataset: 1-parent SaaS at ~$2B ARR, 14 PSPs, 30 countries, ~100K billing attempts, 171-column schema (156 airline-era + 15 SaaS adds).

Format per row:
- **Sxxx** [Master ID] Pattern — quantified target | columns | encoding hint | source

Distribution actual: Country 25 / PSP 15 / Dunning 15 / SCA 15 / Lifecycle 15 / Plan mix 15 / Methods 10 / Fraud 15 / Card/BIN 10 / Operational 10 / Gaps 5. Total 150. Dated shock events: 10.

---

## A. Country auth — 25 patterns

- **S001** [M001] US baseline CNP auth — target 88% approval on US-issued cards on US acquirer | `customer_country`, `card_country`, `processor`, `is_approved` | Bernoulli(0.88) for US×US×domestic-acq | [01.P1]
- **S002** [M002] UK baseline CNP auth — 85–87% post-SCA (14 Mar 2022) | `customer_country='GB'`, `is_approved`, `three_ds_version` | Bernoulli(0.86); force 3DS2 on 90% of CIT | [01.P2]
- **S003** [M003] DE auth — 82–85%, SEPA DD lifts to 94% | `customer_country='DE'`, `payment_method_type`, `is_approved` | if SEPA_DD → 0.94 else 0.83 | [01.P3, 07]
- **S004** [M004] FR auth — 80–83% (conservative issuers, high 3DS challenge) | `customer_country='FR'`, `three_ds_challenge` | Bernoulli(0.82); challenge_rate=0.35 | [01.P4]
- **S005** [M005] Nordics auth — 90–93% (mobile BankID, high frictionless) | `customer_country in ('SE','NO','DK','FI')`, `three_ds_frictionless` | Bernoulli(0.91); frictionless=0.92 | [01.P5]
- **S006** [M006] IT/ES/PT auth — 76–80% (higher challenge drop-off) | `customer_country in ('IT','ES','PT')`, `is_approved` | Bernoulli(0.78) | [01.P6]
- **S007** [M007] BR domestic auth — 78–82% via Pix/boleto; card-only 72–75% | `customer_country='BR'`, `payment_method_type` | if Pix → 0.95; if card → 0.73 | [01.P8, 07]
- **S008** [M008] MX auth — 70–75% card; OXXO voucher pay-rate 58% within 72h | `customer_country='MX'`, `payment_method_type`, `invoice_paid_within_72h` | OXXO: 58% paid, else expire | [01.P9]
- **S009** [M009] AR post-cepo-lift (Apr 2025 FX liberalization) — auth improves +8pp | `customer_country='AR'`, `transaction_date >= 2025-04-14` | pre: 0.62, post: 0.70 | [01.P10, 11.gap]
- **S010** [M010] IN UPI AutoPay collapse — Jan 2024 peak ~72% → Nov 2025 ~38% due to mandate bank opt-outs | `customer_country='IN'`, `payment_method_type='upi_autopay'`, `transaction_date` | piecewise linear Jan-24 0.72 → Nov-25 0.38 | [01.P11, 11.gap]
- **S011** [M011] IN card recurring e-mandate — 70% auth >₹15,000 requires AFA every charge | `card_country='IN'`, `amount_inr`, `sca_exemption` | if amt>15000 → AFA, auth=0.70 | [01.P12]
- **S012** [M012] JP 3DS2 mandate 1 Apr 2025 — auth dip -7pp Q2 2025, recovers Q4 | `customer_country='JP'`, `three_ds_version`, `transaction_date` | pre 0.88, Apr-Jul 2025: 0.81, recover 0.87 by Dec | [01.P13, 10]
- **S013** [M013] TR auth — closed-loop lira, 68% auth on cross-border, 85% domestic | `customer_country='TR'`, `card_country` | domestic: 0.85, xborder: 0.68 | [01.P14]
- **S014** [M014] NG auth — 55–62%, CBN FX windowing | `customer_country='NG'` | Bernoulli(0.58) | [01.P15]
- **S015** [M015] EG auth — 60–65%, USD scarcity | `customer_country='EG'` | Bernoulli(0.62) | [01.P16]
- **S016** [M016] RU corridor closed post-sanctions — 100% decline from EEA acquirer | `customer_country='RU'` | is_approved=0; decline_code='country_blocked' | [01.P17]
- **S017** [M017] Cross-border drag — 10–13pp auth reduction vs domestic acquiring | `card_country != processor_country` | multiply approval P by 0.87 | [01.P18, 02]
- **S018** [M018] USD-billing drag on non-US card — +5pp currency-conversion declines | `currency='USD'`, `card_country!='US'` | subtract 5pp | [01.P19]
- **S019** [M019] AU/NZ auth — 87–89% | `customer_country in ('AU','NZ')` | Bernoulli(0.88) | [01.P20]
- **S020** [M020] CA auth — 86–88%; Interac not for SaaS recurring | `customer_country='CA'` | Bernoulli(0.87) | [01.P21]
- **S021** [M021] NL iDEAL dominant — 70% of NL checkout via iDEAL, 96% success | `customer_country='NL'`, `payment_method_type` | 70% iDEAL; success 0.96 | [01.P22, 07]
- **S022** [M022] PL BLIK — 42% share, 94% auth on mobile push | `customer_country='PL'`, `payment_method_type='blik'` | 0.42 share, 0.94 auth | [07.P12]
- **S023** [M023] CH TWINT — 35% of CH CNP, 93% auth | `customer_country='CH'`, `payment_method_type='twint'` | 0.35 share, 0.93 auth | [07.P13]
- **S024** [M024] Decline code distribution (global baseline) — do_not_honor 36%, insufficient_funds 22%, expired 8%, lost/stolen 4%, 3DS_required 6%, other 24% | `decline_code` | categorical draw on decline branch | [01.P30]
- **S025** [M025] Local acquiring preference — same-country BIN×acquirer = +9pp auth lift | `card_country == processor_country` | add 9pp approval | [02.P8, 01.P31]

## B. PSP — 15 patterns

- **S026** [M080] Stripe baseline spread — +1 to +2pp auth above median due to ML routing | `processor='stripe'` | add 1.5pp to country baseline | [02.P1]
- **S027** [M081] Adyen enterprise — +2 to +3pp auth, lowest cross-border drag | `processor='adyen'` | add 2.5pp | [02.P2]
- **S028** [M082] Braintree — par or -0.5pp vs Stripe | `processor='braintree'` | baseline | [02.P3]
- **S029** [M083] Checkout.com — +1pp EU strong, US -1pp | `processor='checkout_com'` | regional tilt | [02.P4]
- **S030** [M084] dLocal LatAm — +8pp on BR/MX/CO vs cross-border acquirers | `processor='dlocal'`, `customer_country in LATAM` | add 8pp on LatAm | [02.P5]
- **S031** [M085] Ebanx LatAm — parity with dLocal, stronger in BR Pix | `processor='ebanx'` | add 8pp on LatAm | [02.P6]
- **S032** [M086] Razorpay IN — only Indian rails with e-mandate | `processor='razorpay'`, `customer_country='IN'` | IN routing preference | [02.P7]
- **S033** [M088] AWS us-east-1 outage 7 Dec 2021 — 7hr Stripe/Braintree degraded, +40pp timeout | `is_outage=True`, `processor in ('stripe','braintree')`, `outage_window=2021-12-07 10:30–17:30 UTC` | inject outage rows | [02.P15, 10]
- **S034** [M089] Cloudflare BGP 21 Jun 2022 — 1.5hr Stripe checkout failures | `is_outage`, `outage_window=2022-06-21 06:27–08:00 UTC`, `processor='stripe'` | inject outage | [02.P16]
- **S035** [M090] Adyen DDoS Apr 2025 — 2hr EU auth -15pp | `processor='adyen'`, `outage_window=2025-04-18 09:00–11:00 UTC` | inject shock | [02.P17, 10]
- **S036** [M091] Provider latency baseline — Stripe p50=220ms, Adyen p50=190ms, dLocal p50=340ms | `provider_latency_ms` | per-processor lognormal | [02.P20]
- **S037** [M092] Smart Retries uplift — Stripe Smart Retries +11pp on recovered attempts | `processor='stripe'`, `retry_index>0` | recovered+=0.11 | [02.P25, 03]
- **S038** [M093] Network token routing — PSP-level tokens +3–5pp auth | `network_token_used=True` | add 4pp | [02.P29, 09]
- **S039** [M094] Multi-PSP cascade — 2nd PSP retry recovers 18–25% of 1st-PSP fails | `retry_processor != initial_processor` | recovery=0.22 | [02.P30]
- **S040** [M095] PSP fee spread — Stripe 2.9%+$0.30 vs Adyen interchange++; Adyen 30–60bp cheaper at enterprise | `psp_fee_usd` | processor-specific formula | [02.P33]

## C. Dunning / retry / VAU — 15 patterns

- **S041** [M140] Retry ladder standard — 1d / 3d / 7d cadence recovers 28–35% | `retry_index`, `retry_offset_days` | 3 retries at 1/3/7 days | [03.P1]
- **S042** [M141] Smart retry timing — weekday+payday aligned +4pp over fixed | `retry_day_of_month`, `payday_flag` | schedule retries on 1/15 | [03.P2]
- **S043** [M142] First retry recovery — 12–18% of initial fails recover on retry 1 | `retry_index=1`, `is_approved` | Bernoulli(0.15) | [03.P3]
- **S044** [M143] Retry 2 recovery — 8–10% | `retry_index=2` | Bernoulli(0.09) | [03.P4]
- **S045** [M144] Retry 3 recovery — 4–6% | `retry_index=3` | Bernoulli(0.05) | [03.P5]
- **S046** [M145] Visa VAU adoption — 72% of US issuers, 45% EU | `network_token_used`, `card_updater_used`, `card_country` | prob by region | [03.P10, 09]
- **S047** [M146] Mastercard ABU — 68% US, 40% EU | `card_brand='mastercard'`, `card_updater_used` | prob by region | [03.P11]
- **S048** [M147] VAU auto-update recovery — 55–65% of expired cards auto-updated | `decline_code='expired'`, `vau_hit=True` | 60% of expireds get new card silently | [03.P12]
- **S049** [M148] Network token expiration refresh — 95% silent refresh on token rotation | `network_token_used`, `token_refreshed=True` | 95% | [03.P15]
- **S050** [M149] Account Updater timing — ABU monthly batch, VAU real-time | `updater_type` ∈ {batch, realtime} | Stripe/Adyen real-time, mid-tier batch | [03.P16]
- **S051** [M150] Involuntary churn share — 30–40% of total churn is payment-failure-driven | `churn_type='involuntary'` | 35% of churners | [03.P20, 05]
- **S052** [M151] Dunning email open rate — 48% day-1, 22% day-3, 12% day-7 | `dunning_email_opened`, `retry_index` | declining Poisson | [03.P22]
- **S053** [M152] In-product banner vs email — banner recovers +6pp | `dunning_channel`, `is_approved` | +6pp if channel='in_app' | [03.P23]
- **S054** [M153] Recovered revenue TAM — $129B SaaS leakage globally (Recurly 2023) | (metric, not row) | report KPI | [03.P30]
- **S055** [M154] Max retry cap — 4th+ retries have <2% lift, cease at 21 days | `retry_index<=3`, `days_since_first_fail<=21` | cap retries at 3 | [03.P32]

## D. SCA / 3DS2 — 15 patterns

- **S056** [M200] EU SCA enforcement 1 Jan 2021 — -3 to -6pp auth Q1 2021 | `customer_country in EU`, `transaction_date` | pre/post step | [04.P30]
- **S057** [M201] UK SCA enforcement 14 Mar 2022 — -5pp immediate, recovered 4mo | `customer_country='GB'`, `transaction_date` | pre/post step | [04.P32]
- **S058** [M202] MIT share of EU recurring — 65–80% flagged as MIT exempt | `sca_exemption='mit'`, `billing_reason='subscription_cycle'` | 0.72 of renewals | [04.P1]
- **S059** [M203] TRA exemption share — 30–50% of eligible CIT | `sca_exemption='tra'` | 0.40 of eligible | [04.P2]
- **S060** [M204] LVP exemption share — 5% of SaaS (ARPU typically >€30) | `sca_exemption='lvp'`, `amount_eur<30` | 0.05 | [04.P3]
- **S061** [M205] OLO exemption — 8–15% of EU traffic, 94% non-auth pass | `sca_exemption='olo'`, `card_country not in EEA` | 0.12 | [04.P4, P25]
- **S062** [M206] 3DS2 frictionless rate — 72–88% | `three_ds_frictionless`, `three_ds_version='2.2.0'` | 0.82 | [04.P12]
- **S063** [M207] Challenge abandonment — 12% median, mobile 18% vs desktop 9% | `three_ds_challenge=True`, `challenge_abandoned`, `device_type` | mobile 0.18, desktop 0.09 | [04.P16, P17]
- **S064** [M208] TRA uplift — +8 to +12pp auth vs challenge | `sca_exemption='tra'` | add 10pp | [04.P20]
- **S065** [M209] MIT chaining uplift — COF transaction ID present +5-10pp | `cof_transaction_id_chained=True` | add 7pp | [04.P40]
- **S066** [M210] ECI distribution — Visa 05 (full) 70%, 06 (attempted) 25%, 07 (none) 5% | `eci`, `card_brand='visa'` | categorical | [04.P27, P28]
- **S067** [M211] India RBI e-mandate effective 1 Oct 2021 — SaaS auth dropped 85%→40% | `card_country='IN'`, `transaction_date>=2021-10-01` | pre 0.85, post 0.42 | [04.P43, P44]
- **S068** [M212] 3DS1 deprecated Oct 2022 — legacy merchants -15 to -25pp cliff | `three_ds_version='1.0.2'`, `transaction_date>=2022-10-15` | force 2.x | [04.P37]
- **S069** [M213] Wallet biometric = SCA satisfied — Apple/Google Pay 100% frictionless | `payment_method_type in ('apple_pay','google_pay')`, `three_ds_frictionless=True` | force frictionless | [04.P50, P51]
- **S070** [M214] Soft decline '65' SCA-required — 4% steady in EU CNP | `decline_code='65_sca_required'`, `customer_country in EU` | 0.04 of declines | [04.P33]

## E. Lifecycle / NRR / churn — 15 patterns

- **S071** [M270] NRR benchmark top-quartile — 120%+ mid-market SaaS | (metric) | cohort target | [05.P1]
- **S072** [M271] NRR median — 106–110% | (metric) | cohort target | [05.P2]
- **S073** [M272] GRR benchmark — 90–94% top quartile | (metric) | cohort target | [05.P3]
- **S074** [M273] Monthly logo churn Starter — 5–7% | `sku_tier='starter'`, `is_cancelled_month` | 0.06 | [05.P5]
- **S075** [M274] Monthly logo churn Pro — 2–3% | `sku_tier='pro'` | 0.025 | [05.P6]
- **S076** [M275] Monthly logo churn Enterprise — 0.5–1% | `sku_tier='enterprise'` | 0.008 | [05.P7]
- **S077** [M276] First-month churn spike — 2.5× baseline in month 1 | `tenure_months=1` | multiply churn by 2.5 | [05.P10]
- **S078** [M277] Annual vs monthly cadence churn — annual 40% lower gross | `billing_cadence`, `churn_type` | annual×0.6 | [05.P12]
- **S079** [M278] Expansion MRR share — 25–35% of new MRR for healthy SaaS | `mrr_change_reason='expansion'` | 0.30 share of new | [05.P15]
- **S080** [M279] Contraction MRR — 5–8% of active MRR annually | `mrr_change_reason='contraction'` | 0.07 | [05.P16]
- **S081** [M280] Reactivation rate — 8–12% of churned return within 12mo | `reactivation_flag`, `prior_churn_date` | 0.10 | [05.P18]
- **S082** [M281] Trial-to-paid — 18–30% SaaS median (PLG) | `trial_converted`, `plan_type='trial'` | 0.22 | [05.P20, 06]
- **S083** [M282] Voluntary vs involuntary churn split — 65/35 | `churn_type` | categorical | [05.P25]
- **S084** [M283] Save-offer acceptance — 15–25% of cancel-intent | `save_offer_presented`, `save_accepted` | 0.20 | [05.P30, 11.gap]
- **S085** [M284] Cohort retention curve — month 3 retention 70%, month 12 55%, month 24 48% | `cohort_month`, `active_flag` | exponential decay with floor | [05.P35]

## F. Plan mix / tier / cadence — 15 patterns

- **S086** [M320] Inverted triangle SaaS — Starter 60% logos / 15% ARR, Pro 30% / 40% ARR, Enterprise 10% / 45% ARR | `sku_tier`, `arr_usd` | weighted assignment | [06.P1]
- **S087** [M321] Billing cadence split — 55% monthly / 40% annual / 5% multi-year | `billing_cadence` | categorical | [06.P5]
- **S088** [M322] Annual discount — 17% avg (2 months free) | `annual_discount_pct` | 0.17 | [06.P6]
- **S089** [M323] Trial length — 14-day default PLG, 30-day enterprise | `trial_length_days`, `sku_tier` | by tier | [06.P10]
- **S090** [M324] Seat-based scaling — avg 4.2 seats Starter, 28 Pro, 180 Enterprise | `seat_count`, `sku_tier` | lognormal by tier | [06.P15]
- **S091** [M325] Usage-based add-on share — 35% of Pro+ have metered component | `has_usage_billing`, `sku_tier in ('pro','enterprise')` | 0.35 | [06.P20]
- **S092** [M326] Proration on upgrade — 95% prorated | `proration_amount_usd`, `plan_change_type='upgrade'` | compute prorated | [06.P25]
- **S093** [M327] Downgrade effective next cycle — 90% | `plan_change_type='downgrade'`, `effective_date=next_cycle_start` | 0.90 | [06.P26]
- **S094** [M328] Multi-product attach — 28% of Pro have 2+ products | `product_count>=2`, `sku_tier='pro'` | 0.28 | [06.P30]
- **S095** [M329] Enterprise custom pricing — 80% off-list | `sku_tier='enterprise'`, `list_price_match=False` | 0.80 | [06.P32]
- **S096** [M330] Self-serve vs sales-led — Starter 95% self-serve, Enterprise 5% | `acquisition_channel`, `sku_tier` | rule | [06.P35]
- **S097** [M331] Free tier conversion — 2–5% free-to-paid | `plan_type='free'`, `converted_flag` | 0.03 | [06.P38]
- **S098** [M332] Plan change frequency — 18% of customers change plan annually | `plan_change_count_ytd>=1` | 0.18 | [06.P42]
- **S099** [M333] Multi-currency billing — 7 currencies cover 85% (USD/EUR/GBP/BRL/INR/AUD/JPY) | `currency` | top-7 share | [06.P45]
- **S100** [M334] PLG funnel blend — 70% PLG logos / 30% sales-led logos, but 40/60 ARR split | acquisition & ARR columns | blend rule | [06.P50]

## G. Payment methods — 10 patterns

- **S101** [M360] SEPA DD DE/NL/AT — 40–55% of B2B SaaS, 94% success | `payment_method_type='sepa_dd'`, `customer_country in ('DE','NL','AT')` | share+success | [07.P1]
- **S102** [M361] Bacs DD UK — 15–20% of B2B SaaS, 96% success | `payment_method_type='bacs_dd'`, `customer_country='GB'` | share+success | [07.P2]
- **S103** [M362] iDEAL NL — 70% checkout share, 96% success | [07.P3] (see S021)
- **S104** [M363] Pix BR instant — 95% success, settles <10s | `payment_method_type='pix'`, `settlement_time_sec<10` | 0.95 | [07.P5]
- **S105** [M364] Pix Automático launch 16 Jun 2025 — BR recurring rail, target 35% of BR SaaS recurring by end-2025 | `payment_method_type='pix_automatico'`, `transaction_date>=2025-06-16`, `customer_country='BR'` | ramp 0→0.35 | [07.P6, 11.gap]
- **S106** [M365] OXXO voucher MX — 25% of MX checkout, 58% pay within 72h, rest expire | `payment_method_type='oxxo'`, `voucher_status` | pay-rate 0.58 | [07.P8]
- **S107** [M366] UPI AutoPay IN — peaked Jan 2024 ~72% SaaS share, Nov 2025 ~38% (bank opt-outs) | `payment_method_type='upi_autopay'` | time curve | [07.P10]
- **S108** [M367] Apple Pay share EU — 18%, UK 28%, DE 12% | `payment_method_type='apple_pay'`, `customer_country` | by country | [07.P20]
- **S109** [M368] Google Pay share — 8–15% avg, Android-heavy markets higher | `payment_method_type='google_pay'` | 0.11 | [07.P21]
- **S110** [M369] ACH US — 12% of US B2B, 99% success but 3-day settlement | `payment_method_type='ach'`, `customer_country='US'`, `settlement_days=3` | share+latency | [07.P25]

## H. Fraud / chargeback — 15 patterns

- **S111** [M380] CNP fraud rate SaaS — 8–20 bp | `is_fraud`, `chargeback_reason` | Bernoulli(0.0014) | [08.P1]
- **S112** [M381] Chargeback rate — 30–60 bp in SaaS | `chargeback_flag` | 0.004 | [08.P2]
- **S113** [M382] Visa VAMP launch 1 Apr 2025 / enforcement 1 Oct 2025 — excessive threshold 1.5% fraud+disputes | `vamp_status`, `transaction_date` | flag after 1 Oct | [08.P5, 10]
- **S114** [M383] Mastercard ECP/EFM thresholds — 100 chargebacks/mo AND 1% ratio | `mc_ecp_status` | per-merchant monthly | [08.P6]
- **S115** [M384] Reason code mix — 10.4 fraud 55%, 13.1 recurring 15%, 13.2 cancelled 10%, other 20% | `chargeback_reason` | categorical | [08.P10]
- **S116** [M385] CE3.0 representment win rate — 65% for SaaS with evidence | `representment_win`, `has_ce3_evidence=True` | 0.65 | [08.P20]
- **S117** [M386] RDR auto-refund — 30% of eligible disputes resolved pre-CB | `rdr_resolved=True` | 0.30 | [08.P25]
- **S118** [M387] Ethoca alerts — 20% of card-fraud caught pre-dispute | `ethoca_alert_received=True` | 0.20 of fraud | [08.P26]
- **S119** [M388] Friendly fraud share — 30–40% of chargebacks | `chargeback_category='friendly_fraud'` | 0.35 | [08.P30]
- **S120** [M389] Velocity fraud pattern — >3 attempts in 10min same BIN = fraud 40× baseline | `velocity_flag`, `bin_10min_count>3` | flag & elevate | [08.P35]
- **S121** [M390] IP-country mismatch — 5× fraud multiplier | `ip_country != card_country` | 5× | [08.P40]
- **S122** [M391] New-account first-7-day fraud — 8× multiplier | `account_age_days<=7` | 8× | [08.P42]
- **S123** [M392] Trial abuse — 2–4% of free trials are synthetic | `trial_abuse_flag` | 0.03 | [08.P45]
- **S124** [M393] Stripe Radar block rate — 0.5–1.5% of attempts blocked pre-auth | `radar_blocked=True` | 0.01 | [08.P50]
- **S125** [M394] Chargeback-to-fraud lag — median 45 days, p95 90 days | `chargeback_date - transaction_date` | lognormal days | [08.P52]

## I. Card / BIN / issuer — 10 patterns

- **S126** [M430] Card brand mix global — Visa 52%, MC 32%, Amex 9%, Disc 3%, JCB/UPI 4% | `card_brand` | categorical | [09.P1]
- **S127** [M431] Amex B2B skew — Amex 18% of Enterprise vs 6% Starter | `card_brand='amex'`, `sku_tier` | tier weighting | [09.P5]
- **S128** [M432] Prepaid card decline rate — 2× non-prepaid on recurring | `card_funding='prepaid'`, `billing_reason='subscription_cycle'` | 2× decline | [09.P10]
- **S129** [M433] Debit vs credit auth — debit -2pp on recurring (NSF heavier) | `card_funding='debit'` | -2pp | [09.P12]
- **S130** [M434] Chime (neobank) decline pattern — weekend+payday clustering | `issuer='chime'`, `day_of_week in (Sat,Sun)` | clustering | [09.P20]
- **S131** [M435] Nubank BR — 25% of BR card recurring, auth 80% | `issuer='nubank'`, `customer_country='BR'` | 0.25 share | [09.P22]
- **S132** [M436] Brex/Ramp corporate — 40% of US tech SaaS Enterprise | `issuer in ('brex','ramp')`, `sku_tier='enterprise'` | 0.40 | [09.P25]
- **S133** [M437] Network token auth lift by brand — Visa VTS +4pp, MC MDES +3pp | `network_token_used`, `card_brand` | brand-specific lift | [09.P30]
- **S134** [M438] BIN country — US card + non-US billing = 10pp drag | `card_bin_country`, `customer_country` | cross-country drag | [09.P35]
- **S135** [M439] Card expiration distribution — 22% expire in next 12mo | `card_exp_within_12mo` | 0.22 | [09.P40]

## J. Operational / temporal — 10 patterns

- **S136** [M490] First-of-month billing surge — 35% of all renewals on day 1 | `transaction_day_of_month=1`, `billing_reason='subscription_cycle'` | skew 35% day-1 | [10.P1]
- **S137** [M491] 15th-of-month secondary peak — 18% | `transaction_day_of_month=15` | 0.18 | [10.P2]
- **S138** [M492] US Thanksgiving week dip — B2B charges -40% Wed-Fri | `transaction_date in thanksgiving_week` | 0.60× | [10.P5]
- **S139** [M493] Chinese New Year APAC dip — CN/HK/TW/SG -30% for 7 days | `transaction_date in cny_week`, `customer_country in APAC` | 0.70× | [10.P6]
- **S140** [M494] Ramadan MENA pattern — +15% night-time spend, -10% day | `customer_country in MENA`, `hour_of_day` | shift distribution | [10.P7]
- **S141** [M495] FY-end spike US Dec — Enterprise +25% renewals in Dec | `sku_tier='enterprise'`, `transaction_month=12`, `customer_country='US'` | +25% | [10.P10]
- **S142** [M496] Scheme rule cycle — Visa/MC changes ship Apr & Oct; expect behavior shifts those months | `transaction_date in (Apr, Oct)` | release-window flag | [10.P15]
- **S143** [M497] CEDP (Consumer Experience Data Program) Visa 2023 — auth-fee pressure on merchants <75% auth | `cedp_flag`, `merchant_auth_rate<0.75` | flag | [10.P18]
- **S144** [M498] Weekend auth drop — Sat/Sun -1 to -2pp vs weekday (issuer fraud caution) | `day_of_week in weekend` | -1.5pp | [10.P22]
- **S145** [M499] Timezone-aligned fraud windows — 02:00–05:00 local = 3× fraud rate | `local_hour in (2,3,4,5)` | 3× fraud | [10.P25]

## K. Gaps — 5 patterns

- **S146** [M550] Setup Intent / zero-amount auth — 25% of CIT in EU use $0 auth hold for SCA | `is_setup_intent=True`, `amount_usd=0` | 0.25 of EU CIT | [11.gap setup]
- **S147** [M551] FTC Click-to-Cancel rule 16 Oct 2024 → vacated 8 Jul 2025 — window of forced easy-cancel, +12% voluntary churn US | `customer_country='US'`, `transaction_date in [2024-10-16, 2025-07-08]`, `churn_type='voluntary'` | multiply 1.12 in window | [11.gap ftc]
- **S148** [M552] Stablecoin subscription rail — <0.5% SaaS but growing; USDC payment channel | `payment_method_type='stablecoin_usdc'` | 0.004 | [11.gap stablecoin]
- **S149** [M553] Pause instead of cancel — 20–30% of cancel-intent accept pause offer | `pause_offer_accepted`, `subscription_status='paused'` | 0.25 | [11.gap pause]
- **S150** [M554] Bad debt write-off — 0.6–1.2% of booked ARR written off annually (uncollected after dunning exhaustion) | `writeoff_flag`, `days_since_first_fail>90` | 0.009 of ARR | [11.gap bad_debt]

---

## Dated shock events included (10)

1. **2021-01-01** — EU SCA hard enforcement (S056)
2. **2021-10-01** — India RBI e-mandate effective (S067)
3. **2021-12-07** — AWS us-east-1 outage (S033)
4. **2022-03-14** — UK SCA enforcement (S057)
5. **2022-06-21** — Cloudflare BGP outage (S034)
6. **2022-10-15** — 3DS1 deprecation (S068)
7. **2024-10-16 → 2025-07-08** — FTC Click-to-Cancel window (S147)
8. **2025-04-01** — Japan JCA 3DS2 mandate + Visa VAMP launch (S012, S113)
9. **2025-04-18** — Adyen DDoS (S035)
10. **2025-06-16** — Pix Automático launch (S105); plus India UPI AutoPay decay curve Jan 2024 → Nov 2025 (S010); Argentina cepo lift Apr 2025 (S009)

---

## Category distribution summary

| Category | Count |
|---|---|
| A. Country auth | 25 |
| B. PSP | 15 |
| C. Dunning / retry / VAU | 15 |
| D. SCA / 3DS2 | 15 |
| E. Lifecycle / NRR / churn | 15 |
| F. Plan mix / tier / cadence | 15 |
| G. Payment methods | 10 |
| H. Fraud / chargeback | 15 |
| I. Card / BIN / issuer | 10 |
| J. Operational / temporal | 10 |
| K. Gaps | 5 |
| **Total** | **150** |
