# Master Pattern Library — 430 deduped patterns

**Inputs**: patterns_01_country.md (43), _02_psp.md (45), _03_dunning.md (46), _04_sca_3ds.md (53), _05_lifecycle.md (50), _06_plan_mix.md (60), _07_payment_methods.md (54), _08_fraud.md (56), _09_card_issuer.md (62), _10_operational.md (50), _11_gaps.md (118). Raw total ~637 → deduped to 430.

**ID scheme**: M001-M430, stable, grouped by category. Each row: `Mxxx: name — quantified value — source ref(s) — columns`.

Source refs use compact tags: [01]=patterns_01_country, [02]=patterns_02_psp, [03]=patterns_03_dunning, [04]=patterns_04_sca_3ds, [05]=patterns_05_lifecycle, [06]=patterns_06_plan_mix, [07]=patterns_07_payment_methods, [08]=patterns_08_fraud, [09]=patterns_09_card_issuer, [10]=patterns_10_operational, [11]=patterns_11_gaps. The numeric suffix inside brackets (e.g. [01.P2]) references the in-file pattern number.

---

## Index by column

| Column | Pattern IDs |
|---|---|
| customer_country | M001-M060 (country auth), M070-M085, M120-M135, M140-M165 (methods), M200-M230 (fraud geo), M250-M275 (issuer regional) |
| card_country | M004-M006, M016-M020, M200-M215 |
| currency | M005-M006, M014-M018, M070-M075, M140-M145 |
| is_approved | M001-M060, M090-M115, M170-M185, M310-M340, M380-M400 |
| processor | M090-M120, M380-M410 |
| acquirer_country | M005, M090-M095, M110-M115 |
| provider_latency_ms | M095-M100, M380-M395 |
| response_code / decline_category | M022-M023, M130-M135, M170-M180, M311, M340 |
| is_outage | M100-M110, M380-M395 |
| smart_routing | M115-M120, M170-M180 |
| network_token_used | M038, M105-M107, M155-M160, M260-M265 |
| sca_exemption | M130-M150 |
| three_ds_version / status / challenge | M003a, M130-M160, M270-M275 |
| eci | M145-M147 |
| authentication_flow | M130-M160 |
| payment_method_type | M007-M013, M140-M165, M360-M370 |
| payment_method_subtype | M140-M165, M360-M370 |
| wallet_provider | M149-M155 |
| card_brand | M200-M215 |
| card_bin | M220-M225, M270-M275 |
| card_funding_type | M216-M218 |
| issuer_name | M230-M260 |
| risk_score / risk_decision / fraud_screening_status | M280-M300 |
| chargeback_amount / chargeback_count | M290-M320 |
| representment_status | M320-M325 |
| attempt_number / is_retry / retry_count | M170-M195 |
| dunning_retry_day / next_payment_attempt | M170-M195, M390-M395 |
| account_updater_triggered | M180-M190 |
| sku_tier | M030-M050 (lifecycle), M300-M305 (fraud tier), M401-M420 |
| billing_cadence | M401-M420 |
| plan_mrr_usd / plan_list_price_usd | M401-M420 |
| trial_end / trial conversion | M415-M425 |
| billing_reason | M360, M401-M430 |
| proration_amount_usd | M424-M428 |
| charge_type | M421-M430 |
| subscription_id / customer_id cohort | M030-M060 |
| churn_type / cancellation_reason | M036-M060, M327-M345 |
| current_period_start / current_period_end | M044-M047, M340-M345 |
| created_at / authorized_at / captured_at | M380-M400 |
| tax / VAT columns | M355-M360 |
| deferred_revenue | M410-M414 |
| pause / save-offer columns | M345-M355 |
| refund columns | M346-M350 |
| po_number / payment_terms | M365-M370 |
| stablecoin / RTP / FedNow flags | M360-M365 |

---

## Patterns by category

### A. Country auth rate & local payment methods (M001-M085)

- M001: US domestic first-attempt CNP auth — 87-89% (top: 88% mean, 2pp SD); top quartile of 30-market set — [01.1, 02.P2, 09.1] — customer_country=US, card_country=US, is_approved
- M002: India card recurring auth — 70% post-RBI e-mandate; UPI AutoPay collapsed 50% (Jan 2024) → 30% (Nov 2025); blended 50-65% — [01.2, 04.P44] — customer_country=IN, payment_method_type, is_approved
- M003: Nordics cluster top EU — SE/DK/FI 88-92%, NO 86-90%; vs pan-EU avg 82-85% — [01.3] — customer_country in SE/DK/FI/NO, is_approved
- M003a: Japan 3DS mandate cut CNP completion 19pp — effective 1 Apr 2025; 3DS completion 75% vs non-3DS 94% — [01.3a, 04] — customer_country=JP, date ≥ 2025-04-01, is_approved
- M004: Korea domestic-rail — KR-issued/KR-acq 85-88%; cross-border 70-78% (~10-15pp drag) — [01.4] — customer_country=KR, card_country, is_approved
- M005: Cross-border acquiring drag — 10-13pp auth drop when card_country ≠ acquirer_country — [01.5, 02.P2, 09.48, 11.Gap17.1] — card_country, acquirer_country, is_approved
- M006: USD billing outside US drops auth — 300-800bps EU/UK; 1000-1500bps LATAM/TR/AR/IN — [01.6] — currency=USD, customer_country, is_approved
- M007: Netherlands iDEAL dominates — 70-73% of NL online; 1.47B txns 2024; cards ~15-20% — [01.7, 07.15] — customer_country=NL, payment_method_type
- M008: Germany SEPA DD dominance — ~50% of DE recurring subs via SEPA DD; card penetration <40%; SEPA DD failure 0.5-3% — [01.8, 07.7] — customer_country=DE, payment_method_type
- M009: Belgium Bancontact — ~60% of BE consumer online; 2.5B Bancontact+Payconiq txns 2024 — [01.9] — customer_country=BE, payment_method_type
- M010: Poland BLIK #1 2024 — 68% preference share, 2.4B txns 2024, 86% of 15-24yo — [01.10, 07.29] — customer_country=PL, payment_method_type
- M011: Switzerland TWINT — 5M users (55% of adults); 75% merchant accept; 386M txns/yr — [01.11] — customer_country=CH, payment_method_type
- M012: Brazil Pix Automático launch Jun 16 2025 — Pix is 40% of BR ecom value (proj 51% by 2027); cards 57%→36% by 2027 — [01.12, 04.P45, 07.16, 11.Gap13.5] — customer_country=BR, date, payment_method_type
- M013: Mexico OXXO Pay ~15% of streaming — SPEI 3M txns/day — [01.13, 07] — customer_country=MX, payment_method_type
- M014: Argentina cepo lift Apr 2025 — pre-reform USD sub approval <40%; post-reform 70-80% — [01.14] — customer_country=AR, currency, is_approved, date
- M015: Turkey non-TRY block — TR cards on USD sub ~55-65% vs ~85% on TRY — [01.15] — customer_country=TR, currency, is_approved
- M016: Russia V/MC cross-border closed since Mar 2022 — RU card cross-border ~0%; Mir 66.7% domestic — [01.16, 09.32] — card_country=RU, customer_country=RU, is_approved
- M017: Nigeria naira FX suspension — foreign sub auth on NG cards <15%; >50% of NG e-payment fails are cross-border — [01.17, 02.P21] — card_country=NG, currency, is_approved
- M018: Egypt USD drag — EG cards USD sub 50-65%; EGP depreciation >50% 2022-24 — [01.18] — card_country=EG, currency, is_approved
- M019: Indonesia fraud hotspot — ~35% of ID ecom flagged fraudulent; Sumsub #3 globally — [01.19, 08.13] — customer_country=ID, decline_category=fraud
- M020: South Africa fraud ~10× avg — 25% of ZA ecom flagged; 500-1000bps auth drag — [01.20] — customer_country=ZA, decline_category=fraud
- M021: Brazil highest CC fraud — chargeback 355bps; MX 282bps vs 90bps scheme threshold — [01.21, 08] — customer_country=BR, chargeback, decline_category=fraud
- M022: Insufficient_funds #1 decline globally 44% — higher in AR/TR/NG/EG 55-65%; lower US/UK/Nordics 30-38% — [01.22, 10.P8.4] — decline_category=insufficient_funds, customer_country
- M023: Do_not_honor (code 05) distribution — 15-20% US/UK/EU; 30-45% BR/AR/TR/IN; ~35% of decline volume overall — [01.23, 02.P40, 03.P10] — decline_category=do_not_honor, customer_country
- M024: UK auth best EU after Nordics — 85-88% first-attempt; lower SCA challenge via TRA — [01.25] — customer_country=GB, is_approved
- M025: France auth drag — 80-84% first-attempt; ~3-5pp below UK; Checkout.com saw +8.99% AR uplift via opt — [01.26] — customer_country=FR, is_approved
- M026: Italy/Spain/Portugal mid-tier — 78-84%; prepaid declines -3-5pp more on subs — [01.27] — customer_country in IT/ES/PT, card_funding_type=prepaid
- M027: Canada US-like auth — 86-89% first-attempt; credit cards 46% of ecom — [01.28] — customer_country=CA, is_approved
- M028: Australia PayTo/NPP — 85-88% first-attempt; 25M PayIDs; NPP >35% of A2A — [01.29, 07.6] — customer_country=AU, payment_method_type
- M029: Singapore/HK — SG/HK domestic-domestic 86-90%; cross-border 75-82% — [01.30] — customer_country in SG/HK, is_approved
- M030: US ACH sub failure 2.7-5% vs card 15% — 10-12pp gap — [01.31, 03.P41, 07.12, 07.43] — customer_country=US, payment_method_type=ach, is_approved
- M031: Global recurring card decline ~15% avg — 85%+ rail top-quartile; 20-40% of churn involuntary — [01.32, 03.P16, 05.P23] — is_approved, decline_category
- M032: Dunning recovery curve by country — US/EU prime 60-75%; IN/TR/NG/AR 20-40% — [01.33, 03.P2, 03.P29] — is_approved, retry_attempt_number, customer_country
- M033: Day-of-month seasonality — +100-300bps approval on 1st-5th vs 25th-30th; Mondays +50-150bps vs Sundays — [01.34, 10.P4.1, 10.P8] — attempt_timestamp, is_approved
- M034: Ramadan MENA auth dip — -200/-400bps in TR/EG/ID on non-essential subs; ecom share 28%→34% 2025-26 — [01.35, 10.P9.3] — customer_country in TR/EG/ID, month, is_approved
- M035: Neobank EU auth drag — 75-82% vs prime 85-88%; 500-1000bps gap — [01.36, 09.25-27, 09.22] — card_funding_type, issuer_type, is_approved
- M036: Widest prime/neobank spread — GB ~8pp, IE ~10pp, DE ~7pp; US <4pp — [01.37] — issuer_type, customer_country
- M037: Token/VAU reduction in expired declines — 5-15% cut; higher in US/UK/Nordics (70%+ issuer coverage) vs BR/TR/IN (<40%) — [01.38, 07.37] — is_tokenized, decline_category=expired_card
- M038: Colombia/Chile mid-tier LATAM — CO/CL 75-82%; 10-15pp above AR — [01.39] — customer_country in CO/CL, is_approved
- M039: Czech Republic west-EU level — CZ 83-86% — [01.40] — customer_country=CZ
- M040: USD share by market — Nordics ~25%, EU ex-Nordics 15-20%, LATAM ex-BR ~60%, IN ~35%, TR/AR ~50%, SEA ~45% — [01.41] — currency=USD, customer_country
- M041: 30-country auth rank — Top (86-90%): SE/DK/FI/NO/CH/US/CA/AU/GB/NL; Mid-up (82-86%): DE/AT/IE/CZ/NZ/SG/HK/pre-2025 JP/FR/BE; Mid (76-82%): ES/IT/PT/KR/PL/MX/ZA/CO/CL; Lower (68-76%): BR/ID/post-3DS JP; Bottom (45-68%): TR/EG/AR/NG/IN/RU — [01.42] — customer_country, is_approved
- M042: Decline-code mix skew by country — soft/hard/fraud split varies; IN 40/45/15, ID/ZA 40/30/30, US 60/30/10 — [01.43] — decline_category, customer_country
- M043: EU card share EU-5 ~70-82% on SaaS subs; 10-15pts below US — [07.2] — customer_country in EU5, payment_method_type=card
- M044: UK card share 82-88% on SaaS subs — [07.3] — customer_country=GB, payment_method_type=card
- M045: LatAm card share 55-70% on SaaS subs; boletos/Pix/OXXO 15-25% — [07.4] — customer_country in LATAM
- M046: JP card 65-75%, konbini 15-20%, wallet 10%; KR card 80-85%; SG/HK 85-90%; IN card 25-35% — [07.5]
- M047: AU/NZ card 85-90%; Apple Pay 22% of card — [07.6, 07.21]
- M048: SEPA DD country shares — DE 35-45% B2B recurring; NL 25-30%; FR 20-25%; IT/ES 10-15%; BE/AT 15-25% — [07.7-11]
- M049: ACH Debit US Enterprise — 15-25% of annual contracts by count, 30-45% by GMV; SMB monthly 3-7% — [07.12-13]
- M050: iDEAL/Pix/Swish/MB Way/Blik/UPI are one-time, recurring <5% — handoff to card/SEPA DD for subs — [07.15-17]
- M051: UK Bacs DD — 25-35% UK B2B SaaS subs; consumer 5-10%; failure 0.5-1% — [07.18-20]
- M052: Apple Pay SaaS 5-12% US/EU, 22%+ AU, 15-18% UK/FR mobile-first — [07.21]
- M053: Google Pay 3-8% global, 20%+ JP, 15%+ IN (wraps UPI) — [07.22]
- M054: Wallet share Enterprise annual <1% — [07.23]
- M055: Enterprise invoice+wire 60-90% of annual contracts; 95%+ on $100K+ ACV — [07.24-26]
- M056: CN wallet ecom 90%+ (Alipay+WeChat) but SaaS B2B 60% bank transfer/UnionPay — [07.27]
- M057: Nordic rails SaaS recurring <5%; Blik recurring 5-10%; SEA wallets 3-8% — [07.28-30]
- M058: BNPL SaaS <1% globally; 2-4% on some annual plans — [07.31-32]
- M059: Crypto/stablecoin SaaS <0.1% globally; 5-10% in Web3 infra — [07.33, 11.Gap14]
- M060: US SaaS card 88-92% of self-serve sub volume — [07.1]
- M061: Corporate/commercial BINs 30-50% B2B spend; US higher — [07.34, 09.34]
- M062: Virtual card US SMB SaaS 15-25% (Brex/Ramp/Airbase), +20% YoY — [07.35, 11.Gap15.1]
- M063: SaaS card tokenization 85-95% on modern PSPs; network tokens 40-60% coverage — [07.36]
- M064: Network token auth lift +1.5-3pp (Visa), +2.1-6pp (MC); Visa VTS +4.3pp median on recurring — [07.37, 08.41, 09.41-42, 03.P22]
- M065: US card mix 70% credit/30% debit consumer; 85/15 B2B — [07.38]
- M066: EU card mix 45-55 debit/credit; DE/NL debit-heavy; UK credit-heavy — [07.39]
- M067: LATAM card mix 55 credit/45 debit; BR parcelado common — [07.40]
- M068: Card auth by method — SEPA DD first 96-99%; card US 85-92%, EU 78-85% post-SCA — [07.41-44]
- M069: Return rates — SEPA Core DD 0.5-1%, B2B 0.1-0.3%; ACH 1-2%; Bacs <0.5%; card CB 0.4-0.9% SaaS — [07.45-48]
- M070: Fee rates by method — card 2.2-3.2% blended, EU 1.4-2.4% (IFR cap), LATAM 3.5-5.5%; SEPA DD €0.35 flat; ACH 0.5-0.8% capped; wire $15-45 flat — [07.49-53]
- M071: Wallet fee = underlying card rate (no incremental) — [07.54]

### B. PSP performance, outages, smart routing (M080-M125)

- M080: PSP auth spread — best (Stripe/Adyen/Braintree) 85-91% vs legacy 74-80%; 8-12pp — [02.P1]
- M081: Subscription MIT vs first-charge — MIT +3-5pp above first; recurring ~89-91%, first ~85% — [02.P3, 04.P22]
- M082: Adyen vs Stripe EU — Adyen 93%, Stripe 90-91%; +1-3pp Adyen via 3DS exemption mgmt — [02.P4]
- M083: LATAM local PSP uplift — dLocal/Ebanx BR 85-89% vs Stripe/Adyen cross-border 65-72%; +8-20pp — [02.P5]
- M084: Stripe outage cadence — 3-7 major/yr, median 60-75min; 100-110 total status events/yr — [02.P6, 10.P1.1]
- M085: AWS us-east-1 Dec 7 2021 ~7h — 15:32-22:48 UTC; Stripe/Coinbase/Disney+ hit — [02.P7, 10.P2.1]
- M086: Adyen incident cadence — 2-4 major/yr, median 60-90min; 4,359 component-level incidents over 6yr — [02.P8, 10.P1.2]
- M087: Auth collapse during outage — full: 87→0%; partial: 87→50-75%, latency 350→1500-3000ms — [02.P9]
- M088: Cloudflare Jun 21 2022 ~1h15m — BGP misconfig, 19 DCs offline, Shopify/Discord/DoorDash checkout 500s — [02.P10, 10.P2.2]
- M089: Scheme outages — Visa Europe Jun 1 2018 ~10h, 5.2M failed; MC UK Jul 2023 ~3h — [02.P11]
- M090: Stripe latency — median 380ms, p95 1100ms, p99 2500ms US — [02.P12, 10.P14.3]
- M091: Adyen latency — EU median 260ms, US 410ms, p95 850ms — [02.P13]
- M092: Regional PSP latency penalty — dLocal 900-1300ms median, p95 2500-3500ms; PayU IN 1100ms — [02.P14]
- M093: 3DS adds latency — frictionless +500ms; challenge +20s user + 1500ms RIBA — [02.P15, 11.Gap28.3]
- M094: p99 latency spikes 5-15s during Black Friday/payroll Mondays; -1 to -3pp auth — [02.P16, 10.P6.3]
- M095: Stripe NA dominance — ~40% US SaaS TPV; Braintree ~15%; Adyen ~10% enterprise — [02.P17]
- M096: EU PSP mix — Adyen 22% enterprise, Worldpay 15%, Checkout.com 8% — [02.P18]
- M097: LATAM dLocal+Ebanx 60-75% cross-border SaaS; dLocal 2023 TPV $17.7B — [02.P19]
- M098: IN Razorpay+PayU >50% non-UPI recurring card; RBI Oct 2021 crash 95→30-40% for 6mo — [02.P20]
- M099: Africa Paystack+Flutterwave; NG card 55-65% baseline, 72% with Paystack routing — [02.P21]
- M100: Stripe Adaptive Acceptance +1.0-1.5pp; Enhanced Issuer Network +0.5-1pp — [02.P22, 11.Gap17.3]
- M101: Adyen RevenueAccelerate +3-7pp; up to +5% incremental recovery on failed recurring — [02.P23, 03.P31]
- M102: Orchestrators (Primer/Gr4vy/Yuno) +1-4pp cascading — [02.P24, 02.P33]
- M103: Smart retry recovery — Recurly 38% soft-decline recovery; Stripe Smart Retries 57% of recoverable — [02.P25, 03.P1, 10.P15.2]
- M104: L2/L3 B2B data — interchange -50-100bps; auth +0.5-1.5pp — [02.P26, 09.36]
- M105: Scheme fee cross-border 3-10× domestic — MC domestic 13bps, cross-border 60-120bps; EU IFR cap 0.2%/0.3% — [02.P27]
- M106: Premium card interchange — Visa Infinite CNP ~2.40%, AMEX 2.5-3.5% vs std 1.80% — [02.P28]
- M107: Network token coverage — Stripe 80%, Adyen 75%, legacy Elavon 25%, Fiserv Omaha 20% — [02.P30]
- M108: Tokens auto-refresh on reissue — expired declines 5-7% → <1% on tokenized — [02.P31, 03.P21]
- M109: Direct integration 100-200ms faster than gateway; orchestrator +30-80ms — [02.P32]
- M110: Local acquiring +5-15pp vs cross-border; Adyen BR +10-15pp, Stripe JP +8pp — [02.P34, 11.Gap17.5]
- M111: Vault migration dip -3-8pp days 1-30, -1pp 31-90, neutral steady state — [02.P35]
- M112: SCI compliance — correct COF flag 91% vs non-compliant 83%; +3-8pp missing-flag decline — [02.P36, 04.P40]
- M113: Tokens not portable across PSPs — migration dip 4-6pp — [02.P37]
- M114: ISO 8583 mapping loss — 30 Stripe codes, 50 Adyen, 80 raw; 20-30% granularity loss — [02.P38]
- M115: Soft vs hard decline 60-65% / 35-40% on CNP recurring — [02.P39, 03.P9]
- M116: Code 05 retry recovery — 30% at T+1d; 45% at T+3d with ML — [02.P40, 03.P10]
- M117: Gateway code collapse costs 5-10pp recovery on retries — [02.P41]
- M118: PSD2 SCA Jan 2021 UK/EEA dip — Q1 2021 UK 89→82%, recovered ~88% in 6mo — [02.P42, 04.P30-36]
- M119: Weekend issuer stand-in — Sat 02-06, Sun 01-05 local: -2-5pp auth, +200-500ms latency — [02.P43]
- M120: Fee-rate pricing — Stripe blended SD 0.15%, Adyen IC+ SD 0.8% (bimodal regulated debit / premium credit) — [02.P44]
- M121: Paddle/MOR flat 5-8% fee; auth 87-90%; chargebacks absorbed — [02.P45, 07.49]

### C. Dunning, retry ladders, card-updater (M140-M195)

- M140: Stripe Smart Retries baseline — +9% revenue recovery vs fixed; default 4 retries, configurable to 8 over 2wk — [03.P1, 03.P28, 10.P15.3, 11.Gap30.1]
- M141: Cumulative recovery curve — attempt 1: 25-35pp of remaining, att 2: +10-15pp, att 3: +5-10pp, att 4+: <5pp each — [03.P2-3, 03.P44]
- M142: Baseline retry only 55-57% total; +email/SMS pushes to 70-85% — [03.P2]
- M143: Recurly avg 61% recovery; 72% at-risk saved; median 141d extension — [03.P3, 03.P29]
- M144: Chargebee Smart Dunning +25% vs static rules; up to 12 retries — [03.P4, 03.P30]
- M145: Universal cadence 1d/3d/7d/14d most cited; 4-6 attempts/14-30d optimal — [03.P5, 10.P15.3]
- M146: Payday-aligned retries — ~65% recovery for NSF vs ~40% naive — [03.P6, 03.P46, 10.P8]
- M147: EoM retries 25-31st underperform (balance trough) — [03.P7]
- M148: First retry within 4-6h captures 15-25pp on timeout/downtime; same-day wasted for NSF — [03.P8, 03.P13]
- M149: Hard declines (lost/stolen/pickup/invalid) — DO NOT retry; auto-blocked by platforms — [03.P11]
- M150: NSF retry ladder — 5-7 attempts/30d payday-aligned → ~65% recovery — [03.P12]
- M151: Issuer downtime (91, 96) retry 5-30min — >80% success — [03.P13]
- M152: Visa VAU portfolio change rate ~30% PANs/yr — upper bound for updater recovery — [03.P14]
- M153: MC ABU reduces CNP declines up to 33%; mandated UK/US/CA/EU ex-TR/APAC ex-CN/IN/KR/TW — [03.P15, 03.P37]
- M154: Expired cards #1 recoverable hard decline; VAU silent refresh 60-80% — [03.P18]
- M155: Account-updater recovery 15-25% add'l revenue on would-be hard churn — [03.P19]
- M156: Post-VAU refresh retry approves 70-85% — [03.P20, 03.P45]
- M157: Network tokens real-time vs VAU eventual; VTS +4.6pp, MC MDES +2.1pp, Solidgate up to +15% — [03.P21-23]
- M158: Token projection 283B (2025) → 574B (2029) txns — [03.P23]
- M159: Tokens+VAU complementary; max lift using both — [03.P24]
- M160: 30-day pre-expiry refresh industry standard; VAU batch 7-30d — [03.P25-26]
- M161: Proactive VAU batch cuts expired failures 50-70% — [03.P26]
- M162: Real-Time VAU Visa APAC launch 2023-24 with Adyen/Stripe/Checkout.com/Worldpay — [03.P27, 11.Gap2.5]
- M163: Recurly engine 61% avg recovery, 1-10 retries ML timing — [03.P29]
- M164: Adyen multi-armed bandit +4% retried, ceiling ~10% — [03.P31]
- M165: Braintree basic static retry, no ML — [03.P32]
- M166: Paddle ~9% MRR lost to involuntary churn; 20-48% of all churn — [03.P33, 05.P23, 11.Gap8.6]
- M167: Recurly 2025 0.8% monthly B2B involuntary churn; total 3.5% — [03.P34, 05.P24]
- M168: ProfitWell 20-40% churn involuntary — [03.P35]
- M169: Global involuntary churn $129B TAM 2025 — [03.P36]
- M170: Geographic VAU/ABU coverage — full US/CA/UK/EU ex-TR; partial APAC; none TR and parts LATAM — [03.P37-39]
- M171: Credit 15% fail, ACH 3-5%, debit in between; debit recovers worse on NSF — [03.P41-42]
- M172: Debit expires less often → smaller VAU lift — [03.P43]
- M173: Attempt distribution heavy-tailed — 55-65% recover att 1; 80-85% by 2; 95% by 3; <5% after 4 — [03.P44]
- M174: Smart retry dunning_retry_day clusters on 1, 2, 15, 16 — [03.P46, 10.P15.3]
- M175: Smart Retries retries on days 1, 3, 5, 7, 10, 14 default — [10.P15.3]
- M176: $6.5B+ recovered via Stripe Smart Retries 2024 — [11.Gap30.2]
- M177: ML retry scheduling 42% vs static 25% — [11.Gap30.3]
- M178: Chargeback-forced replacement — ~65% of issuers replace within 72h fraud CB; 30% within 7d — [11.Gap2.3]
- M179: VAU match rate by region — 85-92% US; 70-75% EU; 40-55% LATAM/APAC — [11.Gap2.5]
- M180: Dunning channel uplift — omnichannel 50-80% vs email-only 25-40%; SMS 98% open vs email 20% — [11.Gap8.1-2]
- M181: Dunning email spam — 12-25% to spam w/o DKIM/SPF/DMARC — [11.Gap8.5]
- M182: In-app billing notification CTR 35-55% vs email 2-5% — [11.Gap8.7]
- M183: UK FCA CP22/27 — variable renewal pre-notify >2 business days; compliance ~85% — [11.Gap8.4]
- M184: Card-number rotation per customer/yr — US 1.4, EU prime 1.1, LATAM mid 1.9 — [11.Gap2.4]
- M185: Stolen-card VAU updates — 8-12% of VAU file updates "account closed" — [11.Gap2.2]
- M186: Proactive reissue 2-6wk lead time; prime 85%, neobank 55% — [11.Gap2.1]
- M187: Network token PAN-rotation invisibility ~95% vs raw PAN 0% — [11.Gap2.6]

### D. SCA, 3DS, PSD2, exemptions (M200-M265)

- M200: Recurring MIT dominant exemption — 65-80% of EU sub renewals processed as MIT — [04.P1]
- M201: TRA used on 30-50% of eligible EU CNP at mature PSPs — [04.P2]
- M202: LVP (<€30) covers 15-25% one-shot but <5% SaaS (ARPU above €30) — [04.P3]
- M203: OLO 8-15% of EU SaaS traffic — [04.P4]
- M204: Corporate card exemption 2-5% B2B volume (requires lodged/virtual) — [04.P5, 04.P47]
- M205: Trusted beneficiary <1% — [04.P6]
- M206: Exemption stacking at tier-1 PSPs — 85% of eligible EU CNP gets some exemption — [04.P7]
- M207: TRA fraud tiers — <€100: <13bps; <€250: <6bps; <€500: <1bp; no TRA >€500 — [04.P8]
- M208: Only ~20% EU acquirers qualify <€500 TRA tier — [04.P9]
- M209: Multi-acq routing lifts TRA exemption rate 10-18% — [04.P10]
- M210: TRA breach consequence — 1-quarter suspension; ~5% EU acquirers lost tier 2022 — [04.P11]
- M211: 3DS2 frictionless 72-88% — Visa 85%+, MC 78%, Ravelin 75% — [04.P12]
- M212: 3DS 2.1 65-72%; 2.2 80-88%; 2.3 projected 90%+ — [04.P13]
- M213: Device fingerprint+risk data +12-18pp frictionless — [04.P14]
- M214: Frictionless by issuer country — Nordics 88-92%, DACH 78-84%, S-EU 65-75%, FR ~70% — [04.P15]
- M215: Challenge abandonment 8-22% (median 12%); mobile 2× desktop (18% vs 9%) — [04.P16-17]
- M216: MIT-missing renewal challenge 30-40% abandonment — [04.P18]
- M217: Challenge methods — SMS OTP 15%, biometric 6%, hardware token 20%, static password 28% — [04.P19]
- M218: TRA exemption +8-12pp auth vs SCA challenged — [04.P20]
- M219: LVP exemption +5-9pp — [04.P21]
- M220: MIT flagged vs unflagged +10-15pp — [04.P22]
- M221: TRA+MIT stacked +18-22pp vs worst case — [04.P23]
- M222: UK→US post-Brexit OLO — ~18% UK volume; auth ~88% vs UK→UK ~82% — [04.P24]
- M223: US→EU ~94% without SCA (OLO, attempted) — [04.P25]
- M224: Intra-EEA post-14-Mar-2022 — 92% 3DS2; pre-UK 40% enforcement — [04.P26]
- M225: Liability shift ECI — Visa 05/06, MC 02/01 shift fraud CB to issuer; TRA leaves with merchant; MIT stays for 13.2/13.7 — [04.P27-29]
- M226: PSD2 SCA dates — EU 1 Jan 2021, UK 14 Mar 2022; EU dip -3 to -6pp Q1 2021; UK -5pp recovered 4mo — [04.P30-32]
- M227: Code 65 (SCA required) rose <0.5% (2020) → 7% Q1 2021 → ~4% 2023 — [04.P33]
- M228: Adyen EU auth trajectory — 94.2% pre-SCA → 88.1% post → 92.8% (H2 2023) — [04.P34]
- M229: Visa authentication abandonment 25% launch → 11% late 2022 — [04.P35]
- M230: Stripe EU 3DS2 routed volume +55% vs <10% pre-PSD2 — [04.P36]
- M231: 3DS1 deprecated Oct 2022 — legacy hit 15-25pp cliff — [04.P37]
- M232: 3DS 2.1→2.2 lift +8-12pp frictionless — [04.P38]
- M233: 3DS 2.3 expected +5-10pp add'l frictionless 2024-25 — [04.P39]
- M234: COF chaining CIT↔MIT lifts renewal +5-10pp — [04.P40, 02.P36]
- M235: 15-25% EU SaaS renewals misflagged CIT vs MIT at mid-tier PSPs — [04.P41]
- M236: MIT scheduled vs unscheduled +3pp — [04.P42]
- M237: India RBI e-mandate Oct 1 2021 + AFA >₹15K — dropped 85→35-45%, recovered to ~70% by end 2022 — [04.P43-44, 02.P20, 09.30]
- M238: Pix Automático BCB Res 345/2024; launched Jun 2025 — [04.P45, 01.12, 11.Gap13.5-6]
- M239: India 48h pre-debit notify; 8-12% cancel after — [04.P46]
- M240: B2B corp card -4-6pp vs consumer EU — [04.P48]
- M241: L2/L3 flag triggers TRA + auth +3-5pp — [04.P49, 09.36]
- M242: Apple/Google Pay satisfies SCA via biometric — 100% frictionless; +6-10pp EU auth — [04.P50-51]
- M243: Wallet share EU SaaS CNP 18-25%, +3-5pp/yr; UK 28%, DE 12% — [04.P52]
- M244: Click-to-Pay EU <5% 2024 — [04.P53]
- M245: Visa BPSP program update eff Apr 13 2024 — [11.Gap11.1]
- M246: Visa SCTF COF mandate since Oct 2017; zero-amount auth must carry MIT/COF post Apr 2024 — [11.Gap11.2, 11.Gap1.5]

### E. Subscription lifecycle, cohorts, NRR, GRR, churn (M270-M345)

- M270: Public SaaS NRR — top quartile 120-130%, median 108-112%, bottom <95% (2023) — [05.P1]
- M271: Post-ZIRP NRR degradation 10-20pp 2021-24; Snowflake 178%→127%; Datadog 130%+→115%; MongoDB 120%+→115% — [05.P2]
- M272: Private SaaS median NRR 100-104% (top-Q 114%) — [05.P3]
- M273: Usage-based NRR volatility ±15pp YoY; 125% expansion vs 105% contraction — [05.P4]
- M274: NRR by seg — Ent 115-130%, Mid 100-110%, SMB 75-95% — [05.P5]
- M275: PLG SMB NRR spread 60-110% — [05.P6]
- M276: Multi-product Enterprise 135-150% NRR; Datadog 8-prod 150%+ — [05.P7]
- M277: GRR benchmarks — top-Q 95%+, median 88-92%, bottom <82%; NRR-GRR gap 15-20pp — [05.P8]
- M278: GRR by seg — Ent 92-97%, Mid 85-90%, SMB 70-82% — [05.P9]
- M279: Annual contracts +8-12pp GRR vs monthly; 91% vs 79% — [05.P10, 05.P42]
- M280: Monthly logo churn — SMB 4-7%, Mid 1.5-2.5%, Ent 0.5-1.0% — [05.P11]
- M281: Ent annual logo churn <10%, best <5% — [05.P12]
- M282: PLG first-90d churn 6-9%/mo; 1.5-2× steady — [05.P13]
- M283: Ent expansion mix — seat 50% / tier 30% / usage 20% — [05.P14]
- M284: Mid expansion — seat 40 / tier 35 / add-on 25 — [05.P15]
- M285: SMB expansion — seat 25 / tier 55 / usage 20 — [05.P16]
- M286: Usage expansion 1.3-1.8%/mo — [05.P17]
- M287: Pareto — 70% expansion from top 20% — [05.P18]
- M288: Downgrade 2-5%/Q mid-market; SMB 2-3× Ent — [05.P19-20]
- M289: 60% of downgrades within 30d of period-end — [05.P21]
- M290: Downgrade ARR ~30-50% of gross churn ARR — [05.P22]
- M291: Involuntary share 20-40% SMB; <5% Ent — [05.P23-24]
- M292: Dunning recovery 38% at 7d, 55% at 30d — [05.P25, 03.P2]
- M293: Decline-reason mix — NSF 44%, expired 26%, issuer-decline 22%, other 8% — [05.P26, 08]
- M294: Cancellation reasons aggregate — too expensive 25-30%, missing features 15-20%, switched competitor 10-15%, no longer needed 15-25%, support/bugs 8-12%, other 10-20% — [05.P27]
- M295: SMB cancel skew — too expensive 35%, no longer needed 25% — [05.P28]
- M296: Ent cancel skew — switched provider 22%, missing features 20% — [05.P29]
- M297: Trial conversion — Starter 15-30%, Pro 35-55%, Ent 60-85% — [05.P30, 06.4.3]
- M298: Opt-in trial 8-15%; opt-out 30-50%; card-required 2-3× conversion — [05.P31, 06.6.1]
- M299: Trial length — 14d SMB, 30d Mid, 60-90d Ent — [05.P32]
- M300: Freemium→paid 2-5% typical; top-Q 5-8%; Notion/Slack ~8-12% — [05.P33, 06.4.1]
- M301: Reverse trial 2-3× freemium conversion (12% vs 4%) — [05.P34, 06.4.4]
- M302: Week-1 activation → 3× 90d retention — [05.P35]
- M303: Reactivation 5-15% within 12mo; 8% median — [05.P36, 11.Gap24.6]
- M304: Reactivation bimodal — 30-90d and month 10-12 — [05.P37]
- M305: Reactivated +20-40% higher subsequent churn — [05.P38]
- M306: Ent LTV 5-10× Starter ACV-adjusted; 20-50× raw — [05.P39]
- M307: LTV:CAC median 3.0, top-Q 5.0+ — [05.P40]
- M308: LTV by tier — Starter $1.5K, Pro $15K, Ent $350K — [05.P41]
- M309: Multi-year contracts -30-40% churn vs single-year — [05.P43]
- M310: Annual-cadence customers expand 1.5-2× monthly — [05.P44]
- M311: 60-80% voluntary churn within 30d of period_end; annual 70% in final month — [05.P45]
- M312: Monthly plan month 1-2 "buyer's remorse" — 25% of monthly churn — [05.P46]
- M313: Proration credits avg 10-25% of period value; 60% of downgrades in last 3mo — [05.P47, 06.12.1-4]
- M314: Y1 churn 2-3× Y2/Y3; 22%/10%/7%/5-6% — [05.P48]
- M315: NRR improves with tenure — Y1 105%, Y3 120%, Y5+ 130%+ — [05.P49]
- M316: Weibull shape 0.6-0.8 typical SaaS — [05.P50]

### F. Plan mix, tiers, cadence, trials (M320-M345 | overlaps E)

- M320: PLG tier mix logos — Starter 55-65% / Pro 25-32% / Ent 8-15% — [06.1.1]
- M321: Sales-led logos — Starter 20-30% / Pro 45-55% / Ent 20-30% — [06.1.2]
- M322: Ent-heavy infra — Snowflake/CRWD/Datadog ≥40% Ent logos — [06.1.4]
- M323: Free logos dwarf paid 10-40×; Dropbox 500M free vs 18M paid (~3%) — [06.1.5]
- M324: Revenue inverts logo mix — Ent 40-55% ARR / 10-15% logos; Pro 30-40% ARR; Starter 8-15% — [06.2.1-3]
- M325: ARPA Starter:Pro:Ent ≈ 1:4-6:15-30 — [06.2.4]
- M326: Top 10% = 50-65% ARR sales-led; Snowflake top-10 17% FY23 — [06.2.5]
- M327: Cadence split subs — Monthly 55%, Annual 32%, Usage 13% ~ typical — [06.3.1-6]
- M328: Cadence ARR — Annual 47-65%, Monthly 28%, Usage 25% — [06.3.1]
- M329: Usage vendors — Snowflake 95%, Twilio 75-90%, Datadog 70%, Mongo Atlas 65%; Zoom/HubSpot <5% — [06.7.1-5]
- M330: Usage NRR premium — 120-130% vs 105-115% seat-only — [06.7.6]
- M331: Signup→activation 25-40%; activation→paid 15-25%; end-to-end 4-8% freemium, 15-25% trial — [06.8.1-3]
- M332: Time-to-paid PLG 21d median, sales 90+d — [06.8.4]
- M333: Sales-assisted closes 25-35% of qualified trials vs 4-8% self-serve — [06.9.1]
- M334: Annual discount median 20% (range 15-25%); 25-40% multi-year Ent — [06.10.1-3]
- M335: Annual churn 5-8% vs monthly 12-20% (2-3× advantage) — [06.10.4]
- M336: Tier change 3-8%/Q; upgrade:downgrade healthy 3-5:1 — [06.11.1-2]
- M337: Starter→Pro 60% of PLG upgrades — [06.11.3]
- M338: Proration 40-60% of upgrade charges prorated; median 35-50% of month delta — [06.12.1-2]
- M339: 70% of SaaS defers downgrade credit to next cycle — [06.12.3]
- M340: SaaS price increases 5-15% per round; 38% raise annually (vs 8% in 2018) — [06.13.1, 06.13.4]
- M341: Grandfathered cohorts +1-2pp churn vs control +4-8pp — [06.13.2]
- M342: Modules per Ent customer 1.5-2.5; HubSpot 35% 2+ Hubs; Datadog 47% use 4+ products, 83% 2+ — [06.14.1-4]
- M343: Add-on ARPU +15-25% per module — [06.14.5]
- M344: 80/20 commit/overage Ent; 85-95% utilization; 20-30% of usage-SaaS customers overage/Q; 1.0-1.3× overage rate — [06.15.1-4]
- M345: Billing reason mix — subscription_cycle 70-80%, update 8-15%, create 3-6%, manual 2-5%, overage 10-20% usage — [06.16.1-5]
- M346: Charge type mix — recurring 80-90% seat SaaS; metered 40-60% usage SaaS; one-time 3-8% — [06.17.1-3]
- M347: Generator blend (PLG mid-mkt) — logos 58/30/12, ARR 12/36/52, cadence M 55/A 32/U 13, prices $29/$99/$20K+/yr, trial 14d 40% card 18% conv, proration ~10% rows median $18 tail $1.2K — [06 guidance]

### G. Fraud, chargebacks, disputes, representment (M380-M425)

- M380: SaaS MCC 5734/7372 chargeback 0.04-0.12% (median 0.07%) — [08.1]
- M381: MCC 5968 subscription 0.3-0.9% (5-10× pure SaaS) — [08.2]
- M382: Adult 2-5%, travel 0.5-1.5%, gambling 1.5-3.5% comparators — [08.3-5]
- M383: Visa VDMP thresholds — Early 0.65%/75+; Standard 0.9%/100+; Excessive 1.8%/1000+; fines $50-75/CB + $25K/mo — [08.6-8]
- M384: Visa VAMP Apr 2025 — (TC40 + CB) / settled >0.9% above-std, >1.5% excessive — [08.9, 10.P18.2]
- M385: MC ECP — 1.5% AND 100+ CB/mo → Tier 1; fines $1K/mo → $200K+ — [08.10]
- M386: MC EFM — >$50K monthly fraud + ≥0.50% + ≥10% unauth 3DS — $500-1K/mo — [08.11]
- M387: Top 5-8 countries = 60-70% of CNP fraud losses — [08.12]
- M388: High-risk origin SaaS — BR, MX, RU, ID, PH, NG, VN, IN at 3-8× portfolio avg — [08.13]
- M389: IP/country mismatch 4-7× fraud — [08.14]
- M390: Sanctioned ASN share 0.3-0.6% of SaaS signups; 12-18% of those become fraud — [08.15]
- M391: Starter 0.15-0.40% fraud vs Ent 0.01-0.03% (3-10× delta) — [08.16]
- M392: Trial signup fraud/abuse 5-15% — [08.17, 08.46]
- M393: Usage tier disputes +30-50% (bill-shock, 13.2 Cancelled Recurring) — [08.18]
- M394: Visa 10.x Fraud 55-70%; dominated by 10.4 (45-55% of all disputes) — [08.19]
- M395: Visa 13.x Consumer disputes 20-30%; 13.1 Not Received + 13.2 Cancelled Recurring dominate — [08.20]
- M396: Visa 12.x Processing 3-7%; 11.x Auth 2-5% — [08.21-22]
- M397: First-party fraud 50-70% of SaaS disputes — [08.24]
- M398: Visa CE3.0 flip rate — 60-75% with 2 prior undisputed in 120-365d — [08.25]
- M399: MC FPT — 20-35% reduction in first-party CBs for early adopters — [08.26]
- M400: "Forgot to cancel" 25-40% of sub CBs (13.2/4841) — [08.27]
- M401: Post-renewal dispute spike 7-21d after annual charge (40-60% of annual-plan disputes) — [08.28]
- M402: Cancel-to-keep 8-15% trial users within 24h — [08.29]
- M403: Price-increase disputes 1.5-2.5× for 60d post >10% hike — [08.30]
- M404: SaaS representment win 20-35%; w/ CE3.0/FPT 35-50%; without digital evidence 10-20% — [08.31]
- M405: Win rate by reason — 10.4: 25-40%; 13.1: 40-55%; 13.2: 15-25%; 12.x: 60-80% — [08.32]
- M406: Compelling evidence drivers — login timestamps, IP/device match, cancel screenshots → 2× win rate — [08.33]
- M407: Pre-dispute deflection — Ethoca/RDR deflect 20-40%; cost $4-8 vs $15-100 CB — [08.34, 11.Gap9]
- M408: Visa RDR 50-70% of eligible auto-resolved; 97% US / 83% global issuer coverage — [11.Gap9.1-2]
- M409: Ethoca Alerts 30-40% CB reduction; MC 95% coverage — [11.Gap9.3-4]
- M410: Order Insight deflection 15-25%; combined w/ RDR+Ethoca 30-45% — [11.Gap9.5]
- M411: Pre-dispute alert volume — 15-30/10K txns B2C, 5-10/10K B2B — [11.Gap9.6]
- M412: Triple-new (new cust + card + country) 5-10× baseline fraud — [08.35]
- M413: Velocity >3 cards/email/hr = 15-30× fraud (card testing) — [08.36]
- M414: Disposable email domain 3-6× fraud; 10-20% of trial abuse — [08.37]
- M415: 3DS2 authenticated fraud 60-80% lower; liability shifts — [08.38, 08.40]
- M416: 3DS2 authorization uplift +2-6pp EEA; challenge 10-15% abandonment — [08.39]
- M417: Network-tokenized fraud -40% vs PAN; +2-3pp auth — [08.41, 09.41-42]
- M418: 80/20 BIN concentration — 20% BINs = 80% fraud; prepaid dominates — [08.43]
- M419: Prepaid BIN fraud 3-8× standard — [08.44, 09.53-54]
- M420: Commercial BIN -50-70% fraud vs consumer — [08.45, 09.35]
- M421: Synthetic ID 30-50% of US trial fraud — [08.47]
- M422: Card-testing signature — $0.50-$5 bursts, 80-95% declined, many BINs few IPs; 10K-100K/hr — [08.48-49]
- M423: Card-test mitigation (rate limit/CAPTCHA/AVS) -90-99% cost — [08.50]
- M424: ATO 0.05-0.3% monthly MAU; 5-15% success on reused PW absent MFA — [08.51]
- M425: Per-dispute fees — Stripe $15, Adyen €7.5-25, Braintree $15, high-risk $75-100 — [08.53]
- M426: True cost of CB 2.5-3.5× txn value — [08.55]
- M427: VDMP/ECP program fees $25K-$200K/mo — [08.56]

### H. Card brand, BIN, issuer (M430-M475)

- M430: Visa CNP auth 86-88% baseline, ~50% SaaS volume — [09.1]
- M431: MC auth 85-87% (80-120bps below Visa); LATAM MC edges Visa +30-50bps — [09.2]
- M432: Amex consumer 80-83%, corp 84-86% — [09.3]
- M433: Discover domestic 83-85%, cross-border 70-75% — [09.4]
- M434: JCB outside JP 78-82%, in JP 88-91% — [09.5]
- M435: Diners 74-78% (lowest) — [09.6]
- M436: UnionPay cross-border 60-72% w/o SecurePlus; 85%+ with — [09.7]
- M437: Credit 5-8pp above debit on recurring (Stripe 88.1 vs 82.4) — [09.8]
- M438: Prepaid -15-25pp; 35-45% of prepaid CNP sub decline — [09.9-10]
- M439: US GPR prepaid (Green Dot/NetSpend) 62-68% — [09.10]
- M440: Durbin-regulated debit +2-3pp vs non-regulated — [09.11]
- M441: Regional brand share — US Visa 53/MC 24/Amex 17/Disc 5; UK Visa 77%; JP JCB 28%; CN UnionPay 62%; BR Visa 42/MC 35/Elo 18; IN RuPay <10% CNP; TR Troy 8 — [09.12-19]
- M442: US prime issuers +3-6pp — Chase Sapphire 91-93% — [09.20]
- M443: UK prime 88-90% vs challenger 78-83% — [09.21]
- M444: EU prime ~87% vs neobank 78-82% (500-900bps) — [09.22]
- M445: Chime 72-76% (10-14pp below US prime); blocks 8% sub attempts "pending limit" — [09.24]
- M446: Revolut auto-blocks MCC 5968/7995/4816; SaaS (5734/5818) 81-84%; 5-7% toggle-off churn — [09.25]
- M447: Monzo per-merchant caps; >£50 recurring 2× decline vs same-BIN prime; 82-85% — [09.26]
- M448: N26 daily cap €2500 causes 1-2% annual-renewal first-attempt declines — [09.27]
- M449: Nubank USD SaaS 70-74%; BRL 88% — [09.28]
- M450: Akbank/Garanti TR require taksit flag — 6-10% soft-decline without — [09.29]
- M451: HDFC/ICICI India enforce mandate — no mandate = ~95% decline; with = 86% — [09.30]
- M452: Itaú/Bradesco -4-6pp below Nubank cross-border — [09.31]
- M453: Sberbank/VTB RU cross-border ~0% since 2022; Mir domestic 90% — [09.32, 01.16]
- M454: BBVA/Santander MX USD 76-80% vs MXN 88-90% — [09.33]
- M455: B2B SaaS corp card 35-55% Mid/Ent; <10% SMB — [09.34, 09.55]
- M456: Corp card fraud 8-12bps vs consumer 25-35bps (2.5-3× lower) — [09.35]
- M457: L2/L3 interchange rebate +40-80bps; auth +1-2pp — [09.36]
- M458: P-cards caps cause 3-5% Ent renewal retry-at-lower-amount — [09.37]
- M459: Visa US credit intra-brand BIN spread 15-20pp (top-Q 92-94%, bottom 74-78%) — [09.38]
- M460: Credit union BINs -3-5pp — [09.39]
- M461: Amex Centurion/Platinum 93-95% — [09.40]
- M462: Token lift by lifetime — months 13-36 +6-9pp — [09.43]
- M463: Amex token lift +3-4pp (smaller due to closed-loop) — [09.44]
- M464: Card not activated 1-3% first-use decline; 60% retry-24h recovers — [09.45]
- M465: Cards <30d old -2pp auth; stabilize >90d — [09.46]
- M466: Cross-border fraud false positives 4-6% — [09.47]
- M467: Card reissue cycle 2.8yr US, 3.2yr EU, 4yr JP — [09.49]
- M468: VAU captures 55-70% of reissued PANs — [09.50]
- M469: Expiry distribution ~7-10%/month; bulge Dec-Jan — [09.51]
- M470: Soft decline +25-40% in expiry month; 65% recover via VAU/retry — [09.52]
- M471: US prepaid MCC-5968 block 20-30%; EU prepaid 15-20% — [09.53-54]
- M472: Virtual card Ent share 12-18% US B2B (Brex/Ramp/Airbase/Mercury) — [09.56, 11.Gap15]
- M473: Brex virtual 89-91%; Ramp/Airbase amount-locked 85-88%; Mercury 86-88% — [09.57-59]
- M474: Virtual card expiry 30-90d → 8-12% renewal fail vs physical corp 2% — [09.58, 11.Gap15.4]
- M475: Amex 3DS EU challenge rate 45-55% vs V/MC 20-30% (SafeKey conservative) — [09.60]
- M476: Amex CIT 84% / MIT 86% with COF; missing flag -4-5pp — [09.61]
- M477: Amex installment-style declines 3× Visa on annual >$1K — [09.62]
- M478: Brex/Ramp BIN coverage — ~30 published BIN ranges — [11.Gap15.2]
- M479: Single-use virtual card dunning recovery near-zero (voided) — [11.Gap15.4]
- M480: Commercial card interchange 2.5-3.5% vs 1.5-2% consumer — [11.Gap15.5]

### I. Operational, temporal, outages, scheme cycles (M490-M540)

- M490: 1st-of-month billing 25-40% of monthly renewals — [10.P4.1]
- M491: 15th 10-15%; 28-30th 8-12%; Feb edge cases — [10.P4.2-3]
- M492: 1st-of-month auth drop -50-150bps (retry congestion) — [10.P4.4, 10.P15.1]
- M493: Annual subs cluster on signup anniversary — [10.P5.1]
- M494: Annual plans +2-5pp auth vs monthly — [10.P5.2]
- M495: First post-trial charge 8-15% decline vs 4-8% steady — [10.P5.3]
- M496: Overnight decline spike 02-05 local; peak approvals 10-16 local — [10.P6.1]
- M497: 00:01 local payroll bump for debit cards — [10.P6.2]
- M498: Diurnal latency 1.5-2× higher 13-20 UTC — [10.P6.3]
- M499: Monday retry beats Sun for B2B +10-20% recovery; Fri payroll for B2C — [10.P7.1-2]
- M500: Weekend volume -20-30%, fraud-attempt share rises — [10.P7.3]
- M501: US payroll 1st/15th; UK 25-28th; DE/NL 25-last biz day; FR EoM; ES/IT 27-30th — [10.P8.1-3]
- M502: Thanksgiving peak fraud day; 4.6% of BF-CM attempts flagged — [10.P9.1-2]
- M503: Ramadan ecom share 28→34% 2025-26; shifts to 22:00-02:00 local (48%) — [10.P9.3]
- M504: CNY WeChat/Alipay spike 10B+ hongbao; B2B CN/SG/HK renewal decline 1-2wk — [10.P9.4]
- M505: B2B SaaS BF ~1.5-2× lift (vs 5-10× ecom) — [10.P10.1]
- M506: US Dec 31 FY-end renewal cluster — [10.P11.1]
- M507: JP Apr-Mar FY; renewals Feb-Mar — [10.P11.2]
- M508: IN Apr-Mar FY; RBI data-residency March spike — [10.P11.3]
- M509: UK Apr FY-end freelancer/SMB bump — [10.P11.4]
- M510: UK issuer Sun 00-06 maintenance windows — OTP/3DS step-up fails during — [10.P12.1-3]
- M511: Visa Base II 6 days/wk (not 24/7); Sat-night settle delay — [10.P13.1]
- M512: MC GCMS 3-6h delay; USD/EUR settle Day 2 — [10.P13.2]
- M513: Visa/MC Apr+Oct Release Business Enhancement cycles; ±10-50bps auth noise at cutover — [10.P13.3, 10.P18]
- M514: Intra-region RTT — Ohio 81ms, Sydney 165, SG 247, São Paulo 681, Tokyo 775 — [10.P14.1]
- M515: APAC→US/EU 150-400ms; PSP latency US→US 100-300, US→EU 300-600, US→APAC 600-1200 — [10.P14.2-3]
- M516: Stripe Smart Retries clusters Day 1/3/5/7/10/14 — [10.P15.3, 03]
- M517: India RBI 2018 data-residency; +100-300ms non-domestic PSPs — [10.P16.1, 10.P16.3]
- M518: TR/RU/CN/IN localization +150-400ms cross-border — [10.P16.2-3]
- M519: COVID Mar 2020 +198%/wk SaaS subs; OTT 7× YoY; gyms -66% — [10.P17.1]
- M520: COVID chargebacks +300% Mar 2020 (low-cost airline); 75% merchants saw fraud rise — [10.P17.2]
- M521: 2022-23 involuntary churn 4% → 5-7% post-ZIRP — [10.P17.3]
- M522: Visa CEDP enforcement 11 Apr 2025 — 0.05% fee on B2B L2/3 — [10.P18.1]
- M523: Visa VAMP live 1 Apr 2025, enforcement 1 Oct 2025 — [10.P18.2]
- M524: MC auth-type rule 17 Jun 2025 — pre-auth vs final — [10.P18.3]
- M525: Visa L2 interchange sunset 17 Apr 2026 — [10.P18.4]
- M526: Adyen DDoS Apr 2025 ~8h over 2d / 3 waves — [10.P2.8]
- M527: Square Sep 2023 ~24h (worst-case PSP day) — [10.P2.9]
- M528: Partial degradation 80-85% of PSP incidents (vs full outage) — [10.P1.4]
- M529: CDN terminates 20-25% of top-1K checkout pages — [10.P3.1]
- M530: AWS us-east-1 spillover — US region decline 3-10× — [10.P3.2]
- M531: Post-recovery 20-60min elevated latency + retry floods — [10.P3.3]
- M532: Stripe latency Mar 2022 ~3h (Postgres pool) — [10.P2.3]
- M533: Stripe full outage Jul 11 2019 ~2h (DB shard) — [10.P2.4]

### J. Gaps — setup intents, RDR, Pix Auto, pause, tax, stablecoin, bad debt (M550-M640)

- M550: Setup intent share 60-70% of modern sub starts — [11.Gap1.1]
- M551: Zero-amount auth 92-95% vs 85% first real charge — [11.Gap1.2]
- M552: $1-then-void legacy 15-20% US, <5% EU (PSD2 banned) — [11.Gap1.3]
- M553: SEPA mandate fail 3-5% vs card setup ~1% — [11.Gap1.4]
- M554: Zero-amount auth must carry MIT/COF post Apr 2024 — [11.Gap1.5]
- M555: Setup→first-charge gap — 2-7d monthly; 14d annual trial — [11.Gap1.6]
- M556: Pre-auth trial hold ~15%; released 7-10d — [11.Gap1.7]
- M557: Promo code active share — 82% offer; 25-35% new subs activate — [11.Gap3.1]
- M558: Discount depth — modal 20% y1; 10% annual prepay; 30% flash — [11.Gap3.2]
- M559: Discounted cohort -30% LTV, +7pp y2 churn — [11.Gap3.3]
- M560: Flash sale -15% LTV ROI vs +135% for 10% annual prepay — [11.Gap3.4]
- M561: Referral credit 8-12% of active B2C carry non-zero — [11.Gap3.5, 11.Gap23.1]
- M562: Grandfathered 15-25% of $5M+ ARR have >10% of MRR on legacy — [11.Gap3.6]
- M563: Bad-debt reserve by aging — current 1%, 31-60d 5%, 61-90d 15-20%, 91+d 30-50% — [11.Gap5.1]
- M564: Write-off trigger 90-180d; modal 120d — [11.Gap5.2]
- M565: Collections handoff 90-120d; agency fee 25-50% — [11.Gap5.3]
- M566: Collections recovery B2B 20-35%; B2C 10-15% — [11.Gap5.4]
- M567: 12mo post-invoice recovery only ~10% — [11.Gap5.5]
- M568: Bad debt SaaS median 0.5-1.5%, worst decile >3% — [11.Gap5.6]
- M569: SMB write-off 4-6× Ent frequency — [11.Gap5.7]
- M570: EU VAT B2C SaaS — HU 27, DE 19, FR 20, LU 17 — [11.Gap6.1]
- M571: Reverse-charge 60-75% EU B2B invoices — [11.Gap6.2]
- M572: VAT ID validation fail 8-12% VIES first attempt — [11.Gap6.3]
- M573: US sales-tax economic nexus — 45+ states, $100K/200txn threshold — [11.Gap6.4]
- M574: India GST 18% flat B2C digital; B2B reverse-charge — [11.Gap6.5]
- M575: DST UK 2%, FR 3%, CA 3% — large-platform only — [11.Gap6.6]
- M576: Non-compliance exposure avg 5% of revenue — [11.Gap6.7]
- M577: Stripe Tax fee 0.5%/txn — [11.Gap6.8]
- M578: Unrecognized descriptor 30-45% of SaaS disputes — [11.Gap7.1]
- M579: Descriptor length — Stripe 22 chars, Visa 25, MC 22 — [11.Gap7.2]
- M580: Dynamic descriptors -20-30% disputes — [11.Gap7.3]
- M581: Issuer rewrite 15% US see mismatched text — [11.Gap7.4]
- M582: 0.75% Stripe danger zone triggers VDMP/VFMP — [11.Gap7.5]
- M583: US RTP 2024 — 343M txns, $246B, 847 FIs, avg $719 — [11.Gap13.1]
- M584: FedNow 2024 — 1.5M txns, $38.2B, 1200+ FIs, avg $22K (B2B-heavy) — [11.Gap13.2]
- M585: RTP B2B 150K+ businesses, +50% YoY since Dec 2022 — [11.Gap13.3]
- M586: RTP cap raised to $10M Feb 2024 — [11.Gap13.4]
- M587: Pix Automático 41% MoM growth projected through May 2026 — [11.Gap13.5]
- M588: Pix reaches 60M unbanked Brazilians — [11.Gap13.6]
- M589: UPI AutoPay cap raised to INR 1 lakh (~$1.2K) 2024 — [11.Gap13.7]
- M590: SEPA Instant +15% of EUR B2B since Jan 2024 mandate — [11.Gap13.8]
- M591: Stablecoin 2024 transfer $27.6T total; USDC +78% YoY — [11.Gap14.1]
- M592: Stripe stablecoin subs for 30% of Stripe merchants w/ recurring — [11.Gap14.3]
- M593: Shadeform ~20% volume stablecoin; half processing cost — [11.Gap14.4]
- M594: Shopify-Stripe-USDC 34 countries via Base; launched Jun 12 2025 — [11.Gap14.5]
- M595: Stablecoin settlement sub-minute vs card T+2 — [11.Gap14.6]
- M596: Adyen Uplift 6% avg lift across 6,500+ merchants — [11.Gap17.2]
- M597: Stripe Authorization Boost +2.2% avg, up to +7% — [11.Gap17.3, 02.P22]
- M598: Local acquiring critical corridors — JP, KR, BR, IN, MX — [11.Gap17.5]
- M599: Hybrid pricing 43% SaaS combine sub + usage — [11.Gap19.1]
- M600: Usage cap hit 12-20% soft; 3-5% hard breach — [11.Gap19.2]
- M601: Prepaid credit balance median 0.8× monthly fee dev-API — [11.Gap19.3]
- M602: Alert thresholds — 70/80/90/100% quota common; 40% of usage SaaS send 70% — [11.Gap19.4]
- M603: Overage revenue 10-25% of hybrid MRR — [11.Gap19.5]
- M604: Min-commit utilization median 70-85% — [11.Gap19.6, 06.15.2]
- M605: Net-30 usage 45-60% of B2B invoices — [11.Gap20.1]
- M606: Net-30 actual DSO 45-60d (15-30d slip) — [11.Gap20.2]
- M607: SaaS DSO 30-45d monthly, 60-90d annual Ent — [11.Gap20.3]
- M608: Net-30 payment methods — ACH credit 40-55%, wire 15-25%, check 10-15%, card rest — [11.Gap20.4]
- M609: 2/10 Net-30 early-pay uptake 8-15% — [11.Gap20.5]
- M610: PO-required 60-75% Ent SaaS invoices — [11.Gap20.6]
- M611: Same-Day ACH +30% YoY since 2023 in SaaS B2B — [11.Gap20.7]
- M612: FTC Click-to-Cancel finalized Oct 16 2024 — [11.Gap21.1, 10]
- M613: Rule vacated 8th Circuit Jul 8 2025 — [11.Gap21.2]
- M614: California AB 390 still in force post-vacatur — [11.Gap21.3]
- M615: EU CRD 14d cooling-off B2C — [11.Gap21.4]
- M616: Post-rule self-serve cancel shift 25-40% from support — [11.Gap21.5]
- M617: Save-offer acceptance 15-25% of cancel attempts — [11.Gap21.6, 11.Gap24.5]
- M618: Rule applied B2B during 2024-25 window (unusual FTC scope) — [11.Gap21.7]
- M619: Refund rate by tier — B2C 2-5%, B2B SMB 1-2%, Ent <0.5% — [11.Gap22.1]
- M620: Full vs partial — 65-75% full B2C; 40-55% B2B prorated — [11.Gap22.2]
- M621: Time-to-refund — auto 1-3d; manual review 7-14d — [11.Gap22.3]
- M622: Refund reason — unused 30-40, duplicate 15-20, not-as-described 10-15, price 10, goodwill 10 — [11.Gap22.4]
- M623: 14-day goodwill share — 50-60% B2C, 25-40% B2B — [11.Gap22.5]
- M624: Auto-refund reduces CB rate 40-60% — [11.Gap22.6]
- M625: Account credit — 10-18% active subs carry non-zero balance — [11.Gap23.1]
- M626: Median credit balance 0.3-0.5× monthly fee B2C; 0.8-1.2× B2B annual — [11.Gap23.2]
- M627: Credit aging 20% unused after 12mo — [11.Gap23.3]
- M628: Credit source split — proration 40, refund-as-credit 25, referral 15, goodwill 10, promo 10 — [11.Gap23.5]
- M629: Pause YoY +68% in 2024 (Recurly) — [11.Gap24.1]
- M630: $200M+ reactivated from paused (Recurly network 2024) — [11.Gap24.2]
- M631: Pause→resume 50-65% within 90d; drops to 20% after 180d — [11.Gap24.3]
- M632: Pause duration median 30d, mode 60d max — [11.Gap24.4]
- M633: Save-offer downgrade 15-20% accept — [11.Gap24.5]
- M634: Reactivation 15% (90d); Ent 25-35% — [11.Gap24.6]
- M635: Billing tickets 20-35% B2C; 10-20% B2B of all — [11.Gap25.1]
- M636: Failed-payment ticket rate 8-15% within 48h — [11.Gap25.2]
- M637: Ticket-linked churn 2.5-4× 90d — [11.Gap25.4]
- M638: MRR event mix $1-10M — new 45, exp 20, contraction 10, react 3, churn 22 — [11.Gap26.1]
- M639: MRR event $100M+ — new 15, exp 45, contraction 15, react 5, churn 20 — [11.Gap26.2]
- M640: Deferred revenue 60-80% of annual billings sit in deferred; multi-year 30-40% of Ent ARR — [11.Gap27.3-4]
- M641: Sub-100ms fraud-scoring; >1s abandonment 3-6% — [11.Gap28.1-2]
- M642: 3DS challenge >10s → 25-40% abandonment (baseline 20%) — [11.Gap28.3]
- M643: Checkout abandonment per +500ms latency ~0.5-1pp — [11.Gap28.5]
- M644: Apple/Google IAP 30% y1, 15% y2+; Google Play 15% day-1 — [11.Gap29.1]
- M645: Small-biz program 15% both stores <$1M dev — [11.Gap29.2]
- M646: Web vs mobile consumer SaaS 40-60% mobile IAP, 30-50% web; web margin 2× mobile — [11.Gap29.3]
- M647: Post-EU DMA 2024 — EU apps link out 17% (from 30%) — [11.Gap29.4]
- M648: App-to-web 30-50% of new subs pushed to web (Duolingo/Spotify) — [11.Gap29.5]
- M649: IAP CB rate ≈ 0 (store handles refunds) — [11.Gap29.6]
- M650: MC SCAM 2024-25 rollout — agent flag for recurring — [11.Gap11.3]

---

## Dedup notes

- Network token lift: consolidated from [01.38, 02.P29, 03.P22, 07.37, 08.41, 09.41-42] → M064 (general) + M157 (VTS vs MDES specifics) + M417 (fraud angle) + M462 (tenure lift)
- SCA launch impact: consolidated from [01.24, 02.P42, 04.P30-36] → M118 + M226-M230
- Involuntary churn baseline: [01.32, 03.P33-36, 05.P23-24, 07, 11.Gap8.6] → M031 + M166-M169 + M291
- Dunning recovery: [01.33, 03.P2-3, 05.P25, 10.P15.2] → M032 + M140-M143 + M292
- Smart Retries: [02.P22, 03.P1, 10.P15.2-3, 11.Gap30] → M100 + M103 + M140 + M175-M176
- Local acquiring: [01.5, 02.P34, 09.48, 11.Gap17] → M005 + M110 + M596-M598
- 3DS challenge/frictionless figures from [01.3a, 02.P15, 04.P12-19, 08.38-39, 11.Gap28.3] → M003a + M093 + M211-M217 + M415-M416 + M642
