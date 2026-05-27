"""
Shared constants for the Live Events Ticket Agent.
"""

# ── Ticketmaster API ──────────────────────────────────────────────────────────

TM_API_BASE        = "https://app.ticketmaster.com/discovery/v2"
TM_USER_AGENT      = "live-events-agent/1.0"
TM_REQUEST_TIMEOUT = 10          # seconds per HTTP request
TM_MAX_RETRIES     = 3
TM_RETRY_WAITS     = (1, 2, 4)  # seconds between retry attempts

# Event search defaults
TM_SEARCH_CLASSIFICATIONS = "music,sports,arts & theatre"
TM_SEARCH_PAGE_SIZE       = 50
TM_SEARCH_SORT            = "distance,asc"
TM_SEARCH_RADIUS_DEFAULT  = 100  # miles

# ── LLM ──────────────────────────────────────────────────────────────────────

GROQ_MODEL           = "meta-llama/llama-4-scout-17b-16e-instruct"
MAX_AGENTIC_STEPS    = 10   # max tool-call iterations per chat turn
MAX_HISTORY_MESSAGES = 40   # system msg + last N messages kept per user

# ── Auth ──────────────────────────────────────────────────────────────────────

JWT_ALGORITHM        = "HS256"
JWT_EXPIRE_DAYS      = 7
MIN_PASSWORD_LENGTH  = 8
