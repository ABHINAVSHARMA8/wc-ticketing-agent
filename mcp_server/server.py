"""
Live Events Ticket Agent — MCP Server
Exposes four tools:
  - search_events        : find live events near a location within a date range
  - subscribe_to_events  : subscribe to price alerts for one or more events
  - list_subscriptions   : list a user's active subscriptions
  - unsubscribe          : cancel one or more subscriptions
"""

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

from mcp_server.db import (
    delete_subscription,
    get_subscriptions_for_user,
    upsert_subscription,
)
from mcp_server.geo import haversine, resolve_location
from mcp_server.ticketmaster import fetch_event_details, search_events as tm_search

server = Server("live-events-agent")


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="search_events",
            description=(
                "Search for live events (concerts, sports, theater) near a given location "
                "within a date range. Results are sorted by distance then price."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "location":     {"type": "string", "description": "City name or place (e.g. 'Raleigh, NC')"},
                    "date_from":    {"type": "string", "description": "Start of date range YYYY-MM-DD"},
                    "date_to":      {"type": "string", "description": "End of date range YYYY-MM-DD"},
                    "radius_miles": {"type": "number", "description": "Search radius in miles (default 100)"},
                },
                "required": ["location", "date_from", "date_to"],
            },
        ),
        types.Tool(
            name="subscribe_to_events",
            description=(
                "Subscribe a user to price-change alerts for one or more events. "
                "Call this after search_events so you have the event IDs."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "event_ids":       {"type": "array", "items": {"type": "string"}, "description": "List of event IDs"},
                    "user_email":      {"type": "string", "description": "Email address for alerts"},
                    "price_threshold": {"type": "number", "description": "Alert only when price drops below this USD value (optional)"},
                    "notify_on":       {"type": "string", "enum": ["any", "drop", "rise"], "description": "Defaults to 'any'"},
                },
                "required": ["event_ids", "user_email"],
            },
        ),
        types.Tool(
            name="list_subscriptions",
            description="List all active price-alert subscriptions for a user.",
            inputSchema={
                "type": "object",
                "properties": {"user_email": {"type": "string"}},
                "required": ["user_email"],
            },
        ),
        types.Tool(
            name="unsubscribe",
            description="Cancel price-alert subscriptions for one or more events.",
            inputSchema={
                "type": "object",
                "properties": {
                    "event_ids":  {"type": "array", "items": {"type": "string"}},
                    "user_email": {"type": "string"},
                },
                "required": ["event_ids", "user_email"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:

    if name == "search_events":
        location    = arguments["location"]
        date_from   = arguments["date_from"]
        date_to     = arguments["date_to"]
        radius      = int(arguments.get("radius_miles", 100))

        coords = resolve_location(location)
        if not coords:
            return [types.TextContent(type="text", text=f"Could not geocode location: '{location}'.")]
        lat, lng = coords

        try:
            results = tm_search(lat, lng, date_from, date_to, radius)
        except RuntimeError as e:
            return [types.TextContent(type="text", text=str(e))]

        for r in results:
            r["distance_miles"] = round(haversine(lat, lng, r["lat"], r["lng"]))
        results.sort(key=lambda x: (x["distance_miles"], x.get("price_usd") or 9999))

        if not results:
            return [types.TextContent(type="text", text=f"No events found near '{location}' between {date_from} and {date_to}.")]
        return [types.TextContent(type="text", text=json.dumps(results, indent=2))]

    elif name == "subscribe_to_events":
        event_ids       = arguments["event_ids"]
        user_email      = arguments["user_email"]
        price_threshold = arguments.get("price_threshold")
        notify_on       = arguments.get("notify_on", "any")

        subscribed, not_found = [], []
        for eid in event_ids:
            event = fetch_event_details(eid)
            if not event:
                not_found.append(eid)
                continue
            upsert_subscription(
                match_id=eid,
                user_email=user_email,
                last_price=event.get("price_usd") or 0,
                price_threshold=price_threshold,
                notify_on=notify_on,
                event_title=event.get("title", ""),
                event_venue=event.get("venue", ""),
                event_city=event.get("city", ""),
                event_date=event.get("date", ""),
            )
            subscribed.append(f"{event['title']} ({event['city']}) on {event['date']}")

        lines = []
        if subscribed:
            lines.append(f"Subscribed ({notify_on} price changes):")
            for s in subscribed:
                lines.append(f"  • {s}")
            if price_threshold:
                lines.append(f"You'll be alerted when the price drops below ${price_threshold}.")
            else:
                lines.append("You'll be alerted on any price change.")
        if not_found:
            lines.append(f"Event IDs not found: {', '.join(not_found)}")
        return [types.TextContent(type="text", text="\n".join(lines))]

    elif name == "list_subscriptions":
        user_email = arguments["user_email"]
        subs = get_subscriptions_for_user(user_email)
        if not subs:
            return [types.TextContent(type="text", text=f"No active subscriptions for {user_email}.")]

        lines = [f"Active subscriptions for {user_email}:"]
        for s in subs:
            title     = s.get("event_title") or s["match_id"]
            date      = s.get("event_date") or ""
            threshold = f"below ${s['price_threshold']}" if s["price_threshold"] else "any change"
            lines.append(
                f"  • {title} ({date}) — "
                f"notify on: {s['notify_on']}, threshold: {threshold}, "
                f"last known price: ${s['last_price']}"
            )
        return [types.TextContent(type="text", text="\n".join(lines))]

    elif name == "unsubscribe":
        event_ids  = arguments["event_ids"]
        user_email = arguments["user_email"]
        subs = {s["match_id"]: s for s in get_subscriptions_for_user(user_email)}

        removed, not_found = [], []
        for eid in event_ids:
            if delete_subscription(eid, user_email):
                removed.append(subs.get(eid, {}).get("event_title") or eid)
            else:
                not_found.append(eid)

        lines = []
        if removed:
            lines.append(f"Unsubscribed from: {', '.join(removed)}")
        if not_found:
            lines.append(f"No subscription found for: {', '.join(not_found)}")
        return [types.TextContent(type="text", text="\n".join(lines))]

    return [types.TextContent(type="text", text=f"Unknown tool: {name}")]


if __name__ == "__main__":
    asyncio.run(stdio_server(server))
