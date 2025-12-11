from __future__ import annotations
import httpx
from datetime import date, datetime, timedelta
from django.conf import settings
from django.core.cache import cache
from django.urls import reverse
from django.utils import timezone
from typing import List, Dict, Any
from .services import JolpiClient, url_for_year

CURRENT_YEAR = 2025

# ---- API health ----
API_HEALTH_KEY = "api_health_simple_ok"
TTL_SECONDS = 15  

# ---- Schedule menu cache ----
_CACHE = {"ts": None, "year": None, "last5": None}
_TTL = timedelta(minutes=10)

# ---- teams menu cache ----
_CONSTRUCTORS_CACHE = {"ts": None, "year": None, "items": None}
_CONSTRUCTORS_TTL = timedelta(minutes=10)

# ---- Drivers menu cache ----
_DRIVERS_CACHE = {"ts": None, "year": None, "items": None}
_DRIVERS_TTL = timedelta(minutes=30)

# ---- API health function ----
def _quick_ping() -> bool:
    """
    Lightweight API connectivity check using JolpiClient.
    Success = MRData.total > 0 on a tiny endpoint.
    """
    base = getattr(settings, "JOLPICA_BASE", "https://api.jolpi.ca")
    prefix = getattr(settings, "JOLPICA_PREFIX", "/ergast/f1")
    url = f"{base}{prefix}/seasons.json?limit=1"

    try:
        from .services import JolpiClient  
        with JolpiClient(timeout=3.0) as client:
            resp = client.get_url(url)
        total = int((resp.get("MRData", {}) or {}).get("total") or 0)
        return total > 0
    except Exception:
        return False

def api_health(request) -> Dict[str, Any]:
    ok = cache.get(API_HEALTH_KEY)
    if ok is None or TTL_SECONDS == 0:
        ok = _quick_ping()
        if TTL_SECONDS > 0:
            cache.set(API_HEALTH_KEY, ok, TTL_SECONDS)

    return {
        "API_DEGRADED": not ok,
        "API_DEGRADED_MESSAGE": (
            "Live F1 data is currently slow or unreachable. "
            "Some stats may be missing or out of date. Please try again in a few minutes."
        ) if not ok else None,
    }
# ------------- Schedule helpers -------------

def _fetch_year_races(year: int) -> List[Dict[str, Any]]:
    with JolpiClient() as client:
        url = url_for_year("races", year)
        payload = client.get_url(url)
    return (
        payload.get("MRData", {})
        .get("RaceTable", {})
        .get("Races", [])
    )


def _last_completed_round(races: List[Dict[str, Any]]) -> int | None:
    today = date.today()
    past = []
    for r in races:
        try:
            if date.fromisoformat(r.get("date")) <= today:
                past.append(int(r.get("round")))
        except Exception:
            continue
    return max(past) if past else None


def _compute_last5(year: int) -> List[Dict[str, Any]]:
    races = _fetch_year_races(year)
    last_done = _last_completed_round(races)
    if not last_done:
        return []
    rounds = [r for r in races if int(r.get("round", 0)) <= last_done]
    rounds_sorted = sorted(rounds, key=lambda r: int(r["round"]))
    return rounds_sorted[-5:]


# ------------- Schedule menu (navbar) -------------

def schedule_menu(request):
    """Inject last-5 races + current-year schedule URL into all templates."""
    now = timezone.now()
    if (
        _CACHE["ts"] is None
        or _CACHE["year"] != CURRENT_YEAR
        or _CACHE["last5"] is None
        or now - _CACHE["ts"] > _TTL
    ):
        last5 = _compute_last5(CURRENT_YEAR)
        _CACHE.update({"ts": now, "year": CURRENT_YEAR, "last5": last5})

    items = []
    for r in _CACHE["last5"] or []:
        season = int(r.get("season") or CURRENT_YEAR)
        rnd = int(r["round"])
        label = f"Round {rnd} — {r['raceName']} ({r['Circuit']['Location']['country']})"
        url = reverse("f1:schedule_sessions", args=[season, rnd])
        items.append({"label": label, "url": url})

    year_url = reverse("f1:schedule_year", args=[CURRENT_YEAR])

    return {
        "SCHEDULE_MENU": {
            "year": CURRENT_YEAR,
            "items": items,
            "year_url": year_url,
        }
    }


# ------------- Results menu (navbar) -------------

def results_menu(request):
    """Provide Results dropdown links for the current season."""
    return {
        "RESULTS_MENU": {
            "year": CURRENT_YEAR,
            "season_results_url": reverse("f1:results_season", args=[CURRENT_YEAR]),
            "driver_standings_url": reverse("f1:standings_drivers", args=[CURRENT_YEAR]),
            "constructor_standings_url": reverse("f1:standings_constructors", args=[CURRENT_YEAR]),
        }
    }


# ------------- Drivers menu (navbar) -------------

def _fetch_year_drivers(year: int) -> List[Dict[str, Any]]:
    with JolpiClient() as client:
        url = url_for_year("drivers", year) 
        data = client.get_url(url)
    return (
        data.get("MRData", {})
        .get("DriverTable", {})
        .get("Drivers", [])
    )


def _thumb_filename_for_driver(d: Dict[str, Any]) -> str:
    """
    Build thumbs filename like 'lastname-firstname.png' (lowercase, spaces -> hyphens).
    Examples:
      'norris-lando.png', 'albon-alex.png', 'antonelli-kimi-andrea.png'
    """
    family = (d.get("familyName") or "").strip().lower().replace(" ", "-")
    given = (d.get("givenName") or "").strip().lower().replace(" ", "-")
    return f"{family}-{given}.png" if family or given else "unknown.png"


def drivers_menu(request):
    """
    Provide Drivers dropdown: all current-year drivers (excluding Jack Doohan),
    sorted alphabetically by last name, each with a computed thumbnails filename.
    """
    now = timezone.now()
    if (
        _DRIVERS_CACHE["ts"] is None
        or _DRIVERS_CACHE["year"] != CURRENT_YEAR
        or _DRIVERS_CACHE["items"] is None
        or now - _DRIVERS_CACHE["ts"] > _DRIVERS_TTL
    ):
        drivers = _fetch_year_drivers(CURRENT_YEAR)

        drivers = [d for d in drivers if (d.get("familyName") or "").lower() != "doohan"]

        drivers.sort(key=lambda d: (d.get("familyName") or "").lower())

        items = []
        for d in drivers:
            driver_id = d.get("driverId")  
            given = d.get("givenName", "")
            family = d.get("familyName", "")
            label = f"{family}, {given}".strip(", ")

            items.append({
                "driverId": driver_id,
                "label": label,
                "url": reverse("f1:driver_detail", args=[driver_id]),
                "thumb": _thumb_filename_for_driver(d),  
            })

        _DRIVERS_CACHE.update({"ts": now, "year": CURRENT_YEAR, "items": items})

    return {
        "DRIVERS_MENU": {
            "year": CURRENT_YEAR,
            "items": _DRIVERS_CACHE["items"] or [],
        }
    }


def _fetch_year_constructors(year: int):
    with JolpiClient() as client:
        url = url_for_year("constructors", year)  
        data = client.get_url(url)
    return (
        data.get("MRData", {})
            .get("ConstructorTable", {})
            .get("Constructors", [])
    )

def _constructor_thumb_filename(c: dict) -> str:
    """
    Prefer constructorId with underscores -> hyphens, then .png
    e.g., 'aston_martin' -> 'aston-martin.png', 'red_bull' -> 'red-bull.png'
    """
    cid = (c.get("constructorId") or "").strip().lower()
    return f"{cid.replace('_', '-')}.png" if cid else "placeholder.png"

def constructors_menu(request):
    """Provide Teams dropdown: all current-year constructors (A→Z), dead links for now."""
    from .context_processors import CURRENT_YEAR  
    now = datetime.utcnow()

    if (
        _CONSTRUCTORS_CACHE["ts"] is None
        or _CONSTRUCTORS_CACHE["year"] != CURRENT_YEAR
        or _CONSTRUCTORS_CACHE["items"] is None
        or now - _CONSTRUCTORS_CACHE["ts"] > _CONSTRUCTORS_TTL
    ):
        teams = _fetch_year_constructors(CURRENT_YEAR)

        
        teams.sort(key=lambda c: (c.get("name") or "").lower())

        items = []
        for c in teams:
            items.append({
                "constructorId": c.get("constructorId"),
                "label": c.get("name"),
                "thumb": _constructor_thumb_filename(c),
                "url": reverse("f1:constructor_detail", args=[c.get("constructorId")]),
            })

        _CONSTRUCTORS_CACHE.update({"ts": now, "year": CURRENT_YEAR, "items": items})

    return {
        "CONSTRUCTORS_MENU": {
            "year": CURRENT_YEAR,
            "items": _CONSTRUCTORS_CACHE["items"] or [],
        }
    }