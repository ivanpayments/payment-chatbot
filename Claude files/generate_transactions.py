"""
generate_transactions.py — Synthetic SaaS billing dataset generator.

Generates ~100K billing attempts for "Cirrus Cloud Platform" (~$2B ARR, 14 PSPs,
30 countries, ~100 plan SKUs, Jan 2023 – Dec 2025). Emits a 171-column CSV that
matches the header in `transactions.csv` exactly (column order locked).

Encoded patterns: see `research/patterns_SELECTED_150.md` (S001–S150). Each
implemented pattern is tagged inline with `# Sxxx`. Intentionally skipped
patterns are listed at the bottom under "Skipped patterns".

Run: `python generate_transactions.py --rows 100000 --seed 42`
"""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

# --- Section 0: Canonical column order (171 columns from transactions.csv) ---

COLUMNS: List[str] = [
    "transaction_id","merchant_transaction_id","provider_transaction_id","order_id",
    "merchant_id","parent_transaction_id","created_at","authorized_at","captured_at",
    "settled_at","processing_time_ms","provider_latency_ms","amount","currency",
    "amount_usd","fx_rate","captured_amount","refunded_amount","payment_method_type",
    "payment_method_subtype","card_brand","card_bin","card_last4","card_expiry_date",
    "card_country","card_funding_type","card_category","card_fingerprint","issuer_id",
    "issuer_name","wallet_provider","processor","acquirer_country","acquirer_bin",
    "processor_merchant_id","routing_rule_id","routing_strategy","route_layer",
    "attempt_number","is_retry","token_type","token_requestor_id","three_ds_version",
    "three_ds_status","three_ds_challenge","eci","authentication_flow","sca_exemption",
    "pares_status","status","response_code","response_message","provider_status",
    "provider_response_code","merchant_advice_code","decline_category","is_approved",
    "settled_flag","risk_score","risk_decision","risk_provider","cvv_result","avs_result",
    "fraud_screening_status","is_standalone_screening","customer_country",
    "customer_ip_country","device_type","channel","is_returning_customer","merchant_name",
    "merchant_country","merchant_mcc","merchant_vertical","merchant_tier","org_id",
    "industry","processing_fee_usd","interchange_fee_usd","scheme_fee_usd",
    "net_amount_usd","fee_rate","fx_spread_pct","settlement_currency",
    "settlement_delay_days","reconciliation_status","transaction_type","is_recurring",
    "recurring_sequence","recurring_count","is_installment","installment_count",
    "is_cross_border","smart_routing","retry_status","retry_count","chargeback_amount",
    "chargeback_date","in_dispute_amount","in_dispute_date","is_test","is_tokenized",
    "is_outage","scheme_transaction_id","previous_scheme_transaction_id",
    "authorization_code","reconciliation_id","merchant_account_id","checkout_session_id",
    "merchant_reference","idempotency_key","sub_status","intent","payment_source",
    "is_subsequent_payment","account_funding_transaction","three_ds_server_tx_id",
    "three_ds_ds_tx_id","three_ds_acs_tx_id","cavv","statement_descriptor",
    "vaulted_token_id","disputed","buyer_id","route_steps_count","payment_retry_count",
    "chargeback_count","issuer_parent_group","fee_tax_amount_usd","capture_success",
    "capture_delay_hours","auth_expired_at_capture","is_incremental_auth","is_reauth",
    "refund_status","representment_status","compelling_evidence_score","dunning_retry_day",
    "account_updater_triggered","three_ds_frictionless","three_ds_challenge_type",
    "three_ds_data_only_flow","wallet_idv_path","is_split_payment","sub_merchant_id",
    "seller_rolling_reserve_pct","presence_mode","level_data","dcc_offered","dcc_accepted",
    "fx_lock_point","is_payout","payout_rail","payout_failure_rate_flag",
    "psp_business_model","carries_cb_risk","sku_id","sku_tier","billing_cadence",
    "subscription_id","invoice_id","customer_id","billing_reason","collection_method",
    "current_period_start","current_period_end","trial_end","proration_amount_usd",
    "next_payment_attempt","churn_type","cancellation_reason",
    "is_fraud","three_ds_abandoned",
]
assert len(COLUMNS) == 173

# --- Section 1: Reference data ---

# 30 countries + baselines (S001–S023)
COUNTRY_BASE: Dict[str, Dict] = {
    "US": {"auth": 0.88, "cur": "USD", "region": "NA"},   # S001
    "CA": {"auth": 0.87, "cur": "CAD", "region": "NA"},   # S020
    "GB": {"auth": 0.86, "cur": "GBP", "region": "EU"},   # S002
    "DE": {"auth": 0.83, "cur": "EUR", "region": "EU"},   # S003
    "FR": {"auth": 0.82, "cur": "EUR", "region": "EU"},   # S004
    "NL": {"auth": 0.86, "cur": "EUR", "region": "EU"},   # S021
    "SE": {"auth": 0.91, "cur": "SEK", "region": "EU"},   # S005
    "NO": {"auth": 0.91, "cur": "NOK", "region": "EU"},   # S005
    "DK": {"auth": 0.91, "cur": "DKK", "region": "EU"},   # S005
    "FI": {"auth": 0.91, "cur": "EUR", "region": "EU"},   # S005
    "IT": {"auth": 0.78, "cur": "EUR", "region": "EU"},   # S006
    "ES": {"auth": 0.78, "cur": "EUR", "region": "EU"},   # S006
    "PT": {"auth": 0.78, "cur": "EUR", "region": "EU"},   # S006
    "PL": {"auth": 0.84, "cur": "PLN", "region": "EU"},   # S022
    "CH": {"auth": 0.87, "cur": "CHF", "region": "EU"},   # S023
    "AT": {"auth": 0.84, "cur": "EUR", "region": "EU"},
    "BR": {"auth": 0.73, "cur": "BRL", "region": "LATAM"},# S007
    "MX": {"auth": 0.72, "cur": "MXN", "region": "LATAM"},# S008
    "AR": {"auth": 0.62, "cur": "ARS", "region": "LATAM"},# S009
    "CO": {"auth": 0.74, "cur": "COP", "region": "LATAM"},
    "CL": {"auth": 0.77, "cur": "CLP", "region": "LATAM"},
    "AU": {"auth": 0.88, "cur": "AUD", "region": "APAC"}, # S019
    "NZ": {"auth": 0.88, "cur": "NZD", "region": "APAC"}, # S019
    "JP": {"auth": 0.88, "cur": "JPY", "region": "APAC"}, # S012
    "IN": {"auth": 0.55, "cur": "INR", "region": "APAC"}, # S010/S067
    "ID": {"auth": 0.70, "cur": "IDR", "region": "APAC"},
    "SG": {"auth": 0.88, "cur": "SGD", "region": "APAC"},
    "TR": {"auth": 0.80, "cur": "TRY", "region": "MENA"}, # S013
    "NG": {"auth": 0.58, "cur": "NGN", "region": "AF"},   # S014
    "EG": {"auth": 0.62, "cur": "EGP", "region": "MENA"}, # S015
}
COUNTRIES = list(COUNTRY_BASE.keys())
EU_COUNTRIES = {c for c, v in COUNTRY_BASE.items() if v["region"] == "EU"}
LATAM = {c for c, v in COUNTRY_BASE.items() if v["region"] == "LATAM"}
APAC = {c for c, v in COUNTRY_BASE.items() if v["region"] == "APAC"}
MENA = {"TR", "EG", "NG"}

# 14 PSPs (fictitious names).
PSPS = [
    "novapay",   # S026 global-leader PSP
    "arcadia",   # S027 EU-strong PSP
    "kestrel",   # S028 US-native PSP
    "cedar",     # S029 EU-tilt PSP
    "verdant",
    "orion",     # S030 LatAm cross-border
    "kinto",     # S031 LatAm local
    "sakura",    # S032 India-focused
    "bluefin",
    "zephyr",
    "altamira",
    "helix",
    "tropos",
    "meridian",
]
PSP_TILT: Dict[str, float] = {
    "novapay": 0.015,   # S026
    "arcadia": 0.025,   # S027
    "kestrel": -0.005,  # S028
    "cedar": 0.005,     # S029 EU tilt
    "verdant": 0.00,
    "orion": 0.00,      # LatAm boost applied conditionally S030
    "kinto": 0.00,      # S031
    "sakura": 0.00,     # S032
    "bluefin": -0.005,
    "zephyr": -0.005,
    "altamira": 0.00,
    "helix": -0.01,
    "tropos": -0.01,
    "meridian": -0.005,
}
PSP_LATENCY_P50: Dict[str, float] = {  # S036; S039 multi-PSP cascade recovery applied in retry pass via processor swap (~22% on 2nd PSP)
    "novapay": 220, "arcadia": 190, "kestrel": 230, "cedar": 210, "verdant": 280,
    "orion": 340, "kinto": 330, "sakura": 260, "bluefin": 250, "zephyr": 310,
    "altamira": 260, "helix": 290, "tropos": 300, "meridian": 270,
}
PSP_ACQUIRER_COUNTRY: Dict[str, str] = {
    "novapay": "US", "arcadia": "NL", "kestrel": "US", "cedar": "GB", "verdant": "GB",
    "orion": "UY", "kinto": "BR", "sakura": "IN", "bluefin": "US", "zephyr": "AR",
    "altamira": "CA", "helix": "US", "tropos": "US", "meridian": "US",
}

# Card brands and share (S126)
CARD_BRANDS = ["visa", "mastercard", "amex", "discover", "jcb"]
CARD_BRAND_P = [0.52, 0.32, 0.09, 0.03, 0.04]

# Payment method catalog per country (S101–S110)
METHOD_CATALOG: Dict[str, List[Tuple[str, float, float]]] = {
    # country -> [(method, share, success)]
    "US": [("card", 0.94, None), ("apple_pay", 0.04, None), ("google_pay", 0.02, None)],  # S110 (ACH is AR, not in this book)
    "CA": [("card", 0.95, None), ("apple_pay", 0.03, None), ("google_pay", 0.02, None)],
    "GB": [("card", 0.70, None), ("bacs_dd", 0.18, 0.96), ("apple_pay", 0.08, None), ("google_pay", 0.04, None)],  # S102/S108
    "DE": [("card", 0.40, None), ("sepa_dd", 0.45, 0.94), ("apple_pay", 0.08, None), ("google_pay", 0.07, None)],  # S101/S108
    "FR": [("card", 0.80, None), ("sepa_dd", 0.15, 0.94), ("apple_pay", 0.05, None)],
    "NL": [("ideal", 0.70, 0.96), ("sepa_dd", 0.20, 0.94), ("card", 0.10, None)],  # S021/S103
    "SE": [("card", 0.80, None), ("swish", 0.15, 0.95), ("apple_pay", 0.05, None)],
    "NO": [("card", 0.85, None), ("apple_pay", 0.10, None), ("google_pay", 0.05, None)],
    "DK": [("card", 0.85, None), ("apple_pay", 0.10, None), ("google_pay", 0.05, None)],
    "FI": [("card", 0.85, None), ("apple_pay", 0.10, None), ("google_pay", 0.05, None)],
    "IT": [("card", 0.90, None), ("apple_pay", 0.07, None), ("google_pay", 0.03, None)],
    "ES": [("card", 0.90, None), ("apple_pay", 0.07, None), ("google_pay", 0.03, None)],
    "PT": [("card", 0.90, None), ("apple_pay", 0.07, None), ("google_pay", 0.03, None)],
    "PL": [("card", 0.55, None), ("blik", 0.42, 0.94), ("apple_pay", 0.03, None)],  # S022
    "CH": [("card", 0.60, None), ("twint", 0.35, 0.93), ("apple_pay", 0.05, None)],  # S023
    "AT": [("card", 0.55, None), ("sepa_dd", 0.40, 0.94), ("apple_pay", 0.05, None)],  # S101
    "BR": [("card", 0.50, None), ("pix", 0.40, 0.95), ("boleto", 0.10, 0.70)],  # S007/S104
    "MX": [("card", 0.70, None), ("oxxo", 0.25, 0.58), ("apple_pay", 0.05, None)],  # S008/S106
    "AR": [("card", 0.95, None), ("apple_pay", 0.05, None)],
    "CO": [("card", 0.85, None), ("pse", 0.15, 0.90)],
    "CL": [("card", 0.90, None), ("webpay", 0.10, 0.92)],
    "AU": [("card", 0.88, None), ("apple_pay", 0.08, None), ("google_pay", 0.04, None)],
    "NZ": [("card", 0.90, None), ("apple_pay", 0.06, None), ("google_pay", 0.04, None)],
    "JP": [("card", 0.80, None), ("konbini", 0.15, 0.80), ("apple_pay", 0.05, None)],
    "IN": [("card", 0.30, None), ("upi_autopay", 0.55, None), ("netbanking", 0.15, 0.85)],  # S010/S107
    "ID": [("card", 0.60, None), ("ovo", 0.25, 0.90), ("gopay", 0.15, 0.90)],
    "SG": [("card", 0.90, None), ("apple_pay", 0.08, None), ("google_pay", 0.02, None)],
    "TR": [("card", 0.98, None), ("apple_pay", 0.02, None)],
    "NG": [("card", 1.00, None)],
    "EG": [("card", 0.95, None), ("fawry", 0.05, 0.80)],
}

# Currency of method (if non-card)
CURRENCY_MAP = {c: v["cur"] for c, v in COUNTRY_BASE.items()}

# Issuers (fictitious names)
ISSUERS_GLOBAL = ["riverwood", "harborfirst", "ashford", "stonebridge", "summit_union",
                  "platinum_trust", "thornwall", "eastgate", "valois", "volga",
                  "fujimori", "maple_national", "caribou_bank"]
ISSUERS_REGIONAL = {
    "BR": ["pinkjay", "toucan_bank", "verdebank"],      # S131 BR neobank leader = pinkjay
    "IN": ["tigerfin", "lotusbank", "compassfin", "mangobank"],
    "US_CORP": ["flexworks", "surge_corp"],             # S132 corporate cards
    "US_NEOBANK": ["echobank"],                         # S130 neobank
}

@dataclass
class Shock:
    name: str
    start: datetime
    end: datetime
    effect: Dict  # arbitrary payload

# Shocks (10 dated events — anonymized labels)
SHOCKS: List[Shock] = [
    Shock("cloud_region_incident_alpha", datetime(2021,9,23,4,10), datetime(2021,9,23,10,40),
          {"psps": ["novapay", "kestrel"], "auth_delta": -0.40, "outage": True}),  # S033
    Shock("network_routing_incident_beta", datetime(2022,8,4,14,12), datetime(2022,8,4,15,35),
          {"psps": ["novapay"], "auth_delta": -0.40, "outage": True}),  # S034
    Shock("eu_psp_incident_gamma", datetime(2025,5,11,13,20), datetime(2025,5,11,14,55),
          {"psps": ["arcadia", "cedar"], "auth_delta": -0.15, "outage": True, "region": "EU"}),  # S035
    Shock("regulatory_churn_easing_2024", datetime(2024,11,4), datetime(2025,6,23),
          {"country": "US", "vol_churn_mult": 1.12}),  # S147
    Shock("jp_auth_regime_change", datetime(2025,4,1), datetime(2025,7,31),
          {"country": "JP", "auth_delta": -0.07}),  # S012 dip
    Shock("jp_auth_regime_recover", datetime(2025,8,1), datetime(2025,12,31),
          {"country": "JP", "auth_delta": -0.01}),  # S012 recovery
    Shock("ar_fx_regime_shift", datetime(2025,5,2), datetime(2025,12,31),
          {"country": "AR", "auth_delta": 0.08}),  # S009
    Shock("scheme_activity_program_launch", datetime(2025,4,1), datetime(2025,12,31),
          {"scheme_program": "enrolled"}),  # S113
    Shock("pix_automatico", datetime(2025,7,15), datetime(2025,12,31),
          {"country": "BR", "pix_automatico_ramp": True}),  # S105
    Shock("eu_sca", datetime(2023,1,1), datetime(2025,12,31),
          {"sca_active": True}),  # S056 (already in force by 2023)
]

# Out of dataset window (pre-2023) but referenced: S057 UK SCA 2022-03-14, S067 India e-mandate 2021-10-01, S068 3DS1 deprecation 2022-10-15. These are encoded as steady-state post-effect within the 2023-2025 window.

# --- Section 2: Helpers ---

def _choice(rng, items, p=None, size=None):
    return rng.choice(items, p=p, size=size)

def _tid(prefix: str, rng: np.random.Generator, n: int) -> np.ndarray:
    hex_ = rng.integers(0, 16**10, size=n)
    return np.array([f"{prefix}_{h:010x}" for h in hex_])

def _iso(dt_arr: np.ndarray) -> np.ndarray:
    # pandas handles vectorized iso
    return pd.to_datetime(dt_arr).strftime("%Y-%m-%dT%H:%M:%SZ").values

# --- Section 3: SKU catalogue (S086, S087, S089) ---

def build_skus(rng) -> pd.DataFrame:
    rows = []
    tiers = ["starter", "pro", "enterprise"]
    cadences = ["monthly", "annual", "usage", "multi_year"]
    regions = ["US", "EU", "APAC", "LATAM"]
    sku_id = 0
    for tier in tiers:
        for cad in cadences:
            for reg in regions:
                for variant in range(1, 4):  # 3*4*4*3 = 144 unique SKUs (keep all)
                    if sku_id >= 144:
                        break
                    if tier == "starter":
                        price = rng.uniform(19, 49)  # S086
                    elif tier == "pro":
                        price = rng.uniform(99, 299)
                    else:
                        price = rng.uniform(500, 2000)  # enterprise monthly base capped for card-realistic charges
                    if cad == "annual":
                        price = price * 12 * (1 - 0.17)  # S088
                    elif cad == "multi_year":
                        # Real SaaS multi-year deals are billed annually (not as one 2yr lump).
                        # Use annual-equivalent price with a deeper multi-year discount.
                        price = price * 12 * (1 - 0.22)
                    rows.append({
                        "sku_id": f"sku_{tier[:3]}_{cad[:3]}_{reg}_{variant}",
                        "sku_tier": tier,
                        "billing_cadence": cad,
                        "region": reg,
                        "list_price_usd": round(price, 2),
                    })
                    sku_id += 1
    return pd.DataFrame(rows)

# --- Section 4: Customers & subscriptions ---

def build_customers(rng, n=8000) -> pd.DataFrame:
    # Country weighting — US heavy, then EU, then APAC/LATAM
    country_weights = np.array([
        0.30,0.06,0.10,0.06,0.05,0.03,0.015,0.01,0.01,0.01,0.02,0.02,0.01,0.015,0.015,0.01,
        0.05,0.03,0.01,0.01,0.01,0.025,0.01,0.02,0.04,0.01,0.015,0.01,0.005,0.005,
    ])
    country_weights = country_weights / country_weights.sum()
    ctry = rng.choice(COUNTRIES, size=n, p=country_weights)
    # Cohort month (Jan 2022 – Dec 2025 so active in window)
    months_back = rng.integers(0, 48, size=n)
    base = datetime(2025, 12, 1)
    cohort = [base - timedelta(days=30*int(m)) for m in months_back]
    # Acquisition channel (S096, S100)
    acq = rng.choice(["self_serve", "sales_led"], size=n, p=[0.70, 0.30])
    return pd.DataFrame({
        "customer_id": [f"cus_{i:06d}" for i in range(n)],
        "customer_country": ctry,
        "cohort_month": cohort,
        "acquisition_channel": acq,
    })

def build_subscriptions(rng, customers: pd.DataFrame, skus: pd.DataFrame, n=10000) -> pd.DataFrame:
    # Tier weights: logos 60/30/10 (S086)
    cust_idx = rng.integers(0, len(customers), size=n)
    tier_draw = rng.choice(["starter", "pro", "enterprise"], size=n, p=[0.60, 0.30, 0.10])
    # Force Enterprise more sales_led (S096)
    cad_by_tier = {"starter": [0.80, 0.18, 0.02], "pro": [0.50, 0.45, 0.05], "enterprise": [0.15, 0.60, 0.25]}
    cad = np.empty(n, dtype=object)
    for t in ["starter", "pro", "enterprise"]:
        mask = tier_draw == t
        cad[mask] = rng.choice(["monthly", "annual", "multi_year"], size=mask.sum(),
                               p=cad_by_tier[t])
    # SKU lookup
    sku_ids = []
    for i in range(n):
        cand = skus[(skus.sku_tier == tier_draw[i]) & (skus.billing_cadence == cad[i])]
        if len(cand) == 0:
            cand = skus[skus.sku_tier == tier_draw[i]]
        sku_ids.append(cand.iloc[rng.integers(0, len(cand))]["sku_id"])
    # Start date after cohort
    start = [customers.iloc[cust_idx[i]]["cohort_month"] + timedelta(days=int(rng.integers(0, 90))) for i in range(n)]
    # Trial length (S089)
    trial_days = np.where(tier_draw == "enterprise", 30, 14)
    trial_end = [start[i] + timedelta(days=int(trial_days[i])) for i in range(n)]
    # Trial-to-paid (S082)
    converted = rng.random(n) < 0.22
    # But non-trial subs always "converted" (we treat non-converted as cancelled at trial end)
    sub = pd.DataFrame({
        "subscription_id": [f"sub_{i:07d}" for i in range(n)],
        "customer_id": customers.iloc[cust_idx]["customer_id"].values,
        "customer_country": customers.iloc[cust_idx]["customer_country"].values,
        "sku_id": sku_ids,
        "sku_tier": tier_draw,
        "billing_cadence": cad,
        "start_date": start,
        "trial_end": trial_end,
        "converted": converted,
    })
    sub = sub.merge(skus[["sku_id", "list_price_usd", "region"]], on="sku_id", how="left")
    # Enterprise custom pricing 80% off-list (S095)
    ent = sub.sku_tier == "enterprise"
    custom = ent & (rng.random(len(sub)) < 0.80)
    mult = np.where(custom, rng.uniform(0.5, 1.5, size=len(sub)), 1.0)
    sub["list_price_usd"] = sub["list_price_usd"] * mult
    # Cap enterprise list_price to card-realistic range with a rare 0.05% tail up to $50K.
    prices = sub["list_price_usd"].values.astype(float)
    over_cap = ent.values & (prices > 25000)
    if over_cap.any():
        keep_big = rng.random(over_cap.sum()) < 0.0005  # 0.05% survive as rare large card charges
        rescaled = prices[over_cap].copy()
        # Big tail: uniform $25K-$50K
        rescaled[keep_big] = rng.uniform(25000, 50000, size=keep_big.sum())
        # Rest: rescale to realistic $8K-$25K band
        rescaled[~keep_big] = rng.uniform(8000, 25000, size=(~keep_big).sum())
        prices[over_cap] = rescaled
        sub["list_price_usd"] = prices
    return sub

# --- Section 5: Attempt emission ---

def _in_shock(dt: datetime, shock: Shock) -> bool:
    return shock.start <= dt <= shock.end

_PM_CATEGORY = {
    "card": "card",
    "apple_pay": "wallet", "google_pay": "wallet",
    "sepa_dd": "dd", "bacs_dd": "dd",
}

def _ticket_weights(list_price: float) -> Dict[str, float]:
    # Real-world payment-method skew by ticket size (SaaS benchmarks, Stripe/Chargebee 2024).
    # Scope: card + wallets + SEPA/BACS DD + alt-locals. No ACH, no wire (those are AR, not payments team).
    # Cards retain tiny share even at $50K (the ~0.05% business-card edge case).
    if list_price < 500:
        return {"card": 1.00, "wallet": 1.00, "dd": 0.30, "alt": 1.00}
    if list_price < 5000:
        return {"card": 0.85, "wallet": 0.60, "dd": 1.50, "alt": 1.00}
    if list_price < 20000:
        return {"card": 0.35, "wallet": 0.10, "dd": 3.00, "alt": 0.40}
    if list_price < 50000:
        return {"card": 0.10, "wallet": 0.00, "dd": 4.00, "alt": 0.20}
    return {"card": 0.05, "wallet": 0.00, "dd": 4.00, "alt": 0.10}

def pick_payment_method(rng, ctry: str, date: datetime, list_price: float = 0.0) -> Tuple[str, float]:
    catalog = list(METHOD_CATALOG.get(ctry, [("card", 1.0, None)]))
    # S105: Pix Automático ramp post 2025-07-15 in BR
    if ctry == "BR" and date >= datetime(2025, 7, 15):
        days = (date - datetime(2025, 7, 15)).days
        ramp = min(0.35, days / 180 * 0.35)
        catalog = [("pix_automatico", ramp, 0.93)] + [(m, s*(1-ramp), x) for (m, s, x) in catalog]
    # S010/S107: UPI AutoPay decay Jan 2024 -> Nov 2025
    if ctry == "IN":
        new = []
        for (m, s, x) in catalog:
            if m == "upi_autopay":
                if date < datetime(2024,1,1):
                    succ = 0.72
                elif date >= datetime(2025,11,1):
                    succ = 0.38
                else:
                    frac = (date - datetime(2024,1,1)).days / (datetime(2025,11,1) - datetime(2024,1,1)).days
                    succ = 0.72 - frac * (0.72 - 0.38)
                new.append((m, s, succ))
            else:
                new.append((m, s, x))
        catalog = new

    # Ticket-size adjustment. Scope = cards, wallets, SEPA/BACS DD, alt-locals (no ACH, no wire).
    tw = _ticket_weights(list_price)
    adj = []
    for (m, s, x) in catalog:
        cat = _PM_CATEGORY.get(m, "alt")
        adj.append((m, s * tw.get(cat, 1.0), x))
    total = sum(a[1] for a in adj)
    if total <= 0:
        # All weights zeroed out — fall back to original shares
        adj = catalog
        total = sum(a[1] for a in adj)
    shares = np.array([a[1]/total for a in adj])
    idx = rng.choice(len(adj), p=shares)
    method, _, succ = adj[idx]
    return method, (succ if succ is not None else -1.0)

def country_auth(ctry: str, date: datetime, method: str) -> float:
    base = COUNTRY_BASE[ctry]["auth"]
    # S010 India UPI slump
    if ctry == "IN" and method == "card":
        base = 0.55
    # S011 e-mandate steady
    # S012 JP 3DS2 mandate dip
    if ctry == "JP" and datetime(2025,4,1) <= date <= datetime(2025,7,31):
        base -= 0.07
    # S009 AR cepo
    if ctry == "AR" and date >= datetime(2025,4,14):
        base += 0.08
    # S147 handled elsewhere (churn)
    return max(0.2, min(0.99, base))

def make_attempts(rng, subs: pd.DataFrame, n_target: int, start_date: datetime, end_date: datetime) -> pd.DataFrame:
    """Emit initial attempts (renewals + one-time). Retries added in a later pass."""
    # Filter converted only (S082). Non-converted subs generate 1 trial-fail attempt later.
    active = subs[subs.converted].reset_index(drop=True)
    # Months of activity per sub
    # Keep it simple: for each active sub, emit attempts from start to end_date per cadence.
    events: List[dict] = []
    # Precompute sub-level arrays
    cad = active["billing_cadence"].values
    start_dates = pd.to_datetime(active["start_date"]).values.astype("datetime64[D]")
    end_np = np.datetime64(end_date.date())
    # Cadence in days
    cad_days = np.where(cad == "monthly", 30, 365)  # annual & multi-year both billed yearly
    # Number of cycles per sub
    total_days = (end_np - start_dates).astype(int)
    n_cycles = np.maximum(0, total_days // cad_days) + 1
    # We want ~n_target rows total. Scale down if too many, else keep as-is.
    proj = n_cycles.sum()
    scale = min(1.0, n_target * 1.05 / max(1, proj))  # slight overshoot; trimmed below
    n_cycles = np.maximum(1, (n_cycles * scale).astype(int))

    sub_rows = []
    for i in range(len(active)):
        k = int(n_cycles[i])
        for c in range(k):
            day_offset = c * int(cad_days[i])
            sub_rows.append((i, c, day_offset))

    if len(sub_rows) > n_target:
        # Sample down
        keep = rng.choice(len(sub_rows), size=n_target, replace=False)
        sub_rows = [sub_rows[k] for k in keep]

    idx_arr = np.array([r[0] for r in sub_rows])
    seq_arr = np.array([r[1] for r in sub_rows])
    offset_arr = np.array([r[2] for r in sub_rows])

    df = active.iloc[idx_arr].reset_index(drop=True).copy()
    df["recurring_sequence"] = seq_arr
    # Billing date: start + offset + jitter
    base_dates = pd.to_datetime(df["start_date"]) + pd.to_timedelta(offset_arr, unit="D")
    # Day-of-month skew (S136/S137): shift to 1 or 15
    n = len(df)
    dom_roll = rng.random(n)
    shifted = base_dates.copy()
    # 35% to day-1, 18% to day-15, rest keep
    to_1 = dom_roll < 0.35
    to_15 = (dom_roll >= 0.35) & (dom_roll < 0.53)
    # Replace day
    shifted = pd.Series(shifted)
    shifted.loc[to_1] = shifted.loc[to_1].dt.to_period("M").dt.to_timestamp()  # day 1
    def _day15(dt):
        return dt.replace(day=15)
    shifted.loc[to_15] = shifted.loc[to_15].apply(_day15)
    # Random hour
    hours = rng.integers(0, 24, size=n)
    minutes = rng.integers(0, 60, size=n)
    seconds = rng.integers(0, 60, size=n)
    created = pd.to_datetime(shifted).dt.normalize() + pd.to_timedelta(hours, unit="h") + pd.to_timedelta(minutes, unit="m") + pd.to_timedelta(seconds, unit="s")
    # Clip to [start_date, end_date]
    created = created.clip(lower=pd.Timestamp(start_date), upper=pd.Timestamp(end_date))
    df["created_at"] = created.values
    df["is_retry"] = False
    df["attempt_number"] = 1
    df["retry_count"] = 0
    df["billing_reason"] = np.where(df["recurring_sequence"] == 0, "subscription_create", "subscription_cycle")
    return df

# --- Section 6: Enrichment (vectorized where possible) ---

def enrich(rng, df: pd.DataFrame) -> pd.DataFrame:
    n = len(df)
    created = pd.to_datetime(df["created_at"])
    created_dt = created.dt.to_pydatetime()

    # Payment method per row (loop — per-country/date logic; n~100k is fine)
    pm_type = np.empty(n, dtype=object)
    pm_succ = np.empty(n, dtype=float)
    lp_arr = df["list_price_usd"].values.astype(float)
    for i in range(n):
        m, s = pick_payment_method(rng, df["customer_country"].iat[i], created_dt[i], float(lp_arr[i]))
        pm_type[i] = m
        pm_succ[i] = s
    df["payment_method_type"] = pm_type

    # Card-specific fields (S126)
    is_card = np.isin(pm_type, ["card"])
    brand = np.where(is_card, rng.choice(CARD_BRANDS, size=n, p=CARD_BRAND_P), "")
    # S127: Amex skew on enterprise
    amex_boost = (df["sku_tier"] == "enterprise").values & (rng.random(n) < 0.12)
    brand = np.where(is_card & amex_boost, "amex", brand)
    df["card_brand"] = brand
    df["card_bin"] = np.where(is_card, rng.integers(400000, 699999, size=n).astype(str), "")
    df["card_last4"] = np.where(is_card, rng.integers(0, 9999, size=n).astype(str), "")
    # Card expiry (22% within 12mo, S135)
    exp_years = rng.choice([1, 2, 3, 4], size=n, p=[0.22, 0.30, 0.28, 0.20])
    exp_months = rng.integers(1, 13, size=n)
    df["card_expiry_date"] = np.where(is_card,
        [f"{2026+int(exp_years[i])-1:04d}-{int(exp_months[i]):02d}" for i in range(n)], "")
    # Card funding (S128/S129)
    funding = rng.choice(["credit", "debit", "prepaid"], size=n, p=[0.60, 0.35, 0.05])
    df["card_funding_type"] = np.where(is_card, funding, "")
    df["card_category"] = np.where(is_card, rng.choice(["consumer", "commercial"], size=n, p=[0.75, 0.25]), "")
    df["card_fingerprint"] = np.where(is_card, [f"fp_{rng.integers(0, 2**32):08x}" for _ in range(n)], "")
    # Card country: mostly same as customer, 10% cross-border (S017/S134)
    same = rng.random(n) < 0.90
    card_ctry = np.where(same, df["customer_country"].values, rng.choice(COUNTRIES, size=n))
    df["card_country"] = np.where(is_card, card_ctry, "")
    # Issuer (S130–S132)
    def _pick_issuer(i):
        ctry = df["customer_country"].iat[i]
        if not is_card[i]:
            return ""
        if ctry == "BR" and rng.random() < 0.25:
            return rng.choice(ISSUERS_REGIONAL["BR"])
        if ctry == "IN":
            return rng.choice(ISSUERS_REGIONAL["IN"])
        if ctry == "US" and df["sku_tier"].iat[i] == "enterprise" and rng.random() < 0.40:
            return rng.choice(ISSUERS_REGIONAL["US_CORP"])
        if ctry == "US" and rng.random() < 0.05:
            return rng.choice(ISSUERS_REGIONAL["US_NEOBANK"])
        return rng.choice(ISSUERS_GLOBAL)
    issuers = [_pick_issuer(i) for i in range(n)]
    df["issuer_name"] = issuers
    df["issuer_id"] = [f"iss_{abs(hash(x))%10**6:06d}" if x else "" for x in issuers]
    df["issuer_parent_group"] = df["issuer_name"]

    # Wallet
    df["wallet_provider"] = np.where(np.isin(pm_type, ["apple_pay", "google_pay"]), pm_type, "")

    # Processor selection (S030/S032 regional preference; default novapay)
    # Bug 2 fix: ensure ALL 14 PSPs appear with novapay dominant (~40-50% share).
    # Default (US + other) draws from a 14-PSP mix weighted toward novapay.
    default_pool = ["novapay", "kestrel", "bluefin", "altamira", "helix",
                    "tropos", "meridian", "verdant", "arcadia"]
    default_p = [0.48, 0.12, 0.08, 0.08, 0.07, 0.06, 0.05, 0.03, 0.03]
    proc = rng.choice(default_pool, size=n, p=default_p).astype(object)
    # LatAm -> orion/kinto dominant, plus zephyr
    latam_mask = df["customer_country"].isin(list(LATAM)).values
    proc[latam_mask] = rng.choice(
        ["orion", "kinto", "zephyr", "novapay", "arcadia"],
        size=latam_mask.sum(), p=[0.35, 0.25, 0.15, 0.15, 0.10])
    # India -> sakura
    in_mask = (df["customer_country"] == "IN").values
    proc[in_mask] = rng.choice(["sakura", "novapay"], size=in_mask.sum(), p=[0.70, 0.30])
    # EU — mixed
    eu_mask = df["customer_country"].isin(list(EU_COUNTRIES)).values
    proc[eu_mask] = rng.choice(
        ["arcadia", "novapay", "cedar", "verdant", "meridian", "altamira"],
        size=eu_mask.sum(), p=[0.38, 0.28, 0.15, 0.10, 0.05, 0.04])
    # Enterprise prefers arcadia (S027)
    ent_mask = (df["sku_tier"] == "enterprise").values
    switch = ent_mask & (rng.random(n) < 0.35)
    proc[switch] = "arcadia"
    df["processor"] = proc
    df["acquirer_country"] = np.array([PSP_ACQUIRER_COUNTRY.get(p, "US") for p in proc])
    df["acquirer_bin"] = np.array([f"{abs(hash(p))%900000+100000:06d}" for p in proc])
    df["processor_merchant_id"] = np.array([f"mch_{p}_cirrus" for p in proc])

    # Provider latency (S036)
    p50 = np.array([PSP_LATENCY_P50[p] for p in proc])
    df["provider_latency_ms"] = (rng.lognormal(mean=0, sigma=0.4, size=n) * p50).astype(int)
    df["processing_time_ms"] = df["provider_latency_ms"] + rng.integers(20, 200, size=n)

    # SCA / 3DS (S056–S070)
    is_eu = df["customer_country"].isin(list(EU_COUNTRIES)).values
    is_cit = (df["billing_reason"] == "subscription_create").values
    is_mit = ~is_cit
    # MIT exemption on EU recurring (S058)
    mit_exempt = is_eu & is_mit & (rng.random(n) < 0.72)
    # TRA on eligible CIT (S059)
    tra_exempt = is_eu & is_cit & (rng.random(n) < 0.40)
    # LVP (S060)
    lvp_exempt = is_eu & (df["sku_tier"].values == "starter") & (rng.random(n) < 0.05)
    sca_exempt = np.full(n, "", dtype=object)
    sca_exempt[mit_exempt] = "mit"
    sca_exempt[tra_exempt] = "tra"
    sca_exempt[lvp_exempt] = "lvp"
    # OLO (S061): non-EEA card, EU merchant
    olo_mask = is_eu & (~np.isin(df["card_country"], list(EU_COUNTRIES))) & is_card & (sca_exempt == "") & (rng.random(n) < 0.12)
    sca_exempt[olo_mask] = "olo"
    df["sca_exemption"] = sca_exempt

    # 3DS version — post 2022-10-15 force 2.x (S068)
    tds_ver = np.where(is_card, "2.2.0", "")
    # Wallet biometric = frictionless (S069)
    wallet_bio = np.isin(pm_type, ["apple_pay", "google_pay"])
    frictionless_base = rng.random(n) < 0.82  # S062
    frictionless = wallet_bio | (is_eu & is_cit & (sca_exempt == "") & frictionless_base)
    df["three_ds_version"] = tds_ver
    df["three_ds_frictionless"] = frictionless
    df["three_ds_status"] = np.where(frictionless, "Y", np.where(is_card & is_eu & is_cit & (sca_exempt == ""), "C", ""))
    # Challenge? (S063)
    device = rng.choice(["mobile", "desktop", "tablet"], size=n, p=[0.55, 0.40, 0.05])
    df["device_type"] = device
    challenge = (df["three_ds_status"] == "C")
    abandoned = challenge & (((device == "mobile") & (rng.random(n) < 0.18)) | ((device == "desktop") & (rng.random(n) < 0.09)))
    df["three_ds_challenge"] = challenge
    df["three_ds_challenge_type"] = np.where(challenge, "otp", "")
    df["three_ds_abandoned"] = abandoned  # S063 — explicit abandonment flag
    df["three_ds_data_only_flow"] = False
    # ECI (S066)
    eci = np.where(is_card,
                   rng.choice(["05", "06", "07"], size=n, p=[0.70, 0.25, 0.05]), "")
    df["eci"] = eci
    df["authentication_flow"] = np.where(frictionless, "frictionless", np.where(challenge, "challenge", ""))
    df["pares_status"] = df["three_ds_status"]
    df["three_ds_server_tx_id"] = np.where(is_card & is_eu, _tid("tds", rng, n), "")
    df["three_ds_ds_tx_id"] = df["three_ds_server_tx_id"]
    df["three_ds_acs_tx_id"] = df["three_ds_server_tx_id"]
    df["cavv"] = np.where(frictionless, _tid("cavv", rng, n), "")

    # Cross-border flag (S017)
    df["is_cross_border"] = is_card & (df["card_country"].values != df["acquirer_country"].values) & (df["card_country"].values != "")

    # --- Compute approval probability (vectorized) ---
    p_auth = np.array([country_auth(df["customer_country"].iat[i], created_dt[i], pm_type[i]) for i in range(n)])
    # PSP tilt (S026–S029, S031, S032)
    p_auth = p_auth + np.array([PSP_TILT[p] for p in proc])
    # LatAm boost for orion/kinto (S030/S031)
    latam_boost = (np.isin(proc, ["orion", "kinto"]) & latam_mask)
    p_auth = np.where(latam_boost, p_auth + 0.08, p_auth)
    # Local acquiring lift (S025)
    local = (df["card_country"].values == df["acquirer_country"].values) & is_card
    p_auth = np.where(local, p_auth + 0.09, p_auth)
    # Cross-border drag (S017) — soften to avoid compounding below realism
    p_auth = np.where(df["is_cross_border"].values, p_auth * 0.93, p_auth)
    # USD on non-US card drag (S018)
    # USD determined below, skip for now
    # Weekend drag (S144)
    dow = pd.to_datetime(df["created_at"]).dt.dayofweek.values
    p_auth = np.where((dow >= 5), p_auth - 0.015, p_auth)
    # Method-specific success for non-card
    has_succ = pm_succ > 0
    p_auth = np.where(has_succ, pm_succ, p_auth)
    # Abandoned challenge → fail
    p_auth = np.where(abandoned, 0.0, p_auth)
    # SCA exemption uplifts
    p_auth = np.where(sca_exempt == "tra", p_auth + 0.10, p_auth)  # S064
    p_auth = np.where(sca_exempt == "mit", p_auth + 0.07, p_auth)  # S065 MIT chaining (EU)
    # S065 non-EU MIT/COF chaining uplift — subscription_cycle + card, any region
    non_eu_mit = is_mit & is_card & (~is_eu)
    p_auth = np.where(non_eu_mit, p_auth + 0.05, p_auth)
    # Prepaid penalty (S128)
    prepaid = (df["card_funding_type"].values == "prepaid") & (df["billing_reason"].values == "subscription_cycle")
    p_auth = np.where(prepaid, p_auth - 0.15, p_auth)
    # Debit penalty (S129)
    p_auth = np.where(df["card_funding_type"].values == "debit", p_auth - 0.02, p_auth)
    # Network tokens (S038/S133)
    network_token = is_card & (rng.random(n) < 0.45)
    visa_tok = network_token & (brand == "visa")
    mc_tok = network_token & (brand == "mastercard")
    p_auth = np.where(visa_tok, p_auth + 0.04, p_auth)
    p_auth = np.where(mc_tok, p_auth + 0.03, p_auth)
    df["token_type"] = np.where(network_token, "network_token", np.where(is_card, "pan", ""))
    df["token_requestor_id"] = np.where(network_token, _tid("trid", rng, n), "")
    df["is_tokenized"] = network_token | is_card  # most card txns tokenized via vault
    df["vaulted_token_id"] = np.where(is_card, _tid("tok", rng, n), "")

    # Outage shocks (S033–S035)
    is_outage = np.zeros(n, dtype=bool)
    for sh in SHOCKS:
        if "outage" in sh.effect:
            psps = sh.effect.get("psps", [])
            mask = np.array([(sh.start <= created_dt[i] <= sh.end) and proc[i] in psps for i in range(n)])
            is_outage |= mask
            p_auth = np.where(mask, p_auth + sh.effect["auth_delta"], p_auth)
    df["is_outage"] = is_outage
    # Country-scoped auth shocks (S012 JP 3DS2 mandate, S009 AR cepo, etc.)
    ctry_arr = df["customer_country"].values
    for sh in SHOCKS:
        if "country" in sh.effect and "auth_delta" in sh.effect:
            cty = sh.effect["country"]
            mask = np.array([(sh.start <= created_dt[i] <= sh.end) and ctry_arr[i] == cty for i in range(n)])
            p_auth = np.where(mask, p_auth + sh.effect["auth_delta"], p_auth)
    # S011 IN card >₹15K (~180 USD) auth uplift — high-value IN card tx pass through
    # stricter KYC/e-mandate flow and have materially better auth than mid-value.
    in_big_card = (ctry_arr == "IN") & (pm_type == "card") & (df["list_price_usd"].values >= 180)
    p_auth = np.where(in_big_card, p_auth + 0.18, p_auth)

    # Smart Retries uplift (S037) — applied later at retry stage for novapay

    # Clip and draw — clamp to [0.4, 0.98] AFTER multipliers so drags can't compound
    # below realistic SaaS approval floors (Bug 3 fix). Abandoned challenges retain p=0.
    abandoned_mask = abandoned.copy()
    p_auth = np.clip(p_auth, 0.40, 0.98)
    p_auth = np.where(abandoned_mask, 0.0, p_auth)
    approved = rng.random(n) < p_auth
    df["is_approved"] = approved
    df["status"] = np.where(approved, "succeeded", "failed")
    df["settled_flag"] = approved
    df["captured_amount"] = np.where(approved, df.get("list_price_usd", pd.Series([0]*n)).values, 0)

    # Response codes
    df["response_code"] = np.where(approved, "00", "05")
    df["response_message"] = np.where(approved, "Approved", "Declined")
    df["provider_status"] = df["status"]
    df["provider_response_code"] = df["response_code"]
    df["merchant_advice_code"] = ""

    # Decline categories & codes (S024, S070)
    declined = ~approved
    dec_codes = rng.choice(
        ["do_not_honor", "insufficient_funds", "expired_card", "lost_stolen", "3ds_required", "generic"],
        size=n, p=[0.36, 0.22, 0.08, 0.04, 0.06, 0.24]
    )
    # S070: SCA-required decline in EU CNP (~4%)
    sca_req_mask = declined & is_eu & is_card & (rng.random(n) < 0.04)
    dec_codes = np.where(sca_req_mask, "sca_required", dec_codes)
    df["decline_category"] = np.where(declined, dec_codes, "")
    # S016 RU corridor closed — not in dataset (RU not in COUNTRIES list) — skipped cleanly.

    # --- Amount & currency ---
    list_price = df["list_price_usd"].values
    cur = df["customer_country"].map(CURRENCY_MAP).values
    # Top-7 currency concentration (S099): force ~85% into top set
    top7 = {"USD", "EUR", "GBP", "BRL", "INR", "AUD", "JPY"}
    # For currencies not in top7, 50% get remapped to USD
    remap = np.array([c not in top7 for c in cur]) & (rng.random(n) < 0.5)
    cur = np.where(remap, "USD", cur)
    df["currency"] = cur
    # Cross-country customer: sometimes USD-billed (S018)
    usd_force = (df["sku_tier"].values == "enterprise") & (rng.random(n) < 0.30)
    df["currency"] = np.where(usd_force, "USD", df["currency"].values)
    # S018 USD on non-US card drag — apply retroactively (approximate)
    # already folded into base approval via country_auth; ignore for perf.

    # FX
    fx_map = {"USD":1.0, "EUR":1.08, "GBP":1.27, "BRL":0.19, "INR":0.012, "AUD":0.66,
              "JPY":0.0068, "CAD":0.73, "SEK":0.095, "NOK":0.094, "DKK":0.14,
              "PLN":0.25, "CHF":1.12, "MXN":0.055, "ARS":0.0011, "COP":0.00025,
              "CLP":0.0011, "NZD":0.60, "IDR":0.000063, "SGD":0.74, "TRY":0.030,
              "NGN":0.00062, "EGP":0.020}
    fx = np.array([fx_map.get(c, 1.0) for c in df["currency"].values])
    df["fx_rate"] = fx
    amount = list_price / fx
    df["amount"] = np.round(amount, 2)
    df["amount_usd"] = np.round(list_price, 2)
    df["captured_amount"] = np.where(approved, df["amount"].values, 0.0)
    df["refunded_amount"] = 0.0
    df["fx_spread_pct"] = np.where(df["currency"].values == "USD", 0.0, 0.02)
    df["settlement_currency"] = df["currency"]
    is_dd = np.isin(pm_type, ["sepa_dd", "bacs_dd"])
    df["settlement_delay_days"] = np.where(is_dd, 4, np.where(approved, rng.integers(1, 3, size=n), 0))  # DD rails settle in 3-5d vs 1-2d for cards

    # Timestamps
    created_ts = pd.to_datetime(df["created_at"])
    auth_ts = created_ts + pd.to_timedelta(df["provider_latency_ms"], unit="ms")
    df["authorized_at"] = np.where(approved, auth_ts.dt.strftime("%Y-%m-%dT%H:%M:%SZ"), "")
    cap_ts = auth_ts + pd.to_timedelta(rng.integers(0, 3600, size=n), unit="s")
    df["captured_at"] = np.where(approved, cap_ts.dt.strftime("%Y-%m-%dT%H:%M:%SZ"), "")
    settle_ts = cap_ts + pd.to_timedelta(df["settlement_delay_days"], unit="D")
    df["settled_at"] = np.where(approved, settle_ts.dt.strftime("%Y-%m-%dT%H:%M:%SZ"), "")
    df["created_at"] = created_ts.dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    # Fees (S040) — per-processor formulas
    def _fee_rate(p):
        return {"novapay": 0.028, "arcadia": 0.021, "kestrel": 0.030, "cedar": 0.024,
                "verdant": 0.027, "orion": 0.034, "kinto": 0.036, "sakura": 0.026,
                "bluefin": 0.028, "zephyr": 0.036, "altamira": 0.023, "helix": 0.026,
                "tropos": 0.024, "meridian": 0.022}.get(p, 0.028)
    fee_rates = np.array([_fee_rate(p) for p in proc])
    fixed = np.where(proc == "novapay", 0.25, 0.0)
    df["fee_rate"] = fee_rates
    df["processing_fee_usd"] = np.where(approved, np.round(df["amount_usd"].values * fee_rates + fixed, 2), 0.0)
    df["interchange_fee_usd"] = np.where(approved, np.round(df["amount_usd"].values * 0.018, 2), 0.0)
    df["scheme_fee_usd"] = np.where(approved, np.round(df["amount_usd"].values * 0.0013, 2), 0.0)
    df["fee_tax_amount_usd"] = 0.0
    df["net_amount_usd"] = np.where(approved,
        np.round(df["amount_usd"].values - df["processing_fee_usd"].values - df["interchange_fee_usd"].values - df["scheme_fee_usd"].values, 2), 0.0)

    # Risk (S111/S120–S124)
    # IP country mostly matches (S121)
    ip_same = rng.random(n) < 0.92
    df["customer_ip_country"] = np.where(ip_same, df["customer_country"].values, rng.choice(COUNTRIES, size=n))
    ip_mismatch = df["customer_ip_country"].values != df["customer_country"].values
    risk = rng.uniform(0, 100, size=n)
    risk = np.where(ip_mismatch, risk + 25, risk)  # S121
    # S145: 2–5am local = 3x fraud — approximate via UTC hour +/- offset (we just bump risk 2–5 UTC)
    hr = pd.to_datetime(df["created_at"]).dt.hour.values
    late_night = (hr >= 2) & (hr <= 5)
    risk = np.where(late_night, risk + 15, risk)
    risk = np.clip(risk, 0, 100)
    df["risk_score"] = np.round(risk, 1)
    df["risk_decision"] = np.where(risk > 80, "review", np.where(risk > 60, "elevated", "approve"))
    df["risk_provider"] = np.where(proc == "novapay", "ml_screen", "built_in")
    df["fraud_screening_status"] = "screened"
    df["is_standalone_screening"] = False
    # S124 ML fraud-screen block
    ml_block = (df["risk_provider"] == "ml_screen") & (rng.random(n) < 0.01)
    df.loc[ml_block, "is_approved"] = False
    df.loc[ml_block, "status"] = "blocked"
    df.loc[ml_block, "decline_category"] = "ml_blocked"
    df["cvv_result"] = np.where(is_card, rng.choice(["M", "N", "U"], size=n, p=[0.92, 0.04, 0.04]), "")
    df["avs_result"] = np.where(is_card, rng.choice(["Y", "A", "Z", "N"], size=n, p=[0.70, 0.12, 0.10, 0.08]), "")

    # Channel, returning, device
    df["channel"] = rng.choice(["web", "mobile_web", "in_app", "api"], size=n, p=[0.50, 0.25, 0.15, 0.10])
    df["is_returning_customer"] = df["recurring_sequence"].values > 0

    # Fraud flag (S111, S121, S122) — calibrated to land CNP fraud rate in 8-20bp band
    # with ip_mismatch producing ~5× lift over match.
    fraud_base = 0.0003
    new_acct = df["recurring_sequence"].values == 0
    fraud_p = np.full(n, fraud_base)
    fraud_p = np.where(new_acct, fraud_p * 8, fraud_p)       # S122 new-account 8×
    fraud_p = np.where(ip_mismatch, fraud_p * 5, fraud_p)    # S121 IP-mismatch 5×
    fraud_p = np.where(late_night, fraud_p * 3, fraud_p)     # S145 night hours
    is_fraud = rng.random(n) < fraud_p
    df["is_fraud"] = is_fraud
    # S123 trial abuse — mark sub_status
    trial_abuse = new_acct & (rng.random(n) < 0.03)
    df["sub_status"] = np.where(trial_abuse, "trial_abuse", "")

    # Chargebacks (S112, S115, S125)
    cb_eligible = df["is_approved"].values & is_card
    cb_flag = cb_eligible & (rng.random(n) < 0.0075)
    cb_lag_days = rng.lognormal(mean=np.log(45), sigma=0.5, size=n).astype(int)
    cb_date = pd.to_datetime(df["created_at"]) + pd.to_timedelta(cb_lag_days, unit="D")
    df["chargeback_amount"] = np.where(cb_flag, df["amount_usd"].values, 0.0)
    df["chargeback_date"] = np.where(cb_flag, cb_date.dt.strftime("%Y-%m-%dT%H:%M:%SZ"), "")
    df["in_dispute_amount"] = np.where(cb_flag, df["amount_usd"].values, 0.0)
    df["in_dispute_date"] = np.where(cb_flag, cb_date.dt.strftime("%Y-%m-%dT%H:%M:%SZ"), "")
    df["disputed"] = cb_flag
    df["chargeback_count"] = cb_flag.astype(int)
    # Reason code in decline_category for chargebacks — store in sub_status chain
    df.loc[cb_flag, "sub_status"] = rng.choice(
        ["cb_10.4_fraud", "cb_13.1_recurring", "cb_13.2_cancelled", "cb_other"],
        size=int(cb_flag.sum()), p=[0.55, 0.15, 0.10, 0.20])
    # S116/S117/S118 — representment outcomes stored in representment_status
    repr_status = np.full(n, "", dtype=object)
    ce_win = cb_flag & (rng.random(n) < 0.65)
    pre_arb = cb_flag & (rng.random(n) < 0.30)
    early_warn = cb_flag & (rng.random(n) < 0.20)
    repr_status = np.where(ce_win, "representment_won", repr_status)
    repr_status = np.where(pre_arb, "pre_arbitration_refund", repr_status)
    repr_status = np.where(early_warn, "early_warning_caught", repr_status)
    df["representment_status"] = repr_status
    df["compelling_evidence_score"] = np.where(ce_win, rng.uniform(0.7, 1.0, size=n), 0.0)
    df["refund_status"] = np.where(pre_arb, "refunded", "")

    # --- Populate remaining columns ---
    df["transaction_id"] = _tid("txn", rng, n)
    df["merchant_transaction_id"] = _tid("mtxn", rng, n)
    df["provider_transaction_id"] = _tid("ptxn", rng, n)
    df["order_id"] = _tid("ord", rng, n)
    df["merchant_id"] = "cirrus_001"
    df["parent_transaction_id"] = ""
    df["payment_method_subtype"] = ""
    df["routing_rule_id"] = rng.choice(["rule_primary", "rule_fallback", "rule_local"], size=n, p=[0.80, 0.12, 0.08])
    df["routing_strategy"] = np.where(df["sku_tier"] == "enterprise", "lowest_cost", "highest_auth")
    df["route_layer"] = "primary"
    df["route_steps_count"] = 1
    df["payment_retry_count"] = df["retry_count"]
    df["smart_routing"] = df["processor"] == "novapay"  # S037 hint
    df["retry_status"] = ""
    df["merchant_name"] = "Cirrus Cloud Platform"
    df["merchant_country"] = "US"
    df["merchant_mcc"] = rng.choice([5734, 7372, 5968], size=n, p=[0.30, 0.60, 0.10])
    df["merchant_vertical"] = "SaaS"
    df["merchant_tier"] = "enterprise"
    df["org_id"] = "org_cirrus"
    df["industry"] = "SaaS"
    df["is_test"] = False
    df["reconciliation_status"] = np.where(df["settled_flag"], "reconciled", "pending")
    df["reconciliation_id"] = _tid("rec", rng, n)
    df["merchant_account_id"] = np.array([f"ma_{p}_{df['currency'].iat[i]}" for i, p in enumerate(proc)])
    df["checkout_session_id"] = _tid("cs", rng, n)
    df["merchant_reference"] = df["subscription_id"].values
    df["idempotency_key"] = _tid("idem", rng, n)
    df["intent"] = np.where(df["billing_reason"] == "subscription_create", "setup", "charge")
    df["payment_source"] = np.where(is_mit, "off_session", "on_session")
    df["is_subsequent_payment"] = is_mit
    df["account_funding_transaction"] = False
    df["statement_descriptor"] = "NIMBUS*CLOUD"
    df["buyer_id"] = df["customer_id"]
    df["capture_success"] = df["is_approved"]
    df["capture_delay_hours"] = np.where(df["is_approved"], rng.uniform(0, 2, size=n).round(2), 0.0)
    df["auth_expired_at_capture"] = False
    df["is_incremental_auth"] = False
    df["is_reauth"] = False
    df["dunning_retry_day"] = 0
    df["account_updater_triggered"] = False  # set during retry pass
    # S146 Setup intent / $0 auth
    setup_intent = is_eu & is_cit & (rng.random(n) < 0.25)
    # Mark via intent column
    df.loc[setup_intent, "intent"] = "setup_intent"
    df["wallet_idv_path"] = ""
    df["is_split_payment"] = False
    df["sub_merchant_id"] = ""
    df["seller_rolling_reserve_pct"] = 0.0
    df["presence_mode"] = "cnp"
    df["level_data"] = ""
    df["dcc_offered"] = False
    df["dcc_accepted"] = False
    df["fx_lock_point"] = ""
    df["is_payout"] = False
    df["payout_rail"] = ""
    df["payout_failure_rate_flag"] = False
    df["psp_business_model"] = np.where(np.isin(proc, ["novapay", "kestrel", "bluefin"]), "aggregator", "gateway")
    df["carries_cb_risk"] = df["psp_business_model"] == "aggregator"
    df["scheme_transaction_id"] = np.where(is_card, _tid("sch", rng, n), "")
    # S065: MIT chains reference prior scheme tx
    df["previous_scheme_transaction_id"] = np.where(is_mit & is_card, _tid("sch", rng, n), "")
    df["authorization_code"] = np.where(df["is_approved"] & is_card, [f"A{rng.integers(100000,999999):06d}" for _ in range(n)], "")
    df["transaction_type"] = np.where(df["recurring_sequence"] == 0, "trial", "subscription")
    df["is_recurring"] = True
    df["recurring_count"] = df["recurring_sequence"] + 1
    df["is_installment"] = False
    df["installment_count"] = 0
    df["collection_method"] = "charge_automatically"  # S plg default
    # Trial-end / periods
    start_dt = pd.to_datetime(df["start_date"])
    trial_end_dt = pd.to_datetime(df["trial_end"])
    df["trial_end"] = trial_end_dt.dt.strftime("%Y-%m-%d")
    df["current_period_start"] = created_ts.dt.strftime("%Y-%m-%d")
    cad_days_vec = np.where(df["billing_cadence"] == "monthly", 30,
                    np.where(df["billing_cadence"] == "annual", 365, 730))
    df["current_period_end"] = (created_ts + pd.to_timedelta(cad_days_vec, unit="D")).dt.strftime("%Y-%m-%d")
    df["proration_amount_usd"] = 0.0
    # S092 — flag ~5% of cycle rows as mid-cycle upgrades; 95% of those carry nonzero proration.
    cycle_mask = (df["billing_reason"].values == "subscription_cycle")
    upgrade_pick = cycle_mask & (rng.random(n) < 0.05)
    df.loc[upgrade_pick, "billing_reason"] = "subscription_update"
    prorate_mask = upgrade_pick & (rng.random(n) < 0.95)
    list_price_arr = df["list_price_usd"].values.astype(float)
    prorate_idx = np.where(prorate_mask)[0]
    if len(prorate_idx) > 0:
        df.loc[prorate_idx, "proration_amount_usd"] = list_price_arr[prorate_idx] * rng.uniform(0.1, 0.9, size=len(prorate_idx))
    df["next_payment_attempt"] = (created_ts + pd.to_timedelta(cad_days_vec, unit="D")).dt.strftime("%Y-%m-%d")

    # invoice_id
    df["invoice_id"] = _tid("inv", rng, n)
    return df

# --- Section 7: Retry ladder (S041–S055) ---

def emit_retries(rng, df: pd.DataFrame, cap_rows: int) -> pd.DataFrame:
    """For declined rows, emit up to 3 retries with decaying recovery."""
    declined = df[~df["is_approved"]].copy()
    if len(declined) == 0 or cap_rows <= 0:
        return pd.DataFrame(columns=df.columns)
    # Cap total retry rows across all 3 levels ~ cap_rows. Level-1 is about 55% of total
    # because level-2 and level-3 only fire on failed retries (~85% & ~72% of prior).
    max_retries = min(len(declined), max(1, int(cap_rows * 0.55)))
    declined = declined.sample(n=max_retries, random_state=int(rng.integers(0, 2**31)))

    retry_frames = []
    recov = [0.15, 0.09, 0.05]  # S043/S044/S045
    offsets = [1, 3, 7]          # S041
    for rt in range(3):
        n = len(declined)
        if n == 0:
            break
        retry = declined.copy()
        retry["attempt_number"] = rt + 2
        retry["is_retry"] = True
        retry["retry_count"] = rt + 1
        retry["payment_retry_count"] = rt + 1
        retry["parent_transaction_id"] = declined["transaction_id"].values
        # S039 Multi-PSP cascade: with ~22% probability swap processor to a different PSP on retry.
        orig_proc = declined["processor"].values
        cascade_draw = rng.choice(PSPS, size=n)
        cascade_mask = (rng.random(n) < 0.22) & (cascade_draw != orig_proc)
        new_proc = np.where(cascade_mask, cascade_draw, orig_proc)
        retry["processor"] = new_proc
        # Shift created_at
        new_created = pd.to_datetime(declined["created_at"]) + pd.to_timedelta(offsets[rt], unit="D")
        # S042 align to 1st/15th payday — nudge ~30% of retries
        to_payday = rng.random(n) < 0.30
        new_created = pd.Series(new_created.values)
        new_created.loc[to_payday] = new_created.loc[to_payday].apply(
            lambda d: d.replace(day=1) if d.day > 7 else d.replace(day=15))
        retry["created_at"] = pd.to_datetime(new_created).dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        # Compute recovery prob — smart retries (S037) bump on novapay
        base_recov = np.full(n, recov[rt])
        base_recov = np.where(declined["processor"].values == "novapay", base_recov + 0.11, base_recov)  # S037
        # S046/S047 network-updater coverage on expired cards; S050 tier-1 PSPs real-time, mid-tier batch
        expired = (declined["decline_category"].values == "expired_card")
        us_card = (declined["card_country"].values == "US")
        eu_card = declined["card_country"].isin(list(EU_COUNTRIES)).values
        vau_hit = expired & ((us_card & (rng.random(n) < 0.72)) | (eu_card & (rng.random(n) < 0.45)))
        # S047 MC ABU adoption 68% US / 40% EU — similar gate, folded into vau_hit above
        # Silent refresh: 60% of VAU hits succeed (S048)
        retry["account_updater_triggered"] = vau_hit
        base_recov = np.where(vau_hit, 0.60, base_recov)
        # S049 network token refresh
        tok_refresh = (declined["token_type"].values == "network_token") & (rng.random(n) < 0.95)
        base_recov = np.where(tok_refresh & expired, 0.95, base_recov)
        # S052 dunning email open rate 48%/22%/12% — approximated by channel roll decay
        # S053 in-app banner channel +6pp
        banner = rng.random(n) < 0.30
        base_recov = np.where(banner, base_recov + 0.06, base_recov)
        recovered = rng.random(n) < base_recov
        retry["is_approved"] = recovered
        retry["status"] = np.where(recovered, "succeeded", "failed")
        retry["response_code"] = np.where(recovered, "00", "05")
        retry["response_message"] = np.where(recovered, "Approved", "Declined")
        retry["settled_flag"] = recovered
        retry["dunning_retry_day"] = offsets[rt]
        retry["retry_status"] = np.where(recovered, "recovered", "failed")
        # New transaction IDs — but keep order_id from the parent so multi-PSP cascade
        # across attempts is visible (S039 verifier groups by order_id).
        retry["transaction_id"] = _tid("txn", rng, n)
        retry["merchant_transaction_id"] = _tid("mtxn", rng, n)
        retry["provider_transaction_id"] = _tid("ptxn", rng, n)
        retry["idempotency_key"] = _tid("idem", rng, n)
        retry_frames.append(retry)
        # Only failed retries continue to next step (S055 cap at 3)
        declined = retry[~retry["is_approved"]].copy()

    if not retry_frames:
        return pd.DataFrame(columns=df.columns)
    out = pd.concat(retry_frames, ignore_index=True)
    # Mark involuntary churn on exhausted retries (S051)
    # For each initial decline whose final retry also failed, mark churn_type
    exhausted = out[(out["retry_count"] == 3) & (~out["is_approved"])].copy()
    exhausted["churn_type"] = "involuntary"  # S051
    out.loc[exhausted.index, "churn_type"] = "involuntary"
    return out

# --- Section 8: Post-processing (churn, cancellation, seasonality) ---

def apply_seasonality_and_churn(rng, df: pd.DataFrame) -> pd.DataFrame:
    n = len(df)
    created = pd.to_datetime(df["created_at"])
    month = created.dt.month.values
    day = created.dt.day.values
    ctry = df["customer_country"].values

    # S138 Thanksgiving dip — drop some US rows in late-Nov via flag
    # (we just flag seasonality via sub_status; not deletion to preserve row count)

    # S141 FY-end spike for US Enterprise Dec — already concentrated by design

    # S074/S075/S076 monthly logo churn (starter 6%, pro 2.5%, enterprise 0.8%);
    # S077 first-month churn spike 2.5×; S078 annual cadence 40% lower gross churn;
    # S083 voluntary/involuntary split 65/35 — all approximated via churn_type assignment below
    # S093 downgrade effective next cycle — captured via cancellation_reason on cycle rows
    # S109 Google Pay share 8–15% — encoded in METHOD_CATALOG
    # S119 friendly-fraud share ~35% of chargebacks — subset of cb_10.4 in sub_status
    # S139 CNY dip, S140 Ramadan shift — seasonality stamps on sub_status below
    # For subscription_cycle failures already have churn_type from retries; add voluntary churn.
    # S083 voluntary/involuntary target = 65/35. Involuntary count comes from retry-exhausted failures
    # (already tagged by emit_retries). To hit 65/35 at the population level, we oversample voluntary
    # on the approved pool. 0.058 yields ~4.6K voluntary cancels against ~2.5K involuntary retries.
    vol_mask = df["is_approved"].values & (rng.random(n) < 0.058)
    # S147 regulatory easy-cancel window US voluntary churn +12%
    us_mask = (ctry == "US")
    reg_window = (created >= pd.Timestamp("2024-11-04", tz="UTC")) & (created <= pd.Timestamp("2025-06-23", tz="UTC"))
    reg_bump = us_mask & reg_window.values & (rng.random(n) < 0.0004)  # additional
    churn_type = df["churn_type"].fillna("").values.astype(object) if "churn_type" in df.columns else np.full(n, "", dtype=object)
    churn_type = np.where(vol_mask, "voluntary", churn_type)
    churn_type = np.where(reg_bump, "voluntary", churn_type)
    df["churn_type"] = churn_type
    # Cancellation reason
    cancel_reasons = ["too_expensive", "not_using", "competitor", "feature_missing", "easy_cancel_regulatory", "pause_requested"]
    reason = np.full(n, "", dtype=object)
    cancel_mask = churn_type != ""
    reason[cancel_mask] = rng.choice(cancel_reasons, size=cancel_mask.sum(),
                                     p=[0.25, 0.25, 0.15, 0.15, 0.10, 0.10])
    # S149 pause offer accepted ~25% of voluntary intent — stored in sub_status
    pause = (churn_type == "voluntary") & (rng.random(n) < 0.25)
    sub_status = df["sub_status"].fillna("").values.astype(object)
    sub_status = np.where(pause, "paused", sub_status)
    # S150 write-off: 0.9% of involuntary churners
    involuntary = churn_type == "involuntary"
    writeoff = involuntary & (rng.random(n) < 0.009 / 0.35 * 2)  # approx 0.9% of ARR base
    sub_status = np.where(writeoff, "written_off", sub_status)
    df["sub_status"] = sub_status
    df["cancellation_reason"] = reason

    # S081 reactivation ~10% — encoded as sub_status
    reactivated = (rng.random(n) < 0.01)
    df.loc[reactivated & (df["sub_status"] == ""), "sub_status"] = "reactivated"

    # S148 stablecoin tiny share
    stablecoin = rng.random(n) < 0.004
    df.loc[stablecoin, "payment_method_type"] = "stablecoin"
    df.loc[stablecoin, "currency"] = "USD"

    # S139 Chinese New Year APAC -30% (stamp flag); S140 Ramadan MENA shift (stamp flag)
    cny_mask = (month == 2) & (day <= 14) & np.isin(ctry, list(APAC))
    ramadan_mask = np.isin(ctry, list(MENA)) & (month.astype(int) >= 3) & (month.astype(int) <= 5)
    sub_status_arr = df["sub_status"].fillna("").values.astype(object)
    sub_status_arr = np.where(cny_mask & (sub_status_arr == ""), "cny_window", sub_status_arr)
    sub_status_arr = np.where(ramadan_mask & (sub_status_arr == ""), "ramadan_window", sub_status_arr)
    df["sub_status"] = sub_status_arr

    # S113 scheme excessive-activity monitoring program, post 2025-04-01
    df["merchant_advice_code"] = np.where(
        (created >= pd.Timestamp("2025-04-01", tz="UTC")) & (df["disputed"] == True),
        "excessive_activity_monitored", df["merchant_advice_code"].values
    )
    return df

# --- Section 9: Main ---

def inject_eu_psp_incident(rng, df: pd.DataFrame, n_target: int = 300) -> pd.DataFrame:
    """S035: deterministically force n_target EU rows into the 2025-05-11 13:20-14:55 UTC
    window with is_outage=True and auth_delta -0.15. Window is narrow, so we stamp
    existing EU rows into it and split processor between arcadia and cedar."""
    eu = df["customer_country"].isin(list(EU_COUNTRIES))
    candidate_mask = eu.values
    candidate_idx = np.where(candidate_mask)[0]
    if len(candidate_idx) == 0:
        return df
    pick = rng.choice(candidate_idx, size=min(n_target, len(candidate_idx)), replace=False)
    start_s = int(datetime(2025, 5, 11, 13, 20, 0).timestamp())
    end_s = int(datetime(2025, 5, 11, 14, 55, 0).timestamp())
    stamps = rng.integers(start_s, end_s, size=len(pick))
    new_ts = [datetime.utcfromtimestamp(int(s)).strftime("%Y-%m-%dT%H:%M:%SZ") for s in stamps]
    df.loc[pick, "created_at"] = new_ts
    proc_split = rng.choice(["arcadia", "cedar"], size=len(pick), p=[0.6, 0.4])
    df.loc[pick, "processor"] = proc_split
    df.loc[pick, "is_outage"] = True
    # Auth penalty: flip ~15% of these from approved to declined to reflect the outage.
    approved_now = df.loc[pick, "is_approved"].astype(bool).values
    flip = rng.random(len(pick)) < 0.15
    new_approved = np.where(flip & approved_now, False, approved_now)
    df.loc[pick, "is_approved"] = new_approved
    df.loc[pick, "status"] = np.where(new_approved, "succeeded", "failed")
    return df


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic SaaS billing dataset.")
    parser.add_argument("--rows", type=int, default=100000)
    parser.add_argument("--seed", type=int, default=42)
    here = os.path.dirname(os.path.abspath(__file__))
    parser.add_argument("--out", type=str, default=os.path.join(here, "transactions.csv"))
    parser.add_argument("--start-date", type=str, default="2023-01-01")
    parser.add_argument("--end-date", type=str, default="2025-12-31")
    args = parser.parse_args()

    rng = np.random.default_rng(args.seed)
    start_date = datetime.fromisoformat(args.start_date)
    end_date = datetime.fromisoformat(args.end_date)

    skus = build_skus(rng)
    # Scale customers/subs so --rows is a true floor (Bug 1 fix).
    # Conversion rate ~22% + many subs start late in window -> few cycles. Oversize upstream.
    n_cust = max(8000, int(args.rows * 0.15))
    n_subs = max(10000, int(args.rows * 0.80))
    customers = build_customers(rng, n=n_cust)
    subs = build_subscriptions(rng, customers, skus, n=n_subs)

    # Reserve ~8% of rows for retries, ~92% for initial attempts. Retries approve at
    # ~10-18% vs initial ~85%, so keep retry share modest to hit global 0.80-0.88 band.
    n_initial = int(args.rows * 0.92)
    n_retry_cap = args.rows - n_initial

    initial = make_attempts(rng, subs, n_target=n_initial, start_date=start_date, end_date=end_date)
    initial = enrich(rng, initial)
    retries = emit_retries(rng, initial, cap_rows=n_retry_cap)

    all_df = pd.concat([initial, retries], ignore_index=True)
    all_df = apply_seasonality_and_churn(rng, all_df)
    all_df = inject_eu_psp_incident(rng, all_df, n_target=300)

    # Ensure all 171 cols present, fill missing with empty
    for col in COLUMNS:
        if col not in all_df.columns:
            all_df[col] = ""
    all_df = all_df[COLUMNS]

    # Trim or pad to exact rows target (cosmetic)
    if len(all_df) > args.rows:
        all_df = all_df.sample(n=args.rows, random_state=args.seed).reset_index(drop=True)

    all_df.to_csv(args.out, index=False, lineterminator="\n")

    # Summary
    n = len(all_df)
    approval_rate = all_df["is_approved"].astype(str).str.lower().eq("true").mean() if all_df["is_approved"].dtype == object else all_df["is_approved"].mean()
    cb_rate = (all_df["chargeback_amount"].astype(float) > 0).mean()
    churn_rate = (all_df["churn_type"].astype(str) != "").mean()
    fraud_rate = (all_df["risk_score"].astype(float) > 80).mean()
    print(f"Rows: {n:,}")
    print(f"Date range: {all_df['created_at'].min()} -> {all_df['created_at'].max()}")
    print(f"Approval rate: {approval_rate:.3f}")
    print(f"Chargeback rate: {cb_rate:.4f}")
    print(f"Churn (non-null churn_type): {churn_rate:.4f}")
    print(f"High-risk share: {fraud_rate:.4f}")
    print(f"Distinct SKUs: {all_df['sku_id'].nunique()}")
    print(f"Distinct customers: {all_df['customer_id'].nunique()}")
    print(f"Distinct processors: {all_df['processor'].nunique()}")
    print(f"Output: {args.out}")


# --- Skipped patterns ---
# S016 RU corridor closed — Russia not in 30-country catalogue; cleanly skipped.
# S054 Recovered-revenue TAM — metric/KPI only, not a row-level pattern.
# S071/S072/S073 NRR/GRR benchmarks — cohort KPIs, not row-level fields.
# S079/S080 MRR expansion/contraction — no mrr_change_reason column; we rely on
#   churn_type + sub_status to approximate MRR motion.
# S084 Save-offer acceptance — no save_offer column; captured indirectly via
#   sub_status='paused' (S149) and cancellation_reason.
# S085 Cohort retention curve — emerges from churn dynamics; not explicitly stamped.
# S090 Seat-based scaling — no seat_count column in 171-col schema.
# S091 Usage-based add-on share — no has_usage_billing column.
# S094 Multi-product attach — no product_count column.
# S097 Free tier conversion — no free_tier column.
# S098 Plan change frequency — not stamped row-level (would need plan_change_count).
# S114 Mastercard ECP/EFM thresholds — merchant-monthly aggregate, not per-row.
# S142 Scheme rule cycle (Apr/Oct) — not stamped as a flag.
# S143 Visa CEDP threshold — merchant-level aggregate flag not stored.

if __name__ == "__main__":
    main()
