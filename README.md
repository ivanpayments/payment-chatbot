# Payment Data Chatbot

Agentic payment-analytics chatbot for the **Head of Payments / RevOps at a global SaaS**. The book is one SaaS parent: ~100 plan SKUs, 14 PSPs, 30 countries, **~$2B ARR** (Notion/Intercom-scale, not Stripe-scale). The CSV is ~100K billing attempts — outcomes, dunning retries, SCA exemptions, card-updater recoveries — not gross payments. Ask any natural-language question; Claude Opus 4.6 writes pandas in a sandboxed code-execution environment and streams the answer back.

**Live:** https://ivanantonov.com/chatbot

## Stack

- Claude Opus 4.6 with adaptive thinking + `code_execution_20250825`
- Dataset pre-uploaded via Files API (`files-api-2025-04-14`), referenced by `file_id`
- FastAPI + SSE streaming
- Deployed on a DigitalOcean droplet behind Caddy

## Local dev

```
cp .env.example .env   # fill in ANTHROPIC_API_KEY + CHATBOT_CSV_PATH
pip install -r requirements.txt
python app.py
```

Open http://localhost:8083.

## Data & PCI scope

The dataset is **100% synthetic** — generated billing attempts that represent a fictional SaaS book. It contains **no real cardholder data**: no full PAN, no CVV/CVC, no track data, no cardholder names. Card fields are limited to BIN (first 6 digits), last4, expiry month/year, brand, and funding type — the combination PCI DSS explicitly exempts from scope.

Operational controls:

- **System prompt** enforces a PCI boundary: the model refuses requests for full PANs, CVVs, or cardholder names and returns aggregate analytics only.
- **Inbound PAN redaction**: web `/chat` and Twilio webhook inputs are scanned for Luhn-valid 13–19 digit sequences; any hit is replaced with `[REDACTED_PAN]` before persisting to chat history, writing logs, or forwarding to the Anthropic API. This protects against a real user accidentally pasting a card number into the demo.
- **Third-party flow**: the CSV upload to Anthropic's Files API and Twilio's message delivery are safe channels only because the data is synthetic — real cardholder data would extend PCI scope to those providers.

## Status

Milestone 1 (minimal web chat) — shipping. Charts, starter chips, rate limits, WhatsApp, and SMS land in later milestones.
