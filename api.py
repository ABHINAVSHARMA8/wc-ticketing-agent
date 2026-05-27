"""
Live Events Ticket Agent — FastAPI backend
Uses Groq (free tier) with Llama 4 Scout and a manual agentic tool-calling loop.
Auth: JWT Bearer tokens via register/login.
"""

import asyncio
import json
import logging
import os
import sys
from contextlib import asynccontextmanager
from typing import Optional

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from groq import AsyncGroq
from pydantic import BaseModel, EmailStr, field_validator

load_dotenv()

sys.path.insert(0, os.path.dirname(__file__))

from auth import create_token, get_current_user, hash_password, verify_password
from mcp_server.db import (
    create_user,
    delete_subscription,
    get_subscriptions_for_user,
    get_user_by_email,
    init_db,
    upsert_subscription,
)
from mcp_server.constants import (
    GROQ_MODEL,
    MAX_AGENTIC_STEPS,
    MAX_HISTORY_MESSAGES,
    MIN_PASSWORD_LENGTH,
)
from mcp_server.geo import haversine, resolve_location
from mcp_server.ticketmaster import (
    TicketmasterError,
    fetch_event_details,
    search_events as tm_search,
)

log = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)

MODEL = GROQ_MODEL

_conversations: dict[str, list[dict]] = {}
_groq_client: AsyncGroq | None = None


# ── Startup / shutdown ────────────────────────────────────────────────────────

def _get_groq_client() -> AsyncGroq:
    global _groq_client
    if _groq_client is None:
        _groq_client = AsyncGroq(api_key=os.environ["GROQ_API_KEY"])
    return _groq_client


@asynccontextmanager
async def lifespan(_: "FastAPI"):
    # Validate required env vars before accepting traffic
    required = {"GROQ_API_KEY", "JWT_SECRET"}
    missing = required - set(os.environ)
    if missing:
        raise RuntimeError(
            f"Missing required environment variables: {', '.join(sorted(missing))}"
        )
    if os.environ.get("JWT_SECRET") == "change-this-in-production":
        log.critical(
            "JWT_SECRET is set to the insecure default. "
            "Set a strong random secret before deploying."
        )

    init_db()
    _get_groq_client()   # fail fast if GROQ_API_KEY is malformed
    log.info("Startup complete. Model: %s", MODEL)
    yield
    log.info("Shutdown.")


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(title="Live Events Ticket Agent API", lifespan=lifespan)

_cors_origins = [
    o.strip()
    for o in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
    if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def _build_system_prompt() -> str:
    from datetime import date
    today = date.today().isoformat()
    return f"""Today's date is {today}. You are a sharp, friendly live events assistant with genuine enthusiasm for music, sports, and shows.

Your job:
1. Help users find concerts, sports games, and shows near a location within a date range
2. Set up price-change alerts for events they care about
3. View and manage their subscriptions

Personality:
- Talk like a knowledgeable friend who loves live events, not a customer service bot.
- Be warm, casual, and occasionally witty — but stay concise and never ramble.
- Show genuine interest: if someone's looking for a concert, you can briefly react to the artist or event.
- When there are no results, be empathetic and suggest broadening the search.
- IMPORTANT: Never use any markdown formatting. No asterisks, no bold, no italics, no bullet points with *, no headers, no backticks, no quotation marks around event names. Use plain text and dashes (-) for lists only.

Guidelines:
- When a user says "near me" or doesn't specify a location, ask for their city in a natural way.
- When a user gives a relative date like "in June" or "next month", convert it to
  an ISO date range. For example: June 2026 = 2026-06-01 to 2026-06-30.
- After a search, if the user wants to subscribe, use the event IDs from the
  search results — don't ask the user for IDs.
- Confirm subscriptions clearly but conversationally: mention each event and the alert settings.
- When listing subscriptions, always display every single event by name — never summarize with a count. Show the full list every time.
- Events span music concerts, sports games, theater, and other live entertainment.
- If a user asks you to do something outside your scope (e.g. book flights, make payments, answer general knowledge questions), politely let them know that your focus is live event ticket management and you can't help with that. Then suggest what you can do: find events near a location, set up price alerts, or manage their subscriptions.
"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_events",
            "description": (
                "Search for live events (concerts, sports, theater) near a given "
                "location within a date range. Results sorted by distance then price."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "location":  {"type": "string", "description": "City name or place, e.g. 'Raleigh, NC'"},
                    "date_from": {"type": "string", "description": "Start of date range YYYY-MM-DD"},
                    "date_to":   {"type": "string", "description": "End of date range YYYY-MM-DD"},
                },
                "required": ["location", "date_from", "date_to"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "subscribe_to_events",
            "description": "Subscribe a user to price-change alerts for one or more events.",
            "parameters": {
                "type": "object",
                "properties": {
                    "event_ids":       {"type": "array", "items": {"type": "string"}, "description": "List of event IDs from search results"},
                    "user_email":      {"type": "string", "description": "Email address to send alerts to"},
                    "price_threshold": {"type": ["number", "null"], "description": "Alert only when price drops below this value. Omit or pass null if no threshold."},
                    "notify_on":       {"type": "string", "enum": ["any", "drop", "rise"], "description": "Defaults to 'any'"},
                },
                "required": ["event_ids", "user_email"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_subscriptions",
            "description": "List all active price-alert subscriptions for a user.",
            "parameters": {
                "type": "object",
                "properties": {"user_email": {"type": "string"}},
                "required": ["user_email"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "unsubscribe",
            "description": "Cancel price-alert subscriptions for one or more events.",
            "parameters": {
                "type": "object",
                "properties": {
                    "event_ids":  {"type": "array", "items": {"type": "string"}},
                    "user_email": {"type": "string"},
                },
                "required": ["event_ids", "user_email"],
            },
        },
    },
]


# ── Tool execution (sync — called via asyncio.to_thread) ──────────────────────

def _execute_tool(name: str, args: dict) -> str:
    if name == "search_events":
        coords = resolve_location(args["location"])
        if not coords:
            return f"Could not geocode location: '{args['location']}'"
        lat, lng = coords
        try:
            results = tm_search(lat, lng, args["date_from"], args["date_to"])
        except TicketmasterError as e:
            log.error("search_events tool error: %s", e)
            return f"Failed to search events: {e}"
        for r in results:
            r["distance_miles"] = round(haversine(lat, lng, r["lat"], r["lng"]))
        results.sort(key=lambda x: (x["distance_miles"], x.get("price_usd") or 9999))
        if not results:
            return (
                f"No events found near '{args['location']}' between "
                f"{args['date_from']} and {args['date_to']}."
            )
        return json.dumps(results, indent=2)

    if name == "subscribe_to_events":
        subscribed, not_found = [], []
        for eid in args["event_ids"]:
            try:
                event = fetch_event_details(eid)
            except TicketmasterError as e:
                log.error("subscribe fetch error for %s: %s", eid, e)
                not_found.append(eid)
                continue
            if not event:
                not_found.append(eid)
                continue
            upsert_subscription(
                match_id=eid,
                user_email=args["user_email"],
                last_price=event.get("price_usd") or 0,
                price_threshold=args.get("price_threshold"),
                notify_on=args.get("notify_on", "any"),
                event_title=event.get("title", ""),
                event_venue=event.get("venue", ""),
                event_city=event.get("city", ""),
                event_date=event.get("date", ""),
            )
            subscribed.append(f"{event['title']} ({event['city']}) on {event['date']}")
        lines = []
        if subscribed:
            lines.append(
                f"Subscribed ({args.get('notify_on', 'any')} price changes): "
                f"{', '.join(subscribed)}"
            )
        if not_found:
            lines.append(f"Event IDs not found: {', '.join(not_found)}")
        return "\n".join(lines)

    if name == "list_subscriptions":
        subs = get_subscriptions_for_user(args["user_email"])
        if not subs:
            return f"No active subscriptions for {args['user_email']}."
        lines = [f"Active subscriptions for {args['user_email']}:"]
        for s in subs:
            threshold = f"below ${s['price_threshold']}" if s["price_threshold"] else "any change"
            title = s.get("event_title") or s["match_id"]
            date  = s.get("event_date") or ""
            lines.append(
                f"  • {title} ({date}) — "
                f"notify on: {s['notify_on']}, threshold: {threshold}, "
                f"last price: ${s['last_price']}"
            )
        return "\n".join(lines)

    if name == "unsubscribe":
        subs = {s["match_id"]: s for s in get_subscriptions_for_user(args["user_email"])}
        removed, not_found = [], []
        for eid in args["event_ids"]:
            if delete_subscription(eid, args["user_email"]):
                removed.append(subs.get(eid, {}).get("event_title") or eid)
            else:
                not_found.append(eid)
        lines = []
        if removed:
            lines.append(f"Unsubscribed from: {', '.join(removed)}")
        if not_found:
            lines.append(f"No subscription found for: {', '.join(not_found)}")
        return "\n".join(lines)

    return f"Unknown tool: {name}"


def _trim_history(history: list) -> list:
    """Keep the system message and the most recent MAX_HISTORY_MESSAGES messages."""
    system = history[:1]
    tail = history[1:]
    if len(tail) > MAX_HISTORY_MESSAGES:
        tail = tail[-MAX_HISTORY_MESSAGES:]
    return system + tail


# ── Pydantic models ───────────────────────────────────────────────────────────

class AuthRequest(BaseModel):
    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def password_length(cls, v: str) -> str:
        if len(v) < MIN_PASSWORD_LENGTH:
            raise ValueError("Password must be at least 8 characters")
        return v


class ChatMessage(BaseModel):
    message: str

    @field_validator("message")
    @classmethod
    def message_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Message cannot be empty")
        return v.strip()


class SubscribeRequest(BaseModel):
    match_ids: list[str]
    price_threshold: Optional[float] = None
    notify_on: str = "any"

    @field_validator("notify_on")
    @classmethod
    def valid_notify_on(cls, v: str) -> str:
        if v not in ("any", "drop", "rise"):
            raise ValueError("notify_on must be 'any', 'drop', or 'rise'")
        return v


class UnsubscribeRequest(BaseModel):
    match_ids: list[str]


class TokenResponse(BaseModel):
    token: str
    email: str


class HealthResponse(BaseModel):
    status: str
    model: str


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse)
async def health():
    return {"status": "ok", "model": MODEL}


# ── Auth endpoints ────────────────────────────────────────────────────────────

@app.post("/api/auth/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(body: AuthRequest):
    ok = await asyncio.to_thread(
        create_user, body.email, hash_password(body.password)
    )
    if not ok:
        raise HTTPException(status_code=409, detail="Email already registered")
    return {"token": create_token(body.email), "email": body.email}


@app.post("/api/auth/login", response_model=TokenResponse)
async def login(body: AuthRequest):
    user = await asyncio.to_thread(get_user_by_email, body.email)
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return {"token": create_token(body.email), "email": body.email}


# ── Chat endpoint ─────────────────────────────────────────────────────────────

@app.post("/api/chat")
async def chat(body: ChatMessage, user_email: str = Depends(get_current_user)):
    client = _get_groq_client()
    history = _conversations.setdefault(user_email, [
        {"role": "system", "content": _build_system_prompt() + f"\nThe user's email is: {user_email}"}
    ])
    history.append({"role": "user", "content": body.message})

    msg = None
    for _ in range(MAX_AGENTIC_STEPS):
        try:
            response = await client.chat.completions.create(
                model=MODEL,
                messages=history,
                tools=TOOLS,
                tool_choice="auto",
            )
        except Exception as e:
            log.error("Groq API error for %s: %s", user_email, e)
            return {"reply": "I had trouble reaching the AI service. Please try again."}

        msg = response.choices[0].message
        history.append(msg)

        if not msg.tool_calls:
            break

        for tc in msg.tool_calls:
            try:
                args = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                log.warning("Malformed tool arguments from model: %s", tc.function.arguments)
                return {"reply": "I had trouble understanding the search parameters. Could you rephrase?"}
            result = await asyncio.to_thread(_execute_tool, tc.function.name, args)
            history.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result,
            })

    # Trim history after each turn
    _conversations[user_email] = _trim_history(history)
    return {"reply": (msg.content or "") if msg else ""}


@app.delete("/api/chat")
async def clear_chat(user_email: str = Depends(get_current_user)):
    _conversations.pop(user_email, None)
    return {"status": "cleared"}


# ── Event search ──────────────────────────────────────────────────────────────

@app.get("/api/matches")
async def search_matches(
    location: str,
    date_from: str,
    date_to: str,
    radius_miles: float = 100,
    max_price: Optional[float] = None,
):
    coords = resolve_location(location)
    if not coords:
        raise HTTPException(
            status_code=400, detail=f"Could not geocode location: '{location}'"
        )
    lat, lng = coords
    try:
        results = await asyncio.to_thread(
            tm_search, lat, lng, date_from, date_to, int(radius_miles)
        )
    except TicketmasterError as e:
        log.error("/api/matches error: %s", e)
        raise HTTPException(status_code=503, detail="Event search unavailable. Try again later.")
    for r in results:
        r["distance_miles"] = round(haversine(lat, lng, r["lat"], r["lng"]))
    if max_price is not None:
        results = [r for r in results if not r.get("price_usd") or r["price_usd"] <= max_price]
    results.sort(key=lambda x: (x["distance_miles"], x.get("price_usd") or 9999))
    return results


# ── Subscriptions ─────────────────────────────────────────────────────────────

@app.get("/api/subscriptions")
async def list_subscriptions(user_email: str = Depends(get_current_user)):
    subs = await asyncio.to_thread(get_subscriptions_for_user, user_email)
    return [
        {**s,
         "teams": s.get("event_title") or s["match_id"],
         "date":  s.get("event_date")  or "",
         "venue": s.get("event_venue") or "",
         "city":  s.get("event_city")  or ""}
        for s in subs
    ]


@app.post("/api/subscriptions")
async def subscribe(body: SubscribeRequest, user_email: str = Depends(get_current_user)):
    subscribed, not_found = [], []
    for eid in body.match_ids:
        try:
            event = await asyncio.to_thread(fetch_event_details, eid)
        except TicketmasterError as e:
            log.error("subscribe fetch error %s: %s", eid, e)
            not_found.append(eid)
            continue
        if not event:
            not_found.append(eid)
            continue
        await asyncio.to_thread(
            upsert_subscription,
            eid, user_email,
            event.get("price_usd") or 0,
            body.price_threshold, body.notify_on,
            event.get("title", ""), event.get("venue", ""),
            event.get("city", ""),  event.get("date", ""),
        )
        subscribed.append(eid)
    return {"subscribed": subscribed, "not_found": not_found}


@app.delete("/api/subscriptions")
async def unsubscribe(body: UnsubscribeRequest, user_email: str = Depends(get_current_user)):
    removed, not_found = [], []
    for mid in body.match_ids:
        ok = await asyncio.to_thread(delete_subscription, mid, user_email)
        (removed if ok else not_found).append(mid)
    return {"removed": removed, "not_found": not_found}
