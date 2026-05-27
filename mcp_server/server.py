"""
Live Events Ticket Agent — MCP Server (Streamable HTTP transport)

Run locally (stdio):  python -m mcp_server.server --stdio
Run as HTTP server:   python -m mcp_server.server
                      → listens on $PORT (default 8080) at /mcp

Remote clients must pass:  Authorization: Bearer $MCP_API_KEY
"""

import asyncio
import json
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

load_dotenv()

from mcp.server.fastmcp import FastMCP
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from mcp_server.db import (
    delete_subscription,
    get_subscriptions_for_user,
    init_db,
    upsert_subscription,
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

mcp = FastMCP("live-events-agent")


# ── Auth middleware ───────────────────────────────────────────────────────────

class BearerAuthMiddleware(BaseHTTPMiddleware):
    """Reject requests that don't carry the correct MCP_API_KEY."""

    async def dispatch(self, request, call_next):
        api_key = os.getenv("MCP_API_KEY")
        if not api_key:
            # No key configured — allow all (useful for local dev)
            return await call_next(request)
        auth = request.headers.get("Authorization", "")
        if auth != f"Bearer {api_key}":
            return Response("Unauthorized", status_code=401)
        return await call_next(request)


# ── Tools ─────────────────────────────────────────────────────────────────────

@mcp.tool()
async def search_events(
    location: str,
    date_from: str,
    date_to: str,
    radius_miles: int = 100,
) -> str:
    """
    Search for live events (concerts, sports, theater) near a location.

    Args:
        location: City name or place, e.g. 'Raleigh, NC'
        date_from: Start of date range, YYYY-MM-DD
        date_to: End of date range, YYYY-MM-DD
        radius_miles: Search radius in miles (default 100)
    """
    coords = resolve_location(location)
    if not coords:
        return f"Could not geocode location: '{location}'"
    lat, lng = coords

    try:
        results = await asyncio.to_thread(
            tm_search, lat, lng, date_from, date_to, radius_miles
        )
    except TicketmasterError as e:
        return f"Ticketmaster search failed: {e}"

    for r in results:
        r["distance_miles"] = round(haversine(lat, lng, r["lat"], r["lng"]))
    results.sort(key=lambda x: (x["distance_miles"], x.get("price_usd") or 9999))

    if not results:
        return (
            f"No events found near '{location}' "
            f"between {date_from} and {date_to}."
        )
    return json.dumps(results, indent=2)


@mcp.tool()
async def subscribe_to_events(
    event_ids: list[str],
    user_email: str,
    price_threshold: float | None = None,
    notify_on: str = "any",
) -> str:
    """
    Subscribe a user to price-change alerts for one or more events.

    Args:
        event_ids: List of event IDs from search_events results
        user_email: Email address to send alerts to
        price_threshold: Alert only when price drops below this USD value
        notify_on: 'any' | 'drop' | 'rise' (default 'any')
    """
    subscribed, not_found = [], []
    for eid in event_ids:
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
            price_threshold, notify_on,
            event.get("title", ""), event.get("venue", ""),
            event.get("city", ""),  event.get("date", ""),
        )
        subscribed.append(
            f"{event['title']} ({event['city']}) on {event['date']}"
        )

    lines = []
    if subscribed:
        lines.append(f"Subscribed ({notify_on} price changes):")
        lines.extend(f"  • {s}" for s in subscribed)
        if price_threshold:
            lines.append(f"Alert threshold: below ${price_threshold}")
    if not_found:
        lines.append(f"Event IDs not found: {', '.join(not_found)}")
    return "\n".join(lines)


@mcp.tool()
async def list_subscriptions(user_email: str) -> str:
    """
    List all active price-alert subscriptions for a user.

    Args:
        user_email: The user's email address
    """
    subs = await asyncio.to_thread(get_subscriptions_for_user, user_email)
    if not subs:
        return f"No active subscriptions for {user_email}."

    lines = [f"Active subscriptions for {user_email}:"]
    for s in subs:
        title     = s.get("event_title") or s["match_id"]
        date      = s.get("event_date") or ""
        threshold = (
            f"below ${s['price_threshold']}"
            if s["price_threshold"] else "any change"
        )
        lines.append(
            f"  • {title} ({date}) — "
            f"notify on: {s['notify_on']}, threshold: {threshold}, "
            f"last price: ${s['last_price']}"
        )
    return "\n".join(lines)


@mcp.tool()
async def unsubscribe(event_ids: list[str], user_email: str) -> str:
    """
    Cancel price-alert subscriptions for one or more events.

    Args:
        event_ids: List of event IDs to unsubscribe from
        user_email: The user's email address
    """
    subs = {
        s["match_id"]: s
        for s in await asyncio.to_thread(get_subscriptions_for_user, user_email)
    }
    removed, not_found = [], []
    for eid in event_ids:
        ok = await asyncio.to_thread(delete_subscription, eid, user_email)
        if ok:
            removed.append(subs.get(eid, {}).get("event_title") or eid)
        else:
            not_found.append(eid)

    lines = []
    if removed:
        lines.append(f"Unsubscribed from: {', '.join(removed)}")
    if not_found:
        lines.append(f"No subscription found for: {', '.join(not_found)}")
    return "\n".join(lines)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if "--stdio" in sys.argv:
        # Local Claude Desktop mode
        asyncio.run(mcp.run_stdio_async())
    else:
        # Remote HTTP mode — add auth middleware then serve
        init_db()
        app = mcp.streamable_http_app()
        app.add_middleware(BearerAuthMiddleware)

        import uvicorn
        port = int(os.getenv("PORT", 8080))
        log.info("MCP HTTP server starting on port %d at /mcp", port)
        uvicorn.run(app, host="0.0.0.0", port=port)
