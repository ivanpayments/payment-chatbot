# Patterns 04 — SCA, 3DS2, and PSD2 in EU/UK Subscription Billing

Scope: 30 countries incl. full EU + UK. Synthetic SaaS billing dataset, card-on-file + recurring. Focus columns: `sca_exemption`, `three_ds_version`, `three_ds_status`, `three_ds_challenge`, `three_ds_frictionless`, `authentication_flow`, `eci`, `is_approved`, `customer_country`.

All patterns quantified in percentage points (pp) or basis points (bp). Sources cited inline.

---

## 1. SCA exemption usage rates (eligible traffic)

**P1. Recurring MIT (merchant-initiated) is the dominant exemption in SaaS.** 65–80% of all EU subscription renewal attempts are processed as MIT (outside PSD2 scope under RTS Art. 1(c)), not as SCA-authenticated transactions. Only the *first* CIT requires SCA. Source: Stripe SCA guide 2022–2024; Adyen "Recurring transactions under PSD2" docs.

**P2. TRA (Transaction Risk Analysis, RTS Art. 18) is used on ~30–50% of eligible EU card-not-present transactions** at mature PSPs (Adyen, Stripe, Checkout.com). Acquirer-side TRA rollout maturity: Adyen cites ~40% of eligible volume tagged TRA in 2022 reports; Stripe Radar applies TRA on "majority of eligible" traffic.

**P3. Low-Value Payment exemption (LVP, RTS Art. 16, <€30, max 5 consecutive or €100 cumulative) covers ~15–25% of one-shot EU CNP traffic** but <5% of SaaS billing because typical SaaS ARPU (€20–€100) sits near or above €30. Source: EBA Opinion EBA-Op-2019-06.

**P4. One-leg-out (OLO) exemption applies to ~8–15% of EU SaaS traffic** (non-EEA issuer ∨ non-EEA acquirer). "Best-effort" SCA under EBA Opinion EBA-Op-2020-15 (18 Jun 2020) — if 3DS unsupported by issuer, transaction may proceed without SCA. Source: EBA.

**P5. Corporate / commercial card "secure corporate payments" exemption (RTS Art. 17) usage: 2–5% of B2B SaaS volume** — limited because it requires lodged card / virtual card via dedicated secure procurement protocol. Most B2B cards still get challenged unless TRA-exempted.

**P6. Trusted beneficiary / whitelist exemption (RTS Art. 13) <1% of SaaS traffic.** Requires cardholder to whitelist merchant via issuer app — UX rarely completes. Visa/Mastercard scheme data 2023.

**P7. Exemption stacking cascade at tier-1 PSPs: ~85% of eligible EU CNP attempts receive *some* exemption** (MIT → TRA → LVP → OLO fallback). Adyen auth optimization docs, 2023.

---

## 2. Exemption eligibility by acquirer fraud rate (TRA tiers)

**P8. RTS Art. 18 TRA fraud-rate tiers (hard caps):**
- <€100 → acquirer fraud rate must be <13 bp (0.13%)
- <€250 → <6 bp (0.06%)
- <€500 → <1 bp (0.01%)
Above €500: no TRA allowed. Source: Commission Delegated Regulation (EU) 2018/389 Art. 18 & Annex.

**P9. Only ~20% of EU acquirers qualify for the <€500 TRA tier (<1 bp fraud).** Most sit in the <€100 band. Tier-1 PSPs (Adyen, Stripe, Worldpay) publish <5 bp aggregate CNP fraud rates; long-tail acquirers typically 15–30 bp. Source: ECB SecuRe Pay semi-annual fraud report 2023.

**P10. PSP routing behavior: merchants with multi-acquirer setups route high-ticket (>€250) to the acquirer with the lowest fraud rate — observed 10–18% lift in TRA exemption request rate post-routing.** Source: Checkout.com "Smart Routing" case studies 2022–2023.

**P11. Fraud-rate breach consequence: TRA rights suspended for one quarter** if acquirer exceeds the tier cap for two consecutive quarters (RTS Art. 19). Observed in market: ~5% of EU acquirers lost a tier at least once in 2022.

---

## 3. 3DS2 frictionless rate

**P12. Industry-wide 3DS2 frictionless rate: 72–88%** across EU/UK in 2023. Visa reports 85%+ on 3DS 2.2 flows; Mastercard reports 78% average; Ravelin 2023 State of 3DS reports 75% median merchant. `three_ds_status = 'Y' AND three_ds_challenge = FALSE`.

**P13. 3DS 2.1 frictionless: ~65–72%. 3DS 2.2 frictionless: ~80–88%. 3DS 2.3 (rolling out 2024–2025): projected 90%+.** Version matters 15–25pp. Source: EMVCo 3DS 2.3 spec + Visa 2023 scheme data.

**P14. Device fingerprint + risk data submission lifts frictionless rate by 12–18pp** versus minimum-field 3DS2 requests. Adyen and Stripe both publish this delta (Stripe "3D Secure optimization" docs, 2023).

**P15. Frictionless rate varies by issuer country: Nordics 88–92%, DACH 78–84%, Southern Europe (IT/ES/PT) 65–75%, France ~70% (historically conservative issuers).** Source: Checkout.com "State of Digital Commerce 2023", Mastercard 3DS transparency.

---

## 4. 3DS2 challenge drop-off

**P16. Challenge abandonment rate: 8–22% of challenged customers abandon.** Ravelin 2023: median 12%. Adyen: 8–15% in mature markets, up to 25% on mobile + OTP. Stripe: ~15% average in EU.

**P17. Mobile challenge drop-off is 2× desktop: ~18% vs ~9%.** Small OTP input, app switching, SMS delay. Source: Stripe Authentication Insights 2022.

**P18. Repeat-challenge drop-off on renewals (when MIT flag missing): 30–40% abandonment** — customers don't expect to re-auth a subscription. Source: Recurly + Checkout.com SaaS churn reports 2023.

**P19. Challenge methods and drop-off: SMS OTP ~15%, in-app biometric (push to banking app) ~6%, hardware token ~20%, static password (legacy) ~28%.** Biometric wins. Source: UK Finance "SCA Impact Study" 2023.

---

## 5. Auth-rate uplift from exemptions

**P20. TRA-exempted transactions show +8 to +12pp auth approval vs SCA-challenged** (no drop-off layer + issuer treats as lower friction). Source: Adyen "Auth rate uplift" 2022 report.

**P21. LVP exemption: +5 to +9pp auth uplift** — smaller than TRA because issuers also risk-score LVP traffic.

**P22. Properly-flagged MIT (recurring) vs unflagged recurring: +10 to +15pp auth uplift.** Unflagged recurring often gets soft-declined as "do-not-honor" or SCA-required. Source: Stripe Billing benchmarks, Recurly 2023.

**P23. Stacking TRA + MIT correctly on a renewal yields +18–22pp vs worst-case (no exemption, no MIT flag, full challenge).** Tier-1 SaaS observed range.

---

## 6. One-leg-out behavior and corridors

**P24. UK→US corridor post-Brexit: ~18% of UK SaaS CNP volume is US-card-on-UK-acquirer — OLO applies, SCA not mandatory.** FCA confirmed OLO treatment after 1 Jan 2021 (UK left EEA). Observed auth rate on this corridor: ~88%, vs ~82% on UK→UK with SCA.

**P25. US→EU corridor: non-EEA-issued card + EEA acquirer → ~94% of transactions proceed without SCA** (issuer doesn't support 3DS2 or returns attempted-auth). ECI = 06 (attempted, non-reg) common. Source: EBA Opinion 2020-15.

**P26. Intra-EEA corridors post-14-Mar-2022: ~92% of transactions go through 3DS2** (UK finally aligned). Pre-Mar 2022: UK ~40% enforcement, EU 85%+.

---

## 7. Liability shift

**P27. Successful 3DS2 auth (ECI 05 Visa / ECI 02 Mastercard) shifts chargeback liability to issuer for fraud-reason chargebacks.** TRA exemption (no 3DS) = liability stays with merchant. Source: Visa Core Rules + Mastercard Chargeback Guide.

**P28. Attempted 3DS (ECI 06 Visa / ECI 01 Mastercard) also shifts liability** — issuer tried but couldn't complete. Merchants often cite ~35% of their "protected" volume sits in ECI 06.

**P29. MIT transactions: liability stays with merchant for "subscription dispute" reason codes (13.2, 13.7) but shifts to issuer for fraud if original CIT was 3DS-authenticated and the COF transaction ID is correctly chained.** Source: Visa Account Updater + COF framework 2022.

---

## 8. PSD2 enforcement dates and pre/post impact

**P30. EU SCA hard-enforcement: 1 Jan 2021** (after multiple EBA delays from original Sep 2019). UK: **14 March 2022** (FCA delayed to give ecosystem extra time).

**P31. Post-enforcement auth-rate dip: EU saw -3 to -6pp auth rate drop in Q1 2021** vs Q4 2020, recovering to -1pp by Q4 2021 as exemptions matured. Source: Visa Europe 2021 merchant report, Adyen SCA tracker.

**P32. UK post-14-Mar-2022 dip: -5pp immediate, recovered in ~4 months.** Source: Barclaycard + UK Finance 2022.

**P33. Soft-decline ramp: "65" (SCA required) decline code rose from <0.5% of EU CNP in 2020 to ~7% in Q1 2021, stabilizing ~4% in 2023.** Source: Visa DPS 2023 decline code benchmark.

---

## 9. Visa / Adyen published post-SCA deltas

**P34. Adyen reported avg EU auth rate: 94.2% pre-SCA (H2 2020) → 88.1% post-SCA (H1 2021) → 92.8% (H2 2023)** after exemption tuning. Net lasting impact: -1.4pp. Source: Adyen Global Payments Report 2023.

**P35. Visa reported "authentication abandonment" of 25% at SCA launch, down to 11% by late 2022** as 3DS2 matured. Source: Visa "Authentication Insights" 2022.

**P36. Stripe published EU authenticated volume: +55% of all EU card volume now routed through 3DS2** (vs <10% pre-PSD2). Source: Stripe SCA hub 2023.

---

## 10. 3DS version effects

**P37. 3DS1 deprecated Oct 2022 (Visa) / Oct 2022 (Mastercard).** Any 3DS1 attempt now falls back or fails. Legacy merchants hit a 15–25pp auth-rate cliff on deprecation day.

**P38. 3DS 2.1 → 2.2 upgrade alone lifted frictionless rate by +8 to +12pp in 2022** because 2.2 adds exemption flags (TRA, LVP, trusted beneficiary) directly in the AReq. Source: EMVCo + Visa 2022.

**P39. 3DS 2.3 adds decoupled auth, SPC (Secure Payment Confirmation via WebAuthn), and "out-of-band" flows** — expected +5–10pp additional frictionless in 2024–2025. Source: EMVCo 3DS 2.3 spec Oct 2022.

---

## 11. MIT / COF flagging

**P40. Correctly chaining COF (Credential-on-File) transaction IDs between initial CIT and subsequent MIT lifts renewal auth by +5 to +10pp.** Visa Transaction ID / MC Trace ID must be stored from the 3DS-authenticated CIT. Source: Visa COF Framework 2020 + Stripe Billing docs.

**P41. ~15–25% of EU SaaS renewals are misflagged as CIT instead of MIT** at mid-tier PSPs → unnecessary soft declines. Source: Recurly 2023 benchmark, Checkout.com 2022.

**P42. MIT unscheduled (card top-up, usage-based) vs MIT scheduled (fixed subscription): scheduled gets +3pp better auth** because issuers pattern-match calendar. Source: Adyen 2023.

---

## 12. Brazil Pix & India RBI e-mandate equivalents

**P43. India RBI e-mandate (effective 1 Oct 2021, amended 2022): recurring card payments >₹15,000 require AFA (Additional Factor of Authentication) on every charge; ≤₹15,000 allowed via pre-registered e-mandate with 24h pre-debit notification.** Source: RBI circular DPSS.CO.PD No. 447/02.14.003/2021-22.

**P44. Post-RBI-e-mandate, India SaaS recurring auth dropped from ~85% to ~35–45% for non-compliant merchants** in Q4 2021. Recovered to ~70% by end 2022 for merchants using Razorpay / Stripe e-mandate rails. Source: Razorpay report 2022.

**P45. Brazil Pix: not a card rail, but Pix Automático (launched Jun 2025) is the regulated recurring-debit flow — consumer pre-authorizes recurring, bank can revoke.** Pix itself uses device-bound key + biometric at payer's bank app. Source: BCB (Banco Central do Brasil) Resolução BCB 345/2024.

**P46. India 48h pre-debit notification (not 24h as sometimes stated) for e-mandates >₹15,000 since 2022 revision; ~8–12% of customers cancel after notification**, inflating apparent "churn". Source: RBI + Chargebee India benchmark 2023.

---

## 13. B2B corporate card exemption

**P47. RTS Art. 17 "secure corporate payment" exemption requires use of dedicated corporate payment protocol (lodged card, virtual card, BTA/CTA) — raw commercial card swipes do NOT qualify.** Misconception common. Source: EBA Q&A 2018_4141.

**P48. Commercial card auth rate on SaaS: ~4–6pp lower than consumer cards in EU** because many issuers still challenge corporate cards (no corporate-specific exemption flow) and many corporate cards have weak 3DS2 enrollment. Source: Ramp + Brex EU expansion reports.

**P49. Visa Commercial Choice / Mastercard Corporate: both schemes offer "commercial card data" (L2/L3) flag that can trigger TRA at acquirer, lifting auth by +3–5pp.** Source: Visa Commercial Solutions 2022.

---

## 14. Wallet / tokenized exemptions

**P50. Apple Pay in-app / web: SCA satisfied by device biometric (Face/Touch ID) — frictionless rate effectively 100%, no additional challenge.** Source: Apple Pay PSD2 compliance doc + EBA Opinion 2018 (biometric + possession = 2-factor).

**P51. Google Pay: same logic — device PIN/biometric + tokenized PAN satisfies SCA.** Tokenized wallets average +6 to +10pp auth uplift vs raw PAN in EU. Source: Google Pay merchant docs + Adyen wallet benchmark 2023.

**P52. Wallet share of EU SaaS CNP: ~18–25% and rising 3–5pp/year.** Highest in UK (28%), lowest in DE (12% — card-averse + SEPA DD preference). Source: Worldpay Global Payments Report 2024.

**P53. Click-to-Pay (SRC, Secure Remote Commerce): PSD2-compliant when combined with device binding; uptake in EU still <5% of CNP in 2024.** Source: EMVCo SRC metrics.

---

## Appendix — mapping to dataset columns

| Column | Expected values / signals |
|---|---|
| `sca_exemption` | `tra`, `lvp`, `mit`, `olo`, `corporate`, `trusted_beneficiary`, `none` |
| `three_ds_version` | `1.0.2` (legacy, should be ~0% post Oct 2022), `2.1.0`, `2.2.0`, `2.3.0` |
| `three_ds_status` | `Y` (auth), `A` (attempted), `N` (failed), `U` (unavailable), `R` (rejected) |
| `three_ds_challenge` | Boolean — TRUE only when issuer requested step-up |
| `three_ds_frictionless` | Boolean — `three_ds_status='Y' AND three_ds_challenge=FALSE` |
| `authentication_flow` | `frictionless`, `challenge_otp`, `challenge_biometric`, `challenge_oob`, `mit_no_sca`, `exempted` |
| `eci` | Visa: 05 (full auth), 06 (attempted), 07 (non-auth). MC: 02, 01, 00. |
| `is_approved` | Expected auth-rate deltas per patterns P20–P23, P31–P36 |
| `customer_country` | EU27 + UK, plus non-EEA for OLO detection |

---

## Key scheme rules cited

- Commission Delegated Regulation (EU) 2018/389 — RTS on SCA, Articles 10, 13, 16, 17, 18, 19
- EBA Opinion EBA-Op-2019-06 (21 Jun 2019) — SCA elements
- EBA Opinion EBA-Op-2020-15 (18 Jun 2020) — migration issues, OLO
- FCA PS21/19 — UK SCA enforcement 14 Mar 2022
- RBI DPSS.CO.PD No. 447/02.14.003/2021-22 — India e-mandate
- BCB Resolução 345/2024 — Pix Automático
- EMVCo 3DS 2.3.1 spec (Oct 2022)
- Visa Core Rules + Chargeback Guide 2023
- Mastercard Transaction Processing Rules 2023
