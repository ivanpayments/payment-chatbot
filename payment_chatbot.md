# Payment Data Chatbot — Conversational Payment Analytics

## Product Summary

Payment Data Chatbot is the **core platform** of a unified AI chatbot for payments. It's a web-based conversational interface where users ask natural-language questions about payment transaction data and get instant analytics with visualizations. It also hosts tool functions provided by the other two portfolio products — the Routing Intelligence Engine (Product 2) and the Decline Recovery Predictor (Product 3) — so the chatbot answers not just "what's my approval rate?" but also "what should I route next?" and "which declines should I retry?". Deployed publicly at ivanantonov.com/chatbot — interviewers can try it live.

**Platform role**: This is the conversational layer every company thesis centers on (see `company_thesis_research.md`, master theme "AI chatbot for payments"). Products 2 and 3 plug in as additional tool functions; they also stand alone as REST APIs and PyPI packages.

**Ship date**: May 2 (Phase 1, weeks 1-4)
**Build effort**: 17 hours across 9 sessions (8 × 2h + 1h QA)
**Complexity**: SIMPLE (PM showcase)
**Primary role target**: Amazon PMT L6 / Product Manager (product thinking, usage analytics, data-driven decisions, cost control)
**Secondary role target**: Solutions Engineer (live merchant-facing analytics demo), AI Engineer (Claude tool use, streaming)

## The Problem

Every payments company has 3-5 people who answer the same questions every week:

- "What's our approval rate in Brazil?" — a PM asks before a board meeting
- "Why are declines up this month?" — a merchant success manager investigating a client complaint
- "How does Adyen compare to Stripe for recurring payments?" — a head of payments evaluating a provider switch

Today these questions go to the data team via Slack or Jira. The data analyst writes a SQL query, runs it, formats the results, and sends them back. Turnaround: hours to days. The person asking can't follow up ("now show me just Visa") without starting the cycle again.

**Who has this problem**: Payment operations teams, merchant success managers, payment analysts, product managers — anyone who needs payment data but doesn't write SQL.

**How often**: At a mid-size PSP, the data team fields 20-40 ad-hoc payment questions per week. In practice, payment teams ask the same 8 types of questions repeatedly.

**What it costs**: Data team spends ~10 hours/week on ad-hoc queries instead of building pipelines. PMs wait 1-2 days for answers that should take 3 seconds. Decisions get made on gut feel because getting data is too slow.

## What the User Sees

You open the chatbot, type "What's our approval rate by country?", and in 3 seconds you see a formatted table with 15 countries ranked by approval rate, each flagged if they're below the portfolio average, with a recommendation ("Brazil is 7pp below average — investigate decline code distribution"). You say "show me that as a chart" and get a color-coded bar chart inline. You follow up with "now just Visa cards" and the results update. No SQL, no waiting, no data team ticket.

Five pre-loaded sample conversations show what the tool can do even before you ask anything.

## Why Any Team Would Build This

- **Data team gets 40% fewer ad-hoc requests**: The 8 most common question types are handled by the chatbot. Data engineers stop being human SQL executors.
- **Non-technical people self-serve**: PMs, account managers, and merchant success reps get answers without learning SQL or navigating dashboards.
- **Time-to-insight drops from hours to seconds**: A question asked at 2pm gets answered at 2pm, not tomorrow morning.
- **Answers are consistent**: Same query logic every time. No more "the numbers don't match" because two analysts wrote slightly different SQL.
- **Follow-ups are free**: "Now filter by Visa" doesn't require a new Jira ticket. The conversation continues naturally.

Inspired by fintech-context AI tooling work. This version is a public-facing portfolio piece built entirely on synthetic data, open for anyone to interact with.

## Technical Solution

### What you're building

A production AI analytics chatbot at `ivanantonov.com/chatbot` with a vanilla HTML/JS frontend styled with Tailwind CSS. Users type payment questions in plain English. Claude Sonnet interprets the question, calls one of 8 SQL-based tool functions that query PostgreSQL, and streams a formatted response with optional charts via SSE (Server-Sent Events) — words appear one by one like ChatGPT. Redis caches frequent queries, manages conversation sessions, and enforces rate limits. Every query is logged for product analytics — what questions users ask, which tools get called, where users drop off. A dedicated product metrics dashboard at `/analytics` visualizes usage funnels, tool popularity, feedback scores, cost efficiency, and prompt version comparisons — the PM's decision-making tool. The full stack (FastAPI + PostgreSQL + Redis) runs in Docker with one command.

### Architecture

```
User types question in chat UI (vanilla HTML/JS + Tailwind)
  → SSE connection to FastAPI (/chat/stream)
    → FastAPI sends to Claude Sonnet API (system prompt + 8 tools + conversation history)
      → Claude calls tool (e.g. query_approval_rates)
        → SQLAlchemy executes SQL on PostgreSQL → result table
          → Result sent back to Claude as tool_result
            → Claude writes response + optionally calls generate_chart()
              → Response streams token-by-token via SSE
                → Browser renders message with markdown tables + inline chart

Redis: caches query results (TTL 5min), stores conversation history per session, enforces rate limits
Prometheus: /metrics endpoint — request_count, latency_histogram, tool_usage_by_type, cache_hit_rate
```

### Key files to create

| File | What it does |
|------|-------------|
| `static/index.html` | Chat UI — Tailwind CDN, message list, input box, auto-scroll, starter chips |
| `static/app.js` | SSE streaming, message rendering, chart display, follow-up chips |
| `app.py` | FastAPI — serves static files at `/`, SSE at `/chat/stream`, `/health`, `/metrics` |
| `db.py` | SQLAlchemy models (transactions, sessions, query_log, feedback), PostgreSQL connection |
| `tools.py` | 8 Python functions — structured SQL queries |
| `schemas.py` | Pydantic models: ChatMessage, ToolCall, QueryResult |
| `claude_client.py` | Anthropic client, system prompt with 8 tool schemas, tool_use loop, SSE streaming |
| `charts.py` | matplotlib chart generation → base64 PNG |
| `cache.py` | Redis caching layer — query result cache, session storage, rate limit counters |
| `analytics.py` | Analytics API: /api/analytics/* endpoints, aggregation queries, dashboard data |
| `static/analytics.html` | Product metrics dashboard — Chart.js charts, usage funnel, tool popularity |
| `static/analytics.js` | Dashboard logic: fetch analytics API, render charts, auto-refresh every 30s |
| `migrations/` | Alembic database migration scripts |
| `Dockerfile` | Python app with static files |
| `docker-compose.yml` | FastAPI + PostgreSQL + Redis |
| `tests/` | pytest unit tests for all tools, caching |

### Data layer

**Structured data (PostgreSQL):**
The CSV's 72 columns are loaded into a PostgreSQL `transactions` table at setup. All 8 query tools execute SQL via SQLAlchemy — GROUP BY, aggregations, window functions — instead of pandas in memory. This means the chatbot demonstrates real database skills: schema design, indexing (B-tree indexes on country, provider, transaction_status for fast grouping), and SQL query optimization.

Additional tables: `chat_sessions` (tracks each conversation, includes prompt version), `query_log` (what tool was called, with what params, how long it took, success/failure), `feedback` (thumbs up/down per response, stored with session and tool context).

**The key columns** tools query remain the same as before: transaction_status, transaction_amount, country, provider, card_brand, iso8583_response_code, three_ds_version, etc.

**No RAG/knowledge base**: The 8 data query tools cover 95% of user questions. For the remaining 5% — "what does response code 05 mean?", "explain 3D Secure frictionless flow" — key reference information is included directly in Claude's system prompt. Adding a vector database, embedding pipeline, and chunking strategy adds meaningful complexity for marginal coverage. Ship the MVP, measure what users actually ask, add knowledge base search later if the data shows demand. This is product thinking — scope to what matters, instrument to learn what's missing.

### Key decisions

- **Vanilla HTML/JS, not React**: The product value is in the AI analytics, not the frontend framework. A PM builds the simplest thing that works and iterates based on user feedback. No npm, no build step, no component lifecycle — a single HTML file and a JS file that handles SSE streaming and message rendering. Tailwind via CDN for styling.
- **PostgreSQL, not CSV in memory**: Real database skills — schema design, indexing, SQL queries, migrations with Alembic. But also: query logging. Every question users ask is stored with tool called, parameters, latency, and outcome. This data drives product decisions.
- **SSE (Server-Sent Events), not WebSocket for streaming**: The standard for AI response streaming — ChatGPT, Claude, and every major AI app uses SSE. Simpler than WebSocket for server-to-client streaming.
- **Redis for three concerns (cache + sessions + rate limiting)**: One service handles caching (query results, 5-min TTL), session management (conversation history per user), and rate limiting (sliding window, 10 req/min per IP). Simple infrastructure, maximum utility.
- **Usage analytics over A/B testing**: Track what questions users ask most, which tools get called, where users drop off, what gets thumbs down. This data is more valuable than A/B testing prompt variants. PM focuses on understanding users, not optimizing prompts. Prompt version is tracked per session so results can be compared manually when the prompt changes — no engineered framework needed.
- **$5/day API cap + 10-message limit**: Cost control is product management. Set constraints, provide fallback (sample conversations ensure the product always works, even when budget is exhausted).
- **matplotlib for chat charts, Chart.js for analytics dashboard**: Two different needs — Claude decides what to chart in conversation (server-side matplotlib → base64 PNG), while the product metrics dashboard uses Chart.js for interactive panels (hover, filter, auto-refresh). Right tool for each job.
- **Claude Sonnet, not Haiku**: Tool use requires reasoning about which function to call. Sonnet handles multi-step tool chains (query → chart → explain) reliably.
- **No JWT/authentication**: The chatbot is public — that's the point. Rate limiting by IP is sufficient protection for a portfolio project. No admin endpoints means no auth to maintain.
- **structlog + Prometheus, not OpenTelemetry**: Single service, not distributed. JSON-structured logs with request correlation and Prometheus metrics give full observability without the overhead of distributed tracing infrastructure.
- **pytest only, no Playwright**: Unit tests validate tool correctness and caching behavior. Browser E2E tests add maintenance burden disproportionate to value for a single-page vanilla JS app.
- **Docker for deployment**: One `docker-compose up` starts everything. No complex infrastructure.

## Tech Stack

- Python 3.12
- Vanilla HTML/JS + Tailwind CSS via CDN (no npm, no build step)
- Chart.js via CDN (interactive charts for product metrics dashboard)
- FastAPI (REST API + SSE streaming)
- PostgreSQL (transaction data, sessions, query logs, feedback)
- Redis (response cache, session management, rate limiting, API budget tracking)
- Claude Sonnet via Anthropic API (tool use for structured queries)
- SQLAlchemy + Alembic (ORM + database migrations)
- matplotlib (server-side chart generation → base64 PNG)
- Pydantic (request/response validation)
- SSE / Server-Sent Events (streaming Claude responses token-by-token)
- pytest (unit tests for tools, caching, analytics)
- Docker + docker-compose (PostgreSQL + Redis + FastAPI in one stack)
- Prometheus (metrics: request count, latency, tool usage, cache hits)
- Structured logging / structlog (JSON-format logs with request correlation IDs)
- Deployed on DigitalOcean at ivanantonov.com/chatbot via Caddy reverse proxy

## Core Capabilities

### Natural Language Queries
Users ask questions in plain English. Claude interprets the intent and calls Python tool functions to query the dataset:

- "What's the approval rate by country?" → grouped approval rate table + heatmap
- "Compare Stripe vs Adyen for US transactions" → head-to-head provider scorecard
- "Show me decline trends over the last 6 months" → time series chart with trend line
- "Which merchants have the highest chargeback rate?" → ranked table with risk flags
- "Break down 3DS challenge rates by card brand" → grouped bar chart

### Claude Tool Use Architecture
Claude receives a system prompt with dataset schema, key payment reference info, and available tool functions:

| Tool Function | What It Does |
|--------------|-------------|
| `query_approval_rates(group_by, filters)` | Approval rate analysis with flexible grouping |
| `query_decline_codes(top_n, filters)` | Top decline codes by volume/value |
| `query_provider_comparison(providers, metrics)` | Head-to-head provider scorecard |
| `query_geographic(metric, filters)` | Country-level performance matrix |
| `query_temporal(metric, granularity)` | Time-series analysis (hourly/daily/weekly) |
| `query_fraud_metrics(group_by, filters)` | Chargeback rates, fraud-to-sales ratio |
| `query_3ds_performance(group_by)` | Challenge rates, frictionless conversion, version distribution |
| `generate_chart(data, chart_type, title)` | Render visualization from query results |
| `query_routing_intelligence(country, card_brand, amount)` | Ships with Product 2 (May 30). Calls the Routing Intelligence Engine REST API → returns ranked provider recommendations with projected approval rate, latency, fee. |
| `predict_decline_recovery(transaction_context)` | Ships with Product 3 (Jun 27). Calls the Decline Recovery Predictor REST API → returns retry / cascade / abandon decision with SHAP explanation and expected recovery value. |

### Multi-Turn Conversation
- Context maintained across turns — "Now filter that by Visa only" works
- Follow-up questions refine previous queries
- Claude explains its reasoning and suggests follow-up questions

### Visualizations
- Charts rendered server-side (matplotlib → PNG)
- Embedded inline in chat responses
- Chart types: bar, line, heatmap, pie, scatter

### Usage Analytics & Instrumentation
Every interaction is instrumented for product learning:

- **Query logging**: question text, tool called, parameters, latency, success/failure — all stored in `query_log` table
- **Session tracking**: session start/end, message count, prompt version, last active timestamp
- **Feedback collection**: thumbs up/down button on each bot response, stored with session and tool context
- **Cost tracking**: Claude API token usage per request, daily spend vs $5 budget, cost per successful query

### Product Metrics Dashboard (`/analytics`)
A dedicated dashboard page at `ivanantonov.com/chatbot/analytics` built with Chart.js, showing real product health metrics. This is the PM showcase — not a technical observability tool, but a product decision-making tool.

**Dashboard panels:**

| Panel | Chart type | What it answers |
|-------|-----------|-----------------|
| Usage funnel | Horizontal funnel | Sessions → Questions asked → Follow-ups → Feedback given — where do users drop off? |
| Tool popularity | Horizontal bar | Which of the 8 analytics tools do users actually call? (approval_rates dominates at ~40%) |
| Session depth | Histogram | How many messages per session? Most stop at 2-3, engaged users reach 8-10 |
| Feedback by tool | Grouped bar | Which tools get thumbs up vs down? Charts get lower scores → improve chart formatting |
| Daily usage trend | Line + 7-day MA | Sessions per day, with rolling average — is the product growing or stagnating? |
| Cost efficiency | Dual-axis line | Daily API spend (left axis) vs successful queries (right axis) — cost per useful answer |
| Top 10 questions | Table | Most common query patterns — reveals what payment teams actually care about |
| Prompt version comparison | Side-by-side bar | Tool success rate + avg feedback score per prompt version — did the prompt change help? |
| Error analysis | Pie | Why queries fail: tool error, Claude misroute, timeout, rate limited — prioritize fixes |
| Peak hours | Heatmap | Day-of-week × hour-of-day usage — when are users most active? |

**API endpoints powering the dashboard:**
- `GET /api/analytics/overview` — summary cards: total sessions, total queries, avg session depth, overall feedback score, today's API cost
- `GET /api/analytics/funnel` — usage funnel data (sessions → queries → follow-ups → feedback)
- `GET /api/analytics/tools` — per-tool call count, success rate, avg latency, avg feedback score
- `GET /api/analytics/sessions` — session depth distribution, drop-off analysis by message number
- `GET /api/analytics/feedback` — feedback breakdown by tool type, by day, by prompt version
- `GET /api/analytics/cost` — daily API spend, cost per session, cost per successful query, budget utilization
- `GET /api/analytics/trends` — daily active sessions + queries with 7-day rolling average

**The dashboard tells a product story**: after 50 sessions, you can see that approval rate analysis is 40% of all queries, users who get charts ask more follow-ups, and the second prompt version improved tool success from 85% to 93%. These aren't vanity metrics — each one maps to a product decision.

### Rate Limiting & Cost Control
- Rate limiting: 10 requests/minute per IP via Redis sliding window
- API budget cap: $5/day Claude API spend, tracked in Redis counter
- 10-message session limit per conversation
- Friendly message when limits reached + show pre-computed sample conversations as fallback
- No authentication — the chatbot is public. IP-based rate limiting is sufficient protection.

### Observability
- Structured JSON logging via structlog — every request, tool call, and error includes request_id for correlation
- Prometheus `/metrics` endpoint: request_count, request_latency_histogram, tool_calls_by_type, cache_hit_rate, active_sessions

## Build Plan

### Session 1 (2h): Project scaffold + PostgreSQL + data loading
**Build**:
1. Create repo `ivanpayments/payment-chatbot`, init venv, `pyproject.toml` with all dependencies
2. PostgreSQL schema: `transactions` table (matching CSV's 72 columns), `chat_sessions` table (id, created_at, prompt_version, message_count), `query_log` table (session_id, tool_name, params_json, latency_ms, success, timestamp), `feedback` table (session_id, message_index, rating, created_at)
3. Alembic init + first migration
4. SQLAlchemy models for all tables
5. Bulk load `synthetic_transactions.csv` into PostgreSQL (10K rows)
6. FastAPI scaffold: `GET /` serves static files, `GET /health` returns `{"status": "ok", "transactions": 10000}`, SSE stub at `/chat/stream`
7. Create indexes on transactions: country, provider, transaction_status, card_brand (B-tree)

**Done when**: PostgreSQL has 10K rows. `/health` returns 200. `SELECT COUNT(*) FROM transactions` returns 10000. Alembic migration runs cleanly.

---

### Session 2 (2h): Core query tools — SQL-based
**Build**:
1. `query_approval_rates(group_by, filters)` — SQLAlchemy GROUP BY, calculates approval_count / total_count / approval_rate / total_amount / avg_amount, adds vs_portfolio_avg delta, flags groups >5pp below average, generates recommendation with dollar impact estimate
2. `query_decline_codes(top_n, filters)` — Filters to declined only, groups by response code, classifies soft vs hard decline, adds actionability column ("Retry in 30 min" / "Do not retry" / "Cascade to alternate provider")
3. `query_provider_comparison(providers, metrics, filters)` — Per-provider scorecard: approval rate, avg latency, decline rate, top decline code, weighted score (60% approval, 20% latency, 20% decline), routing recommendation
4. Unit tests for all 3 functions with pytest (test database with 100-row fixture)

**Done when**: Each function returns correct results from PostgreSQL. Tests pass. `query_approval_rates(group_by=["country"])` returns 15 countries.

---

### Session 3 (2h): Remaining tools + Claude integration
**Build**:
1. `query_geographic(metric, filters)` — Group by country, add region column, rank, flag low-confidence (<50 txns)
2. `query_temporal(metric, granularity, filters)` — Group by time bucket, rolling average, anomaly flagging
3. `query_fraud_metrics(group_by, filters)` — Chargeback rate, fraud-to-sales ratio, risk flags
4. `query_3ds_performance(group_by, filters)` — Challenge rate, frictionless rate, version breakdown
5. Claude client: system prompt (dataset schema + key payment reference info + 8 tool JSON schemas + formatting rules), `chat()` function with tool_use loop
6. Wire SSE endpoint: receive message → call Claude → execute tool → stream response
7. Response formatting: markdown tables, numbers with commas, percentages to 1 decimal

**Done when**: Send "What's the approval rate by country?" → get formatted markdown table with 15 countries from PostgreSQL via Claude tool use.

---

### Session 4 (2h): Charts + SSE streaming
**Build**:
1. `charts.py`: `generate_chart(data, chart_type, title, x_col, y_col)` returns base64 PNG
2. 5 chart types with matplotlib: horizontal bar (sorted, color-coded above/below average), line (time series + trend overlay), heatmap (country x provider matrix), pie (share breakdown), scatter (two metrics)
3. Consistent style: navy/blue palette, clean labels, 800x500px, "Data: 10,000 synthetic transactions" source note
4. Add `generate_chart` as tool in Claude's schema — Claude calls it after a query to visualize
5. SSE streaming implementation: FastAPI `StreamingResponse` with `text/event-stream`, yield tokens as `data:` events
6. Chart arrives as final SSE event with base64 image data

**Done when**: "Show approval rates by country as a bar chart" → streaming text response + inline chart image via SSE.

---

### Session 5 (2h): Frontend chat UI — vanilla HTML/JS + Tailwind
**Build**:
1. `static/index.html`: Tailwind CDN, chat container layout — dark navy header with "Payment Data Chatbot" title, white chat area, input area
2. `static/app.js`: SSE connection to `/chat/stream`, accumulate streaming tokens, detect chart events, handle errors
3. User/bot message bubbles (user right/blue, bot left/white), markdown rendering (tables, bold, lists), inline `<img>` for chart images
4. 3 starter question chips — "What's my approval rate by country?", "Compare providers for Brazil", "Show me top decline codes" — auto-send on click
5. 5 pre-computed sample conversations as expandable cards (always visible, proof the tool works even if API budget exhausted)
6. Follow-up suggestion chips parsed from Claude's response, rendered as clickable chips below each bot message
7. Mobile responsive (Tailwind breakpoints), auto-scroll to latest message, loading animation

**Done when**: Full chat works in browser. Type question → see streaming response with formatted tables and charts. Mobile layout works at 320px. Starter chips and sample conversations work.

---

### Session 6 (2h): Redis + rate limiting + usage analytics
**Build**:
1. Redis connection via `redis-py` (async)
2. Session management: store conversation history in Redis (key: `session:{id}`, value: JSON message list, TTL: 1 hour)
3. Response caching: cache tool results by query hash (key: `cache:{hash}`, TTL: 5 min). On cache hit, skip Claude API call.
4. Rate limiting: sliding window per IP address — max 10 requests per minute. Redis ZADD + ZRANGEBYSCORE.
5. API budget tracking: daily Claude API spend tracked in Redis counter (key: `budget:{date}`), cap at $5/day, return friendly "budget reached" message
6. 10-message session limit: counter per session in Redis, show samples when limit reached
7. `analytics.py`: log every query to `query_log` (tool_name, params, latency, success/failure), feedback endpoint for thumbs up/down
8. Prompt versioning: store system prompt version in `chat_sessions` table, compare tool success rate across versions

**Done when**: 11th request in 1 minute returns 429. Repeated identical query returns cached result (faster, no Claude call). Analytics data accumulates in `query_log`. Feedback button stores ratings.

---

### Session 7 (2h): Product metrics dashboard
**Build**:
1. `static/analytics.html`: dashboard layout with Chart.js CDN — 10 panels arranged in 2-column grid, responsive
2. `static/analytics.js`: fetch all `/api/analytics/*` endpoints, render Chart.js charts (bar, line, pie, heatmap), auto-refresh every 30 seconds
3. Analytics API endpoints in `analytics.py`:
   - `GET /api/analytics/overview` — aggregate from query_log + chat_sessions + feedback tables
   - `GET /api/analytics/funnel` — COUNT DISTINCT at each stage (sessions → queries → follow-ups → feedback)
   - `GET /api/analytics/tools` — GROUP BY tool_name: call_count, success_rate, avg_latency, avg_feedback
   - `GET /api/analytics/sessions` — session depth distribution (histogram buckets), drop-off by message number
   - `GET /api/analytics/feedback` — feedback scores sliced by tool, day, prompt version
   - `GET /api/analytics/cost` — sum token usage per day, compute cost per session and per successful query
   - `GET /api/analytics/trends` — daily session + query counts with 7-day rolling window
4. Usage funnel visualization: horizontal funnel chart showing conversion at each stage
5. Tool popularity chart: horizontal bar chart sorted by call count, colored by success rate
6. Prompt version comparison: side-by-side bars for success rate + feedback score across versions
7. Link from main chatbot UI: small "Product Metrics" link in header → opens `/analytics`

**Done when**: `/analytics` page loads with all 10 panels showing real data from query_log/sessions/feedback tables. Charts are interactive (hover shows values). Auto-refreshes.

---

### Session 8 (2h): Docker + observability + deploy
**Build**:
1. `Dockerfile`: Python 3.12-slim, copy static files + Python source, install deps, run uvicorn
2. `docker-compose.yml`: `web` (FastAPI, port 8083), `db` (PostgreSQL 16), `cache` (Redis 7). Volume for PostgreSQL data persistence.
3. Structured logging: `structlog` with JSON output. Every log entry includes `request_id`, `timestamp`, `level`, `event`. Request middleware adds correlation ID.
4. Prometheus `/metrics` endpoint via `prometheus-fastapi-instrumentator`: request_count, request_duration_seconds (histogram), custom counters for tool_calls_by_type, cache_hits_total, active_sessions_gauge
5. Deploy to DigitalOcean: `docker-compose up -d` on droplet, Caddy reverse proxy at `/chatbot/*` → `localhost:8083`
6. Push to GitHub `ivanpayments/payment-chatbot`
7. README: screenshot, architecture diagram, "Try it live" link, local dev setup instructions

**Done when**: `docker-compose up` starts full stack from scratch. Logs are JSON. `/metrics` returns Prometheus-format metrics. `ivanantonov.com/chatbot` loads chat UI and works end-to-end.

---

### Session 9 (1h): QA + polish
End-to-end testing: all 8 query tools, chart rendering for each type, SSE streaming, multi-turn context, rate limiting triggers, cached responses, mobile layout, starter chips, sample conversations, feedback buttons, analytics page. Fix bugs. Take 5 screenshots for portfolio. Update portfolio site card. Verify Docker stack restarts cleanly.

## Deliverables

- [ ] Live at ivanantonov.com/chatbot — anyone can try it
- [ ] GitHub repo (`ivanpayments/payment-chatbot`) with README + architecture diagram
- [ ] 8 SQL-based query tools + chart generation via Claude tool use
- [ ] SSE streaming responses
- [ ] PostgreSQL data layer with query logging
- [ ] Redis: response cache + session management + rate limiting
- [ ] Product metrics dashboard at /analytics with 10 Chart.js panels (usage funnel, tool popularity, feedback scores, cost tracking, session depth, prompt comparison)
- [ ] Analytics API: 7 endpoints powering the dashboard with real usage data
- [ ] Usage instrumentation: query logging, feedback collection, cost tracking, prompt versioning
- [ ] Docker-compose: full stack in one command (FastAPI + PostgreSQL + Redis)
- [ ] Prometheus metrics + structured JSON logging
- [ ] pytest test suite
- [ ] 5 pre-computed sample conversations as fallback
- [ ] 5 portfolio screenshots

## Interview Talking Points

**For Amazon PMT L6 / PM roles (primary)**:
- "I built a conversational analytics product that replaces ad-hoc SQL queries with natural language. The key product decision: focus on 8 structured data tools that cover 95% of payment team questions, not a generic chatbot."
- "I built a product metrics dashboard that shows a usage funnel — sessions to questions to follow-ups to feedback. After 50 sessions I could see that 60% of users never ask a follow-up, which told me the initial response needed to be more complete."
- "The dashboard shows tool popularity — approval rate analysis is 40% of all queries. That told me to optimize that tool first. Data-driven product prioritization, not guesswork."
- "I track prompt versions per session and compare success rate + feedback scores side by side. When I updated the system prompt, tool success went from 85% to 93%. The dashboard made that visible instantly."
- "Cost efficiency panel: I can see cost per successful query trending down from $0.08 to $0.05 as caching improves. The $5/day budget cap and 10-message limit are product constraints that force focus."
- "The feedback heatmap by tool type showed chart responses getting lower scores than table responses. That's a specific, actionable product insight — improve chart formatting, not the whole system."
- "Every metric on the dashboard maps to a product decision. Usage funnel → improve onboarding. Tool popularity → prioritize development. Cost per query → optimize caching. This is how I think about product management."

**For Solutions Engineer roles**:
- "Live demo at ivanantonov.com/chatbot — type any payment question and get a formatted answer with charts. Built with Claude tool use, SSE streaming, and PostgreSQL."
- "Redis handles three concerns with one service: caching, session management, and rate limiting. The standard answer to system design questions."

**For AI Engineer / TPM roles**:
- "Claude Sonnet with tool_use decides which of 8 SQL-based functions to call based on natural language input. SSE streams the response token by token."
- "Containerized with docker-compose. Structured JSON logging. Prometheus metrics for monitoring."

## Coverage Matrix

| Role | Relevance | Signal |
|------|-----------|--------|
| Amazon PMT L6 / PM | PRIMARY | Product thinking, usage analytics, data-driven decisions, cost control |
| Solutions Engineer | Strong | Live merchant demo, data storytelling, payment domain |
| AI Engineer | Moderate | Claude tool use, SSE streaming |

## Data Source

Powered by `synthetic_transactions.csv`:
- 10,000 transactions, 72 columns
- 12 fake merchants, 15 countries, 10 fake providers
- Safe for public repos (fully synthetic)
