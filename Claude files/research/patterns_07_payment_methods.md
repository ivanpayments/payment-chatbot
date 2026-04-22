# Patterns 07 — Payment Method Adoption by Region (SaaS Subscription Billing)

Scope: quantified patterns for seeding a synthetic SaaS billing dataset (30 countries, subscription cadences, SMB + Enterprise tiers). Each pattern is tagged to the dataset columns it should drive: `payment_method_type`, `payment_method_subtype`, `wallet_provider`, `card_brand`, `currency`, `customer_country`, `sku_tier`, `billing_cadence`, `fee_rate`.

Key distinction: **subscription-relevant** (recurring-capable) vs **one-time-only** methods. iDEAL, Pix, Alipay (default), MB Way, Blik, Swish, UPI (Collect) are historically one-time; recurring variants (iDEAL mandate via SEPA DD, Pix Automatico 2024+, UPI AutoPay, e-mandates) are newer and low-share. Card-on-file remains the global default for SaaS recurring.

---

## 1. Card share by region (drives `payment_method_type=card` weight by `customer_country`)

1. **US SaaS card share ≈ 88–92%** of self-serve subscription volume (transactions), with invoice/ACH absorbing most of the rest on Enterprise tiers. Source: Stripe *Payment Methods Guide* (US), Worldpay *Global Payments Report 2024*.
2. **EU-5 (DE/FR/IT/ES/NL) card share ≈ 70–82%** on SaaS subs, ~10–15 pts below US because SEPA DD absorbs B2B recurring. Source: Adyen *Retail Report* + ECB SEPA statistics 2023.
3. **UK card share ≈ 82–88%** on SaaS subs — higher than EU average because Bacs DD is B2B-skewed, leaving consumer/SMB on cards. Source: UK Finance *Payment Markets Report 2024*.
4. **LatAm (BR/MX/CO/AR/CL) card share ≈ 55–70%** on SaaS subs; boletos/Pix/OXXO/local debit absorb 15–25%, wallets 5–10%. Source: Worldpay GPR 2024, Americas Market Intelligence 2023.
5. **APAC split: JP card ≈ 65–75%**, konbini/bank transfer ≈ 15–20%, wallets ≈ 10%; **KR card ≈ 80–85%** (credit-heavy); **SG/HK card ≈ 85–90%**; **IN card ≈ 25–35%** (UPI dominant). Source: Adyen APAC guide, RBI Retail Payments Report 2024.
6. **AU/NZ card share ≈ 85–90%** SaaS subs, with wallet (Apple Pay) overlay inside card rails reaching 22%+ of card volume. Source: RBA *Retail Payments Statistics* 2024.

## 2. SEPA Direct Debit penetration (drives `payment_method_type=sepa_dd` by country for EUR subs)

7. **DE SEPA DD share ≈ 35–45% of B2B recurring SaaS** (highest in EU); SEPA DD is the dominant B2B cadence vehicle for invoice-less monthly sub. Source: Bundesbank *Zahlungsverhalten* 2023, Stripe DE guide.
8. **NL SEPA DD share ≈ 25–30% of SaaS subs** — iDEAL is ecommerce-first-pay, with SEPA DD carrying the recurring leg via mandate. Source: DNB payments statistics, Adyen NL guide.
9. **FR SEPA DD share ≈ 20–25%** SaaS subs; French utilities/telco legacy drives comfort with DD, but card-on-file still majority. Source: Banque de France *Rapport sur les paiements scripturaux* 2023.
10. **IT / ES SEPA DD share ≈ 10–15%** SaaS subs — lower trust in DD, more card-on-file. Source: Banca d'Italia + Banco de España SEPA reports 2023.
11. **BE / AT SEPA DD share ≈ 15–25%** — mid-tier; AT closer to DE pattern, BE closer to FR. Source: ECB SEPA Indicators 2023.

## 3. ACH Debit / eCheck (US) (drives `payment_method_subtype=ach_debit`)

12. **ACH Debit ≈ 15–25% of US Enterprise annual SaaS contracts** by count, higher by GMV (30–45%) since deal sizes are larger. Source: Nacha *2023 ACH Network Statistics*, Stripe Enterprise case studies.
13. **ACH for US SMB monthly sub ≈ 3–7%** — friction of micro-deposit verification keeps share low; Plaid-linked ACH closes the gap for modern billing stacks. Source: Plaid *Fintech Report 2023*.
14. **WEB (consumer) vs CCD/PPD (B2B) split within ACH Debit on SaaS ≈ 60/40** by count, flipping to 30/70 by dollar value. Source: Nacha 2023 volume breakdown.

## 4. iDEAL and one-time-only rails (subscription impact)

15. **iDEAL share of NL ecommerce ≈ 60%+**, but on SaaS recurring ≈ <5% — iDEAL is single-payment bank redirect without recurring mandate; subs default to card or SEPA DD after first payment. Source: Currence iDEAL statistics 2023, Adyen NL guide.
16. **Pix share of BR ecommerce ≈ 40%+**, but **Pix on SaaS recurring ≈ <3%** pre-2024; Pix Automatico launched Oct 2024, expected to lift to 10–15% of BR SaaS subs by 2026. Source: BCB *Estatísticas de Pagamentos* 2024.
17. **UPI share of IN digital payments ≈ 75%+**, but UPI AutoPay on SaaS subs ≈ 15–25% — cap limits (₹15k without 2FA) and mandate failures drag effective share. Source: NPCI *UPI AutoPay Bulletin* 2024.

## 5. UK Bacs Direct Debit (drives `payment_method_subtype=bacs_debit`, GBP only)

18. **UK Bacs DD ≈ 25–35% of UK B2B SaaS subs** (monthly/quarterly); consumer SaaS ≈ 5–10%. Source: UK Finance *Bacs Payment Schemes* 2023, Stripe UK guide.
19. **Bacs setup lead time ≈ 3 business days** (vs SEPA DD 2 business days, ACH 3–5) — this latency is why Bacs is under-adopted for short trials. Source: Pay.UK operational guide 2024.
20. **Bacs AUDDIS failure rate ≈ 0.5–1%** of mandates (return/indemnity claims), lowest of major bank debits. Source: Bacs annual report 2023.

## 6. Apple Pay / Google Pay (drives `payment_method_type=wallet_*`, rides card rails)

21. **Apple Pay share of SaaS self-serve checkout ≈ 5–12%** US/EU, rising to **22%+ in AU** and **15–18% in UK/FR** on mobile-first signup flows. Source: Apple investor commentary, Adyen wallet report 2024.
22. **Google Pay share ≈ 3–8%** globally, peaking at **20%+ in JP** and **15%+ in IN** (where it wraps UPI, not card). Source: Worldpay GPR 2024.
23. **Wallet share on Enterprise annual contracts ≈ <1%** — Apple/Google Pay is essentially a self-serve consumer/SMB phenomenon; procurement flows don't route through wallets. Source: Stripe Billing benchmarks 2024.

## 7. Invoice / wire / ACH credit (Enterprise) (drives `payment_method_type=invoice_wire`)

24. **Enterprise annual SaaS contracts ≈ 60–90% paid by invoice + wire/ACH credit**, rising to 95%+ on deals above $100k ACV. Source: Stripe Billing *Enterprise Invoicing Report* 2023, Zuora Subscription Economy Index 2024.
25. **Average DSO on Enterprise SaaS invoices ≈ 35–55 days** (net-30 terms + slippage), vs <1 day for card-on-file. Source: SaaS Capital benchmark 2024.
26. **Wire fees absorbed by payer ≈ $15–45 per inbound**; ACH credit ≈ $0.20–1.50 — drives preference for ACH credit in US Enterprise. Source: J.P. Morgan *Treasury Services* fee schedule 2024.

## 8. Regional wallets — CN/SEA/Nordics/CEE (drives `wallet_provider`)

27. **CN Alipay + WeChat Pay ≈ 90%+ of CN consumer ecommerce**, but **SaaS B2B recurring in CN still ≈ 60%+ bank transfer / corporate card UnionPay**; cross-border SaaS billed to CN entities uses UnionPay or offshore USD wire. Source: iResearch *China Third-Party Payment Report 2023*.
28. **Nordic rails — Swish (SE), MobilePay (DK/FI), Vipps (NO)**: consumer ecom share 30–50%, SaaS sub share <5% (P2P/one-time rails, weak recurring mandate support). Source: Swedish Riksbank *Payments Report 2023*, Danmarks Nationalbank 2023.
29. **PL Blik ≈ 65%+ of PL ecommerce**, SaaS recurring ≈ 5–10% (Blik cyclical/recurring launched 2022, adoption lagging). Source: Polish Payment Standard (PSP) annual report 2023.
30. **PT MB Way ≈ 40%+ PT ecom**, SaaS recurring ≈ <5%. **SEA wallets (GoPay ID, TrueMoney TH, GrabPay SG)** ≈ 20–35% ecom share each, SaaS recurring ≈ 3–8%. Source: Worldpay GPR 2024 APAC section.

## 9. BNPL in SaaS (drives rare `payment_method_type=bnpl`)

31. **BNPL share of SaaS subs ≈ <1%** globally — Klarna/Affirm/Afterpay are ecom-checkout products; Affirm B2B (Resolve) and Klarna B2B pilots exist but negligible volume. Source: Klarna + Affirm 10-Ks 2023, Worldpay GPR 2024.
32. **Exception: dev-tool / creator-tier annual upfront ≈ 2–4% BNPL** (Stripe + Affirm pilot for $500–3000 annual plans). Source: Stripe/Affirm announcement 2023.

## 10. Crypto / stablecoin (drives rare `payment_method_type=crypto`)

33. **Crypto/stablecoin share of SaaS subs ≈ <0.1%** globally; concentrated in Web3 infra vendors (Alchemy, Infura, Helius) where it may reach 5–10% of their own billing. Source: Chainalysis *Stablecoin Report 2024*, public Web3 infra disclosures.

## 11. Corporate card vs personal card (drives `card_brand` + BIN-derived flag)

34. **B2B SaaS spend on corporate/commercial BINs ≈ 30–50%** (US higher, EU lower due to virtual-card adoption lag). Source: Brex + Ramp benchmarks 2023, Visa commercial card report 2024.
35. **Virtual card (Brex/Ramp/Airbase) share of US SMB SaaS ≈ 15–25%** and rising 20% YoY. Source: Ramp *Spend Report 2024*.

## 12. Card-on-file tokenization (drives `tokenized=true` flag)

36. **SaaS recurring card-on-file tokenization rate ≈ 85–95%** on modern PSPs (Stripe, Adyen, Braintree); network tokens (Visa VTS, Mastercard MDES) cover 40–60% of that on tier-1 merchants. Source: Visa VTS 2024 disclosures, Stripe network tokens launch blog.
37. **Network-token lift on auth rate ≈ +1.5 to +3.0 pts** vs PAN-only; drives PSPs to push adoption. Source: Stripe + Adyen network-token case studies 2023.

## 13. Debit vs credit split (drives `card_subtype`)

38. **US SaaS card mix ≈ 70% credit / 30% debit** on consumer; 85% credit / 15% debit on B2B. Source: Federal Reserve *Payments Study 2022*, Visa/MC quarterly mixes.
39. **EU card mix ≈ 45–55% debit / 45–55% credit** (DE/NL debit-heavy, UK credit-heavy); drives lower interchange → lower `fee_rate`. Source: ECB *Payment Statistics* 2023.
40. **LatAm card mix ≈ 55% credit / 45% debit**; BR installments ("parcelado") common on cards, adding complexity to `fee_rate`. Source: ABECS *Brazilian Cards Report 2023*.

## 14. Auth rate by payment method (drives synthetic `auth_rate`)

41. **SEPA DD first-collection auth rate ≈ 96–99%** (mandate pre-validated); recurring collections ≈ 98%+. Source: ECB SEPA performance reports.
42. **Card auth rate: US ≈ 85–92%, EU ≈ 78–85%** (SCA drag), APAC ≈ 80–88%. Source: Adyen *Authorisation Performance Benchmarks 2024*.
43. **ACH Debit auth rate ≈ 94–97%** (returns split across R01 NSF, R03 no-account, R10 unauthorized). Source: Nacha return-code statistics 2023.
44. **Bacs DD auth rate ≈ 97–99%**, lowest failure of the three bank-debit rails. Source: Pay.UK 2023.

## 15. Return / chargeback / reversal rates (drives synthetic `return_rate`)

45. **SEPA Core DD return rate ≈ 0.5–1.0%** (consumer 8-week no-question refund window drives the bulk); SEPA B2B DD return rate ≈ 0.1–0.3% (no refund right). Source: Bundesbank + ECB 2023.
46. **ACH return rate ≈ 1–2%** on SaaS subs; ACH unauthorized return (R10/R11) ≈ 0.03–0.08%, Nacha threshold 0.5%. Source: Nacha Rules 2024.
47. **Bacs DD indemnity claim rate ≈ <0.5%**; chargeback equivalent (Direct Debit Guarantee). Source: Bacs 2023.
48. **Card chargeback rate on SaaS subs ≈ 0.4–0.9%** all-brand; Visa threshold 0.9% / 100 txn, MC 1.5% / 100 txn. Source: Visa VAMP + MC ECM 2024.

## 16. Payment method cost (drives `fee_rate` column)

49. **Card fee_rate (blended SaaS, standard-pricing PSP) ≈ 2.2–3.2%** (US CP/CNP mix 2.6–2.9%, EU 1.4–2.4% due to IF cap, LatAm 3.5–5.5%). Source: Stripe + Adyen public pricing 2024, EU Interchange Fee Regulation.
50. **SEPA DD fee_rate ≈ 0.25–0.50 EUR flat** (often €0.35 fixed), effectively <0.5% on a €99 MRR. Source: Stripe SEPA pricing, GoCardless pricing 2024.
51. **ACH Debit fee_rate ≈ 0.5–0.8%** capped (Stripe 0.8% capped $5; Plaid-ACH similar). Source: Stripe ACH pricing 2024.
52. **Wire fee_rate ≈ 0.05–0.15% effective** on Enterprise large invoices (flat $15–45 / wire on $100k+ ACV). Source: JPM + BofA treasury fee schedules 2024.
53. **Bacs DD fee_rate ≈ £0.20–0.50 flat** per collection. Source: GoCardless + Stripe UK pricing.
54. **Wallet (Apple/Google Pay) fee_rate ≈ same as underlying card** (wallet is not a separate scheme); no incremental issuer fee. Source: Apple Pay / Google Pay merchant terms.

---

## Dataset seeding cheat-sheet (how to translate into synthetic rows)

- `customer_country` ∈ {US, CA, GB, DE, FR, NL, IT, ES, BE, AT, CH, IE, SE, DK, NO, FI, PL, PT, AU, NZ, JP, KR, SG, HK, IN, BR, MX, CO, AR, CL}.
- Card weight by country from §1; SEPA DD only when `currency=EUR`; Bacs only when `currency=GBP`; ACH only when `currency=USD`; PAD only when `currency=CAD`.
- `sku_tier=Enterprise` → flip 60–90% to `invoice_wire` (§7) regardless of country; `sku_tier=SMB/Pro/Starter` → follow country card/DD mix.
- `billing_cadence=annual` + `sku_tier=Enterprise` → invoice_wire dominates; `billing_cadence=monthly` + consumer tier → card + wallet.
- `wallet_provider` populated only when `payment_method_type` starts with `wallet_`; country caps per §6/§8.
- `fee_rate` drawn from §16 with small noise (±20%).
- `auth_rate` and `return_rate` drawn from §14/§15 by method.
- One-time-only rails (iDEAL, Pix pre-2024, Swish, MB Way, Blik, UPI Collect) should only appear as **first-payment** rows with a follow-on `sepa_dd` or `card` row for subsequent cycles — models the real-world mandate handoff.

---

## Source index (short form)

- Stripe Payment Methods Guide — https://stripe.com/docs/payments/payment-methods/overview
- Adyen Retail Report / Global Payments guides (2024)
- Worldpay (FIS) Global Payments Report 2024
- ECB SEPA Indicators / Payment Statistics (2023)
- Bundesbank *Zahlungsverhalten in Deutschland* (2023)
- UK Finance *Payment Markets Report* 2024; Pay.UK / Bacs annual 2023
- Nacha *ACH Network Statistics* 2023 + Rules 2024
- RBI *Retail Payments* 2024; NPCI UPI AutoPay bulletins
- BCB *Estatísticas de Pagamentos* 2024 (Pix / Pix Automatico)
- RBA *Retail Payments Statistics* 2024 (AU)
- Riksbank / Danmarks Nationalbank / DNB / Banque de France / Banca d'Italia / Banco de España — 2023 SEPA & retail payments reports
- Polish Payment Standard (Blik) 2023; Currence (iDEAL) 2023; SIBS (MB Way) 2023
- iResearch *China Third-Party Payment Report* 2023
- Visa / Mastercard commercial-card and network-token disclosures 2024
- Federal Reserve *Payments Study* 2022
- Brex / Ramp *Spend Reports* 2023–2024; Plaid *Fintech Report* 2023
- Klarna + Affirm 10-Ks 2023; Chainalysis *Stablecoin Report* 2024
- ABECS (Brazil cards) 2023; Americas Market Intelligence 2023
- Zuora *Subscription Economy Index* 2024; SaaS Capital benchmarks 2024
- J.P. Morgan + Bank of America *Treasury Services* fee schedules 2024
