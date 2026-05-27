import math
import urllib.request
import urllib.parse
import json


def haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Return distance in miles between two lat/lng points."""
    R = 3958.8
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlng / 2) ** 2
    )
    return R * 2 * math.asin(math.sqrt(a))


def geocode_city(city: str) -> tuple[float, float] | None:
    """
    Geocode a city name to (lat, lng) using the free Nominatim API.
    Returns None if the city cannot be found.
    """
    query = urllib.parse.urlencode({"q": city, "format": "json", "limit": 1})
    url = f"https://nominatim.openstreetmap.org/search?{query}"
    req = urllib.request.Request(url, headers={"User-Agent": "fifa-ticket-agent/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            results = json.loads(resp.read())
            if results:
                return float(results[0]["lat"]), float(results[0]["lon"])
    except Exception:
        pass
    return None


# Fallback coordinates for common US cities so the app works offline / without network
CITY_COORDS: dict[str, tuple[float, float]] = {
    "raleigh":          (35.7796, -78.6382),
    "charlotte":        (35.2271, -80.8431),
    "new york":         (40.7128, -74.0060),
    "los angeles":      (34.0522, -118.2437),
    "chicago":          (41.8781, -87.6298),
    "dallas":           (32.7767, -96.7970),
    "miami":            (25.7617, -80.1918),
    "boston":           (42.3601, -71.0589),
    "philadelphia":     (39.9526, -75.1652),
    "san francisco":    (37.7749, -122.4194),
    "seattle":          (47.6062, -122.3321),
    "atlanta":          (33.7490, -84.3880),
    "washington":       (38.9072, -77.0369),
    "houston":          (29.7604, -95.3698),
    "phoenix":          (33.4484, -112.0740),
}


def resolve_location(location: str) -> tuple[float, float] | None:
    """
    Resolve a location string to (lat, lng).
    Tries the local fallback dict first, then Nominatim.
    """
    key = location.lower().strip()
    if key in CITY_COORDS:
        return CITY_COORDS[key]
    # Try partial match
    for city, coords in CITY_COORDS.items():
        if city in key or key in city:
            return coords
    # Fall back to live geocoding
    return geocode_city(location)