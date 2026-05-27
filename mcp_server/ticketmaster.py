"""
Ticketmaster Discovery API client.

Shared by api.py, agent/chat.py, mcp_server/server.py, and monitor/.
All calls are synchronous (urllib); wrap with asyncio.to_thread in async
contexts. Retries up to TM_MAX_RETRIES times with exponential back-off
on 429 / 5xx / network errors.
"""

import json
import logging
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime

from mcp_server.constants import (
    TM_API_BASE,
    TM_MAX_RETRIES,
    TM_REQUEST_TIMEOUT,
    TM_RETRY_WAITS,
    TM_SEARCH_CLASSIFICATIONS,
    TM_SEARCH_PAGE_SIZE,
    TM_SEARCH_RADIUS_DEFAULT,
    TM_SEARCH_SORT,
    TM_USER_AGENT,
)

log = logging.getLogger(__name__)


# ── Custom exceptions ────────────────────────────────────────────────────────


class TicketmasterError(Exception):
    """Base error for Ticketmaster API failures."""


class TicketmasterRateLimitError(TicketmasterError):
    """Raised when Ticketmaster returns HTTP 429."""


class TicketmasterNotFoundError(TicketmasterError):
    """Raised when the requested event does not exist (HTTP 404)."""


# ── HTTP layer ───────────────────────────────────────────────────────────────


def _retry_wait(attempt: int) -> float:
    """Return the back-off delay (seconds) for the given attempt index."""
    return TM_RETRY_WAITS[min(attempt, len(TM_RETRY_WAITS) - 1)]


def _build_url(path: str, params: dict) -> tuple[str, str]:
    """Return (full_url_with_key, safe_url_without_key)."""
    api_key = os.getenv("TICKETMASTER_API_KEY")
    if not api_key:
        raise TicketmasterError("TICKETMASTER_API_KEY not set in .env")
    full = (
        f"{TM_API_BASE}{path}"
        f"?{urllib.parse.urlencode({**params, 'apikey': api_key})}"
    )
    safe = f"{TM_API_BASE}{path}?{urllib.parse.urlencode(params)}"
    return full, safe


def _handle_http_error(
    exc: urllib.error.HTTPError,
    attempt: int,
    safe_url: str,
) -> Exception:
    """
    Handle an HTTPError from a single attempt.
    Returns the exception to store as last_exc, or raises immediately
    for non-retryable codes.
    """
    if exc.code == 404:
        raise TicketmasterNotFoundError(safe_url) from exc
    if exc.code == 429:
        wait = _retry_wait(attempt)
        log.warning(
            "Rate-limited (attempt %d/%d) — retrying in %ds",
            attempt + 1, TM_MAX_RETRIES, wait,
        )
        time.sleep(wait)
        return TicketmasterRateLimitError(
            f"Rate limited after {attempt + 1} attempts"
        )
    if exc.code >= 500:
        wait = _retry_wait(attempt)
        log.warning(
            "Server error %s (attempt %d/%d) — retrying in %ds",
            exc.code, attempt + 1, TM_MAX_RETRIES, wait,
        )
        time.sleep(wait)
        return TicketmasterError(f"HTTP {exc.code}")
    raise TicketmasterError(f"HTTP {exc.code}: {exc.reason}") from exc


def _get(path: str, params: dict) -> dict:
    """GET request to the Ticketmaster API with retry/back-off."""
    url, safe_url = _build_url(path, params)
    last_exc: Exception = RuntimeError("unreachable")

    for attempt in range(TM_MAX_RETRIES):
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": TM_USER_AGENT}
            )
            with urllib.request.urlopen(
                req, timeout=TM_REQUEST_TIMEOUT
            ) as resp:
                return json.loads(resp.read())

        except urllib.error.HTTPError as exc:
            last_exc = _handle_http_error(exc, attempt, safe_url)

        except urllib.error.URLError as exc:
            wait = _retry_wait(attempt)
            log.warning(
                "Network error (attempt %d/%d): %s — retrying in %ds",
                attempt + 1, TM_MAX_RETRIES, exc.reason, wait,
            )
            time.sleep(wait)
            last_exc = TicketmasterError(f"Network error: {exc.reason}")

    raise last_exc


# ── Event mapping ────────────────────────────────────────────────────────────


def _parse_venue(event: dict) -> tuple[dict, float, float]:
    """Extract venue object and coordinates from a raw event."""
    venues = event.get("_embedded", {}).get("venues", [{}])
    venue_obj = venues[0] if venues else {}
    location = venue_obj.get("location", {})
    try:
        lat = float(location.get("latitude") or 0)
        lng = float(location.get("longitude") or 0)
    except (TypeError, ValueError):
        lat, lng = 0.0, 0.0
    return venue_obj, lat, lng


def _parse_date(event: dict) -> str | None:
    """Extract and normalise the event start date to YYYY-MM-DD, or None."""
    dates = event.get("dates", {})
    dt_str = (
        dates.get("start", {}).get("dateTime", "")
        or dates.get("start", {}).get("localDate", "")
    )
    if not dt_str:
        return None
    try:
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        return None


def _parse_price(event: dict) -> float | None:
    """Return the lowest listed price, or None if unavailable."""
    price_ranges = event.get("priceRanges", [])
    return price_ranges[0].get("min") if price_ranges else None


def _parse_category(event: dict) -> str:
    """Return the segment name (music, sports, arts…) in lower-case."""
    classifications = event.get("classifications", [{}])
    if not classifications:
        return "other"
    return (
        classifications[0].get("segment", {}).get("name", "").lower()
        or "other"
    )


def _build_event_dict(
    event: dict,
    venue_obj: dict,
    lat: float,
    lng: float,
    date: str,
    price: float | None,
    category: str,
) -> dict:
    """Assemble the normalised event dict from pre-parsed fields."""
    city = venue_obj.get("city", {}).get("name", "")
    state = venue_obj.get("state", {}).get("stateCode", "")
    return {
        "id":               str(event["id"]),
        "title":            event.get("name", "TBD"),
        "category":         category,
        "venue":            venue_obj.get("name", ""),
        "city":             f"{city}, {state}" if state else city,
        "lat":              lat,
        "lng":              lng,
        "date":             date,
        "price_usd":        price,
        "ticketmaster_url": event.get("url", ""),
    }


def _map_event(event: dict) -> dict | None:
    """Map a raw Ticketmaster event to our internal format, or None."""
    venue_obj, lat, lng = _parse_venue(event)
    date = _parse_date(event)
    if date is None:
        return None
    return _build_event_dict(
        event,
        venue_obj,
        lat,
        lng,
        date,
        _parse_price(event),
        _parse_category(event),
    )


# ── Public API ───────────────────────────────────────────────────────────────


def search_events(
    lat: float,
    lng: float,
    date_from: str,
    date_to: str,
    radius_miles: int = TM_SEARCH_RADIUS_DEFAULT,
) -> list[dict]:
    """
    Search Ticketmaster for music / sports / arts events near a lat-lng
    within a date range. Returns a list of mapped event dicts.
    Raises TicketmasterError on failure.
    """
    params = {
        "latlong":            f"{lat},{lng}",
        "radius":             radius_miles,
        "unit":               "miles",
        "startDateTime":      f"{date_from}T00:00:00Z",
        "endDateTime":        f"{date_to}T23:59:59Z",
        "classificationName": TM_SEARCH_CLASSIFICATIONS,
        "size":               TM_SEARCH_PAGE_SIZE,
        "sort":               TM_SEARCH_SORT,
    }
    data = _get("/events.json", params)
    raw = data.get("_embedded", {}).get("events", [])
    results = [m for e in raw if (m := _map_event(e)) is not None]
    log.info(
        "Search (%.4f, %.4f) %s → %s: %d results",
        lat, lng, date_from, date_to, len(results),
    )
    return results


def fetch_event_details(event_id: str) -> dict | None:
    """
    Fetch full event details by Ticketmaster ID.
    Returns a mapped event dict, or None if the event does not exist.
    Raises TicketmasterError on other failures.
    """
    try:
        data = _get(f"/events/{event_id}.json", {})
        return _map_event(data)
    except TicketmasterNotFoundError:
        log.warning("Event not found: %s", event_id)
        return None


def fetch_event_price(event_id: str) -> float | None:
    """
    Fetch the current lowest ticket price for a single event.
    Uses the search endpoint (which reliably includes priceRanges) rather than
    the direct event endpoint which often omits pricing data.
    Returns None if the event has no price or does not exist.
    """
    try:
        data = _get("/events.json", {"id": event_id})
        events = (
            data.get("_embedded", {}).get("events", [])
        )
        if not events:
            log.warning("Event not found when fetching price: %s", event_id)
            return None
        return _parse_price(events[0])
    except TicketmasterNotFoundError:
        log.warning("Event not found when fetching price: %s", event_id)
        return None
