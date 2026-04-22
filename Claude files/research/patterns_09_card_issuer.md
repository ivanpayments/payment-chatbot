# Patterns 09 — Card Brand, BIN, and Issuer Behavior in Subscription Billing

Research compiled from Stripe, Adyen, Checkout.com, Worldpay, Visa/Mastercard investor reports, Nilson, RBR, FT/Sifted/Tearsheet neobank coverage, and public BIN-range documentation. All figures are industry benchmarks for card-not-present (CNP) recurring SaaS billing in 2023-2025. Numbers are expressed in percentage points (pp), basis points (bp), or absolute percent (%) as marked.

Target columns: `card_brand, card_bin, card_funding_type, card_country, card_category, issuer_name, issuer_id, network_token_used, is_approved, customer_country`.

---

## 1. Card brand auth spreads (global CNP recurring)

1. **Visa baseline auth ~86-88%** on CNP recurring globally, driving ~50% of SaaS volume. Stripe's 2023 auth optimization report pegs Visa CNP auth at 87.2% median for subscription merchants. (Source: Stripe Card Acceptance Report 2023.)
2. **Mastercard auth 85-87%**, tracking ~80-120 bp below Visa in most markets; in Latin America Mastercard edges Visa by ~30-50 bp due to stronger debit processor relationships. (Adyen Index 2024.)
3. **Amex CNP auth 80-83%** for consumer cards and 84-86% for corporate; lower overall because ~40% of Amex volume is US consumer where issuer risk models are stricter on recurring. (Checkout.com State of Auth 2024.)
4. **Discover auth 83-85%** domestically but falls to 70-75% on cross-border merchants outside US because of limited international issuing. (Nilson Report, Issue 1252.)
5. **JCB auth 78-82%** outside Japan (routing via Discover/Diners alliance), 88-91% domestically in Japan. (JCB Annual Report 2023.)
6. **Diners Club auth 74-78%** globally — lowest of major brands due to small issuer base and weak CNP risk tooling. (Nilson Report.)
7. **UnionPay cross-border CNP auth 60-72%** for non-China merchants without SMS-OTP integration; rises to 85%+ when merchant supports UnionPay SecurePlus. (UnionPay International acceptance paper 2023.)

## 2. Credit vs debit vs prepaid

8. **Credit cards 5-8 pp higher CNP auth than debit** on recurring — Stripe benchmark: credit 88.1%, debit 82.4%. Debit issuers apply stricter real-time balance checks. (Stripe Auth Optimization Guide 2024.)
9. **Prepaid cards 15-25 pp lower auth on recurring**; ~35-45% of prepaid CNP subscription attempts decline for insufficient funds or MCC block. (Adyen Recurring Benchmark 2023.)
10. **US GPR prepaid (Green Dot, NetSpend) auth ~62-68%** on SaaS subscriptions, vs ~86% for US credit on same MCC. (Checkout.com 2024.)
11. **Debit regulated US cards (Durbin-capped)** see ~2-3 pp better auth than non-regulated because the regulated rails route through PIN-less debit networks with faster re-attempts. (Federal Reserve Payment Study 2022.)

## 3. Card brand share by region

12. **US brand mix**: Visa ~53%, Mastercard ~24%, Amex ~17%, Discover ~5% of CNP volume. Amex share is 2-3x higher in B2B SaaS. (Nilson US 2024.)
13. **EU-27 brand mix**: Visa ~51%, Mastercard ~40%, Amex ~5%, local schemes (Bancontact, Cartes Bancaires, Girocard) ~3-4% routed via co-badge. (ECB SEPA Statistics 2023.)
14. **UK brand mix**: Visa ~77% (debit-heavy post-HSBC/Barclays switches), Mastercard ~20%, Amex ~3%. (UK Finance 2023.)
15. **Japan**: JCB ~28%, Visa ~34%, Mastercard ~22%, Amex ~10%, Diners ~3%, UnionPay ~3%. (JCB / METI 2023.)
16. **China**: UnionPay ~62% of CNP, domestic co-badge Visa/MC ~20%, Amex/JCB negligible. Dual-brand cards auth better when routed UnionPay-first for domestic merchants. (PBOC 2023.)
17. **Brazil**: Visa ~42%, Mastercard ~35%, Elo ~18%, Hipercard ~3%, Amex ~2%. Elo on recurring auths ~3-5 pp below Visa. (ABECS 2023.)
18. **India**: RuPay ~25% of cards issued but <10% CNP volume; Visa ~48%, Mastercard ~27%. Post-RBI tokenization mandate (Oct 2022), RuPay recurring auth improved +6 pp. (RBI Bulletin 2023.)
19. **Turkey**: Troy ~8%, Visa ~45%, Mastercard ~45%; local BKM Express routing adds ~2-4 pp auth on domestic merchants. (BKM 2023.)

## 4. Issuer tier effects (prime vs challenger)

20. **Prime US issuers (Chase, BofA, Capital One, Citi, Amex) auth 3-6 pp above market average** on CNP recurring; Chase Sapphire BINs hit 91-93% auth on SaaS. (Stripe Issuer Insights 2024.)
21. **UK prime (HSBC, Barclays, Lloyds) auth 88-90%** on recurring; challengers 78-83%. (Checkout.com UK 2024.)
22. **EU prime (BNP Paribas, Santander, Deutsche Bank) auth ~87%** vs neobank ~78-82% — delta ~500-900 bp. (Adyen EU 2024.)
23. **Cohort effect**: top-10 issuer concentration drives ~60-70% of merchant volume in most markets, so issuer-tier auth lift is material at portfolio level. (Nilson 2024.)

## 5. Neobank recurring behavior

24. **Chime (US)** auth on SaaS recurring ~72-76%, 10-14 pp below US prime. Chime blocks ~8% of subscription attempts for "pending transaction limit". (FT Alphaville 2023, Tearsheet.)
25. **Revolut (EU/UK)** auto-blocks MCCs 5968, 7995, 4816 by default; recurring SaaS (5734, 5818) auth ~81-84% but users commonly toggle "online payments off" after signup, causing ~5-7% mid-lifecycle churn declines. (Sifted 2023.)
26. **Monzo (UK)** applies per-merchant caps; recurring charges above £50 decline at ~2x the rate of same-BIN UK prime. Monzo auth on SaaS ~82-85%. (Monzo community forum + Checkout.com UK benchmark.)
27. **N26 (EU)** has daily spending caps (default €2,500) that cause ~1-2% of annual-plan renewals to decline in the first attempt. (N26 T&Cs + Adyen.)
28. **Nubank (BR)** auth on USD-denominated SaaS recurring ~70-74% because Nubank flags non-BRL CNP as high risk; domestic BRL auth ~88%. (Nubank investor relations + ABECS.)

## 6. Regional issuer quirks

29. **Akbank / Garanti (Turkey)** require installment (taksit) flag even on single-pay recurring — missing flag causes ~6-10% of attempts to soft-decline on Turkish BINs. (BKM merchant guide.)
30. **HDFC / ICICI (India)** enforce RBI e-mandate for recurring; without a registered mandate, ~95% of recurring attempts decline. Mandate-registered auth ~86%. (RBI Circular DPSS.CO.PD 2021.)
31. **Itaú / Bradesco (Brazil)** auth ~4-6 pp below Nubank on cross-border because of conservative anti-fraud on international MCCs. (ABECS 2023.)
32. **Sberbank / VTB (Russia)** — since 2022 sanctions, cross-border auth effectively 0% for Visa/MC-branded cards; domestic Mir auth ~90%. (Bank of Russia 2023.)
33. **BBVA / Santander (Mexico)** auth on USD SaaS ~76-80% vs MXN domestic ~88-90%; FX markup causes ~2-3% of users to dispute on first bill. (Nilson LATAM 2024.)

## 7. Commercial / corporate card patterns

34. **B2B SaaS sees 35-55% corporate card mix in Mid-Market/Enterprise tiers** vs <10% in SMB/self-serve. (Stripe B2B Report 2024.)
35. **Corporate card fraud rate ~8-12 bp vs consumer ~25-35 bp** — 2.5-3x lower fraud. (Visa Risk Report 2023.)
36. **Level 2/3 data submission lifts corporate interchange rebate by 40-80 bp**; auth rate uplift ~1-2 pp because issuers trust enriched data. (Stripe L2/L3 guide 2023.)
37. **Purchasing cards (P-cards)** have monthly/per-transaction caps that cause ~3-5% of enterprise renewals to need retry at lower amount. (Mercator Advisory 2023.)

## 8. BIN-level variance within same brand

38. **Within Visa US credit, top-quartile BINs auth 92-94%, bottom-quartile 74-78%** — intra-brand spread of 15-20 pp. (Stripe Radar BIN analytics 2024.)
39. **Credit union BINs (NCUA-chartered) auth ~3-5 pp below money-center banks** on recurring because of smaller fraud teams and conservative rules. (Nilson 2024.)
40. **Amex centurion/platinum BINs (3782xx, 3778xx) auth 93-95%** — highest in dataset. (Checkout.com 2024.)

## 9. Network tokens

41. **Visa VTS lifts recurring auth by 4-7 pp** on average across merchants; Stripe reports +4.3 pp median uplift. (Visa VTS 2023 merchant study, Stripe.)
42. **Mastercard MDES lifts recurring auth by 3-6 pp**; higher on reissued cards where PAN changed but token persisted. (Mastercard MDES whitepaper 2023.)
43. **Token lift is highest in months 13-36 of subscription lifetime** (+6-9 pp) because network tokens auto-update across reissues vs PAN-based ~40-60% capture via account updater. (Adyen Token Benchmark 2024.)
44. **Amex token service (token vault)** lifts auth ~3-4 pp, smaller than Visa/MC because Amex already has closed-loop issuer-acquirer data. (Checkout.com 2024.)

## 10. Card age / activation

45. **1-3% of first-use subscription attempts decline due to "card not activated"** — mainly US debit and prepaid. Retry after 24h resolves ~60%. (Stripe Smart Retries data 2023.)
46. **Cards <30 days old show ~2 pp lower auth** on CNP recurring (issuer velocity rules); cards >90 days old stabilize. (Adyen 2023.)

## 11. Cross-border BIN misread

47. **~4-6% of cross-border CNP recurring declines are "fraud false positives"** where issuer saw a foreign merchant descriptor on a small-ticket recurring charge. (Visa Cross-Border Report 2023.)
48. **Local acquiring reduces cross-border declines by 8-12 pp** — e.g. Stripe routing via local Adyen entity in EU for US-based SaaS. (Stripe Local Acquiring 2024.)

## 12. Card reissue cycles

49. **Average card reissue cycle 2.8 years** in US, 3.2 years in EU, 4 years in Japan. (Nilson Issuer Report 2023.)
50. **Account updater (Visa VAU / MC ABU) captures 55-70% of reissued PANs**; remaining 30-45% churn unless network tokenized. (Visa VAU performance 2023.)

## 13. Expiry soft declines

51. **Expiration dates distribute ~7-10% per month** with mild seasonality (slight bulge Dec-Jan from year-end reissues). (Stripe expiry histogram 2023.)
52. **Soft declines spike +25-40% in the calendar month a card expires**; ~65% of these recover via account updater or retry with new expiry. (Checkout.com Retry Study 2024.)

## 14. Prepaid recurring blocks

53. **~20-30% of US prepaid BINs outright block MCC-5968 recurring** per network rules (NetSpend, Green Dot Vanilla, Walmart MoneyCard). (Prepaid Industry Benchmark 2023.)
54. **EU prepaid (Viva, Revolut prepaid tier) blocks ~15-20% of recurring MCCs by default**. (Sifted 2023.)

## 15. Business card mix in Enterprise tier

55. **Enterprise SaaS ($50k+ ACV) sees 50-65% corporate card share**; Mid-Market 25-40%; SMB 8-15%. (Stripe B2B Report 2024.)
56. **Virtual corporate cards (Brex, Ramp, Airbase, Mercury) now ~12-18% of US B2B SaaS volume**, up from ~3% in 2020. (Mercator 2024.)

## 16. Virtual card patterns

57. **Brex virtual cards auth ~89-91%** on SaaS; single-use virtual cards from expense platforms (Ramp, Airbase) auth ~85-88% because many are amount-locked. (Ramp blog + merchant benchmarks.)
58. **Virtual card expiry dates often 30-90 days**, causing ~8-12% of subscription renewals on virtual cards to fail vs physical corporate ~2%. (Checkout.com B2B 2024.)
59. **Mercury (fintech business banking) virtual cards** auth ~86-88% on SaaS; higher decline on cross-border. (Mercury docs + merchant data.)

## 17. Amex recurring-specific behavior

60. **Amex 3DS challenge rate in EU ~45-55% vs Visa/MC 20-30%** under PSD2 SCA — Amex SafeKey fires more conservatively on recurring initial authentication. (Adyen 3DS Report 2024.)
61. **Amex CIT (customer-initiated) recurring auth ~84%, MIT (merchant-initiated) ~86%** once COF credential flagged correctly. Missing COF flag costs Amex ~4-5 pp. (Amex SafeKey merchant guide 2023.)
62. **Amex declines cluster on installment-style recurring** — ~3x higher than Visa for annual plans >$1,000 without pre-authorization step. (Checkout.com B2B 2024.)

---

## Summary patterns count: 62 quantified patterns across 17 areas.

### Key columns coverage
- `card_brand` — patterns 1-7, 12-19, 40-44, 60-62
- `card_bin` — patterns 38-40, 47
- `card_funding_type` — patterns 8-11, 53-54
- `card_country` / `customer_country` — patterns 12-19, 29-33, 47-48
- `card_category` — patterns 34-37, 55-59
- `issuer_name` / `issuer_id` — patterns 20-33, 38-40
- `network_token_used` — patterns 41-44, 50
- `is_approved` — quantified throughout
