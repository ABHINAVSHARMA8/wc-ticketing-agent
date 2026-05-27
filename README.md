# FIFA World Cup 2026 Ticket Agent

An AI-powered ticket monitoring agent built with Claude + MCP (Model Context Protocol).

## What it does

- **Conversational search** — ask in plain English: _"Show me matches near Charlotte in June under $200"_
- **Price subscriptions** — subscribe to one or more matches and get emailed when prices change
- **Background monitoring** — a cron-friendly script polls prices and fires alerts automatically

---

## Project structure

```
fifa-ticket-agent/
├── mcp_server/
│   ├── server.py     # MCP tool definitions (search, subscribe, list, unsubscribe)
│   ├── db.py         # SQLite helpers
│   └── geo.py        # Haversine distance + geocoding
├── agent/
│   └── chat.py       # Conversational chat loop (connects Claude to MCP server)
├── monitor/
│   └── price_monitor.py  # Background price checker + email alerter
├── data/
│   └── matches.json  # Mock FIFA 2026 match data
├── .env.example      # Environment variable template
└── requirements.txt
```

---

## Quick start

### 1. Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Set up environment

```bash
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY
```

### 3. Run the agent

```bash
python -m agent.chat
```

### 4. Try these prompts

```
Show me matches near Raleigh in June
Show me games within 300 miles of Charlotte between June 1 and July 10
Any matches near me under $200?
Subscribe me to the first two results
Subscribe me to all of them, alert only if price drops below $150
List my subscriptions
Unsubscribe me from the Charlotte game
```

---

## Running the price monitor

### Single check (good for cron)

```bash
python -m monitor.price_monitor
```

### Continuous loop (every 10 minutes)

```bash
python -m monitor.price_monitor --loop --interval 600
```

### As a cron job

```cron
*/10 * * * * cd /path/to/fifa-ticket-agent && .venv/bin/python -m monitor.price_monitor
```

---

## Email alerts setup

Without SMTP credentials the monitor still works — alerts are logged to the console instead of emailed.

**Recommended: Resend** (simpler than Gmail)
1. Sign up at [resend.com](https://resend.com) — free tier is generous
2. Create an API key
3. Add to `.env`:
```
SMTP_HOST=smtp.resend.com
SMTP_PORT=587
SMTP_USER=resend
SMTP_PASS=your_resend_api_key
FROM_EMAIL=alerts@yourdomain.com
```

**Gmail**
1. Enable 2FA on your Google account
2. Create an App Password at myaccount.google.com/apppasswords
3. Add to `.env`:
```
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=you@gmail.com
SMTP_PASS=your_16_char_app_password
FROM_EMAIL=you@gmail.com
```

---

## MCP Tools

| Tool | Description |
|------|-------------|
| `search_matches` | Find matches by location + date range. Returns sorted by distance then price. |
| `subscribe_to_matches` | Subscribe to price alerts for one or more match IDs. Supports `notify_on: any/drop/rise` and an optional `price_threshold`. |
| `list_subscriptions` | List all subscriptions for a user email. |
| `unsubscribe` | Cancel subscriptions for given match IDs. |

---

## Replacing mock data with real prices

The `fetch_current_price()` function in `monitor/price_monitor.py` currently simulates price fluctuations. To connect to real data:

1. **StubHub API** — register at developer.stubhub.com
2. **Viagogo API** — register at developer.viagogo.net
3. **Web scraping** — use `playwright` or `httpx` to scrape the FIFA official ticket portal

Replace the body of `fetch_current_price()` with your real data source.

---

## Next steps

- [ ] Add a web UI (FastAPI + React) instead of the CLI chat loop
- [ ] Deploy MCP server to Railway with HTTP/SSE transport
- [ ] Add SMS alerts via Twilio
- [ ] Persist conversation history to DB for multi-session memory
- [ ] Add a `get_price_history` tool so users can ask "has the price been dropping?"