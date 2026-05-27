"""
Live Events Ticket Agent — CLI Chat Interface
Uses Groq (free tier) with Llama 4 Scout and manual tool-calling loop.
"""

import json
import os
import sys

from groq import Groq
from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp_server.db import delete_subscription, get_subscriptions_for_user, upsert_subscription
from mcp_server.geo import haversine, resolve_location
from mcp_server.ticketmaster import fetch_event_details, search_events as tm_search

load_dotenv()

DEFAULT_USER_EMAIL = os.getenv("USER_EMAIL", "user@example.com")
MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"

SYSTEM_PROMPT = f"""You are a helpful live events ticket assistant.
Help users find concerts, sports games, and shows near them, subscribe to price alerts, and manage subscriptions.
The user's email is: {DEFAULT_USER_EMAIL}
Convert relative dates to ISO date ranges (e.g. "in June" → 2026-06-01 to 2026-06-30).
Keep responses concise and friendly.
"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_events",
            "description": "Search for live events (concerts, sports, theater) near a location within a date range.",
            "parameters": {
                "type": "object",
                "properties": {
                    "location":  {"type": "string"},
                    "date_from": {"type": "string"},
                    "date_to":   {"type": "string"},
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
                    "event_ids":       {"type": "array", "items": {"type": "string"}},
                    "user_email":      {"type": "string"},
                    "price_threshold": {"type": "number"},
                    "notify_on":       {"type": "string", "enum": ["any", "drop", "rise"]},
                },
                "required": ["event_ids", "user_email"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_subscriptions",
            "description": "List active price-alert subscriptions for a user.",
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


def execute_tool(name: str, args: dict) -> str:
    if name == "search_events":
        coords = resolve_location(args["location"])
        if not coords:
            return f"Could not geocode: '{args['location']}'"
        lat, lng = coords
        try:
            results = tm_search(lat, lng, args["date_from"], args["date_to"])
        except RuntimeError as e:
            return str(e)
        for r in results:
            r["distance_miles"] = round(haversine(lat, lng, r["lat"], r["lng"]))
        results.sort(key=lambda x: (x["distance_miles"], x.get("price_usd") or 9999))
        return json.dumps(results, indent=2) if results else "No events found."

    if name == "subscribe_to_events":
        subscribed, not_found = [], []
        for eid in args["event_ids"]:
            event = fetch_event_details(eid)
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
            subscribed.append(f"{event['title']} ({event['city']})")
        lines = []
        if subscribed:
            lines.append(f"Subscribed: {', '.join(subscribed)}")
        if not_found:
            lines.append(f"Not found: {', '.join(not_found)}")
        return "\n".join(lines)

    if name == "list_subscriptions":
        subs = get_subscriptions_for_user(args["user_email"])
        if not subs:
            return f"No subscriptions for {args['user_email']}."
        lines = ["Your subscriptions:"]
        for s in subs:
            threshold = f"below ${s['price_threshold']}" if s["price_threshold"] else "any change"
            title = s.get("event_title") or s["match_id"]
            lines.append(f"  • {title} ({s.get('event_date','')}) — {s['notify_on']}, {threshold}")
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
            lines.append(f"Unsubscribed: {', '.join(removed)}")
        if not_found:
            lines.append(f"No subscription for: {', '.join(not_found)}")
        return "\n".join(lines)

    return f"Unknown tool: {name}"


def run():
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        print("Error: GROQ_API_KEY not set in .env")
        sys.exit(1)

    client = Groq(api_key=api_key)
    history = [{"role": "system", "content": SYSTEM_PROMPT}]

    print("=" * 55)
    print("  Live Events Ticket Agent (Groq/Llama)")
    print("=" * 55)
    print("  Try: 'Show me concerts near Charlotte in June'")
    print("  Try: 'Any sports events in Miami this summer?'")
    print("  Type 'quit' to exit.")
    print("=" * 55)

    while True:
        try:
            user_input = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not user_input:
            continue
        if user_input.lower() in {"quit", "exit", "bye"}:
            print("Agent: Goodbye!")
            break

        history.append({"role": "user", "content": user_input})

        try:
            for _ in range(10):
                response = client.chat.completions.create(
                    model=MODEL, messages=history, tools=TOOLS, tool_choice="auto",
                )
                msg = response.choices[0].message
                history.append(msg)
                if not msg.tool_calls:
                    break
                for tc in msg.tool_calls:
                    result = execute_tool(tc.function.name, json.loads(tc.function.arguments))
                    history.append({"role": "tool", "tool_call_id": tc.id, "content": result})
            print(f"\nAgent: {msg.content}")
        except Exception as e:
            print(f"\n[Error]: {e}")


if __name__ == "__main__":
    run()
