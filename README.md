# Live Events Ticket Agent

An agentic AI assistant that helps you find live events, track ticket prices, and get alerted when prices change.

Try it: **https://wc-ticketing-agent.vercel.app/**

---

## What it does

- **Conversational search** — ask in plain English: "Show me concerts near Raleigh in June"
- **Price alerts** — subscribe to events and get emailed when ticket prices change
- **Background monitoring** — a worker polls Ticketmaster every 10 minutes and fires Resend email alerts automatically
- **MCP server** — exposes tools over Streamable HTTP, compatible with Claude Desktop

---

## Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI, Python 3.13 |
| LLM | Groq (Llama 4 Scout) with agentic tool-calling loop |
| Tickets | Ticketmaster Discovery API |
| Email alerts | Resend |
| Database | PostgreSQL (psycopg2) |
| Frontend | React 18 + Vite |
| MCP | FastMCP, Streamable HTTP transport |
| Deployment | Render (API + MCP + monitor), Vercel (frontend) |

---

## Project structure

```
wc-ticketing-agent/
├── api.py                  # FastAPI app — chat endpoint, auth, agentic loop
├── auth.py                 # JWT + bcrypt
├── mcp_server/
│   ├── server.py           # FastMCP server (stdio + HTTP)
│   ├── db.py               # PostgreSQL helpers
│   ├── ticketmaster.py     # Ticketmaster API client
│   ├── geo.py              # Haversine distance + geocoding
│   └── constants.py        # Shared constants
├── monitor/
│   └── monitor_prices.py   # Background price monitor + email alerts
├── frontend/               # React + Vite frontend
├── render.yaml             # Render Blueprint (4 services)
└── requirements.txt
```

---

## Local setup

### 1. Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Set up environment

```bash
cp .env.example .env
```

Required env vars:

| Variable | Description |
|---|---|
| `GROQ_API_KEY` | Groq API key |
| `JWT_SECRET` | Strong random secret for JWT signing |
| `TICKETMASTER_API_KEY` | Ticketmaster Discovery API key |
| `RESEND_API_KEY` | Resend API key for email alerts |
| `DATABASE_URL` | PostgreSQL connection string |
| `CORS_ORIGINS` | Frontend URL (e.g. http://localhost:5173) |
| `MCP_API_KEY` | Bearer token for remote MCP auth |

### 3. Run the API

```bash
uvicorn api:app --reload
```

### 4. Run the frontend

```bash
cd frontend
npm install
npm run dev
```

---

## Price monitor

```bash
# Single check
python monitor/monitor_prices.py

# Continuous loop (every 10 minutes)
python monitor/monitor_prices.py --loop --interval 600
```

---

## MCP tools

| Tool | Description |
|---|---|
| `search_events` | Find events by location + date range, sorted by distance then price |
| `subscribe_to_events` | Subscribe to price alerts for one or more events |
| `list_subscriptions` | List all active subscriptions for a user |
| `unsubscribe` | Cancel subscriptions for given event IDs |

### Claude Desktop config (remote MCP)

```json
{
  "mcpServers": {
    "live-events-agent": {
      "type": "http",
      "url": "https://wc-ticketing-agent-mcp.onrender.com/mcp",
      "headers": { "Authorization": "Bearer YOUR_MCP_API_KEY" }
    }
  }
}
```

---

## Deployment

The project deploys via a Render Blueprint (`render.yaml`) which provisions 4 services automatically:

- PostgreSQL database
- Web API (FastAPI)
- MCP HTTP server
- Background monitor worker

The React frontend deploys to Vercel with `VITE_API_URL` pointing to the Render web service.
