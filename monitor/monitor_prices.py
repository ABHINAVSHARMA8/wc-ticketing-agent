"""
Live Events Ticket Agent — Background Price Monitor

Run once:       python3 monitor/monitor_prices.py
Run in loop:    python3 monitor/monitor_prices.py --loop --interval 60
"""

import argparse
import json
import logging
import os
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

from mcp_server.db import get_all_active_subscriptions, log_price, update_last_price
from mcp_server.ticketmaster import fetch_event_price

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()],
)
log = logging.getLogger(__name__)


# ── Email via Resend ──────────────────────────────────────────────────────────

def send_email_alert(to_email: str, event: dict, old_price: float, new_price: float):
    api_key = os.getenv("RESEND_API_KEY")
    direction  = "dropped" if new_price < old_price else "rose"
    change_pct = abs(new_price - old_price) / old_price * 100
    arrow      = "↓" if direction == "dropped" else "↑"
    color      = "#16a34a" if direction == "dropped" else "#dc2626"

    if not api_key:
        log.warning(
            "[ALERT — no RESEND_API_KEY] %s %s $%.2f → $%.2f (%s%.1f%%) → %s",
            event["title"], direction, old_price, new_price, arrow, change_pct, to_email,
        )
        return

    html = f"""
    <div style="font-family:sans-serif;max-width:520px;margin:0 auto;color:#111">
      <div style="background:#1a56db;padding:20px 24px;border-radius:8px 8px 0 0">
        <h1 style="color:#fff;margin:0;font-size:20px">🎫 Live Events Ticket Alert</h1>
      </div>
      <div style="border:1px solid #e5e7eb;border-top:none;padding:24px;border-radius:0 0 8px 8px">
        <p style="margin:0 0 16px">A ticket price you're watching just changed:</p>
        <table style="width:100%;border-collapse:collapse;font-size:15px">
          <tr><td style="padding:6px 0;color:#6b7280">Event</td>
              <td style="padding:6px 0;font-weight:600">{event['title']}</td></tr>
          <tr><td style="padding:6px 0;color:#6b7280">Venue</td>
              <td style="padding:6px 0">{event['venue']}, {event['city']}</td></tr>
          <tr><td style="padding:6px 0;color:#6b7280">Date</td>
              <td style="padding:6px 0">{event['date']}</td></tr>
          <tr><td style="padding:6px 0;color:#6b7280">Old price</td>
              <td style="padding:6px 0;text-decoration:line-through">${old_price:.2f}</td></tr>
          <tr><td style="padding:6px 0;color:#6b7280">New price</td>
              <td style="padding:6px 0;font-weight:700;font-size:18px;color:{color}">
                {arrow} ${new_price:.2f}
                <span style="font-size:13px;font-weight:400">({change_pct:.1f}% {direction})</span>
              </td></tr>
        </table>
        <p style="font-size:12px;color:#9ca3af;margin-top:24px">
          You're receiving this because you subscribed to price alerts for this event.
        </p>
      </div>
    </div>
    """

    payload = json.dumps({
        "from":    "Live Events Alerts <onboarding@resend.dev>",
        "to":      [to_email],
        "subject": f"🎫 {event['title']} tickets {direction}: ${old_price:.0f} → ${new_price:.0f}",
        "html":    html,
    }).encode()

    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=payload,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            resp.read()
        log.info("Email sent to %s — %s %s $%.2f → $%.2f",
                 to_email, event["title"], direction, old_price, new_price)
    except urllib.error.HTTPError as e:
        log.error("Resend error %s: %s", e.code, e.read().decode())
    except Exception as e:
        log.error("Failed to send email: %s", e)


# ── Alert logic ───────────────────────────────────────────────────────────────

def should_alert(old_price: float, new_price: float, notify_on: str, price_threshold: float | None) -> bool:
    if old_price == new_price:
        return False
    price_dropped = new_price < old_price
    if notify_on == "drop" and not price_dropped:
        return False
    if notify_on == "rise" and price_dropped:
        return False
    if price_threshold is not None and price_dropped:
        return new_price <= price_threshold
    return True


# ── Main check ────────────────────────────────────────────────────────────────

def run_check():
    log.info("Price source: Ticketmaster live API")
    subscriptions = get_all_active_subscriptions()

    if not subscriptions:
        log.info("No active subscriptions — nothing to check.")
        return

    log.info("Checking %d subscription(s)...", len(subscriptions))
    alerts_sent = 0

    for sub in subscriptions:
        event_id = sub["match_id"]
        # Event details are stored in the subscription row
        event = {
            "title": sub.get("event_title") or event_id,
            "venue": sub.get("event_venue") or "",
            "city":  sub.get("event_city")  or "",
            "date":  sub.get("event_date")  or "",
        }

        current_price = fetch_event_price(event_id)
        if current_price is None:
            log.warning("No live price for '%s' — skipping.", event["title"])
            continue

        old_price = sub["last_price"]
        log.info("%-50s  $%.2f → $%.2f", event["title"][:50], old_price, current_price)
        log_price(event_id, current_price)

        if should_alert(old_price, current_price, sub["notify_on"], sub["price_threshold"]):
            send_email_alert(sub["user_email"], event, old_price, current_price)
            alerts_sent += 1

        update_last_price(sub["id"], current_price)

    log.info("Done. %d alert(s) sent.", alerts_sent)


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Live Events Ticket Price Monitor")
    parser.add_argument("--loop",     action="store_true", help="Run continuously")
    parser.add_argument("--interval", type=int, default=600, help="Seconds between checks (default: 600)")
    args = parser.parse_args()

    if args.loop:
        log.info("Monitor started (interval: %ds). Ctrl+C to stop.", args.interval)
        while True:
            run_check()
            log.info("Sleeping %ds...", args.interval)
            time.sleep(args.interval)
    else:
        run_check()


if __name__ == "__main__":
    main()
