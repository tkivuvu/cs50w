import time
from datetime import date, datetime, timedelta
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.http import Http404
from django.views.decorators.http import require_POST
from .forms import SignUpForm
from .models import FavoriteDriver, FavoriteConstructor
from .news import fetch_news_rss, driver_query, team_query
from .services import JolpiClient, url_for_year, url_for_round


CURRENT_YEAR = 2025

_RESULTS_CACHE: dict[str, dict] = {}   
_CACHE_TTL = timedelta(minutes=5)

def _cache_get(key: str):
    rec = _RESULTS_CACHE.get(key)
    if not rec:
        return None
    if datetime.utcnow() - rec["ts"] > _CACHE_TTL:
        return None
    return rec["data"]

def _cache_set(key: str, data: dict):
    _RESULTS_CACHE[key] = {"ts": datetime.utcnow(), "data": data}

def _load_year_collection(resource: str, year: int, per_page: int = 200) -> dict:
    """
    Fetch a *season-scoped* collection with pagination (limit/offset),
    merging pages into a single MRData payload. Minimizes API calls
    vs. per-round fetching and avoids 429s.
    """
    cache_key = f"{resource}:{year}:{per_page}"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    with JolpiClient() as client:
        base = url_for_year(resource, year)  
        merged: dict | None = None
        offset = 0

        while True:
            sep = '&' if '?' in base else '?'
            url = f"{base}{sep}limit={per_page}&offset={offset}"
            for attempt in range(3):
                try:
                    page = client.get_url(url)
                    break
                except Exception as ex:
                    time.sleep(0.6 * (attempt + 1))
            else:
                raise

            mr = page.get("MRData", {})
            total = int(mr.get("total") or 0)
            limit = int(mr.get("limit") or per_page)
            off = int(mr.get("offset") or offset)

            if merged is None:
                merged = page
            else:
                if resource == "results":
                    merged["MRData"]["RaceTable"]["Races"] += mr.get("RaceTable", {}).get("Races", [])
                elif resource == "sprint":
                    merged["MRData"]["RaceTable"]["Races"] += mr.get("RaceTable", {}).get("Races", [])
                elif resource == "drivers":
                    merged["MRData"]["DriverTable"]["Drivers"] += mr.get("DriverTable", {}).get("Drivers", [])
                elif resource == "races":
                    merged["MRData"]["RaceTable"]["Races"] += mr.get("RaceTable", {}).get("Races", [])
                elif resource == "driverstandings":
                    merged = page
                else:
                    merged = page  

            offset = off + limit
            if offset >= total or total == 0:
                break

    if merged is None:
        merged = {"MRData": {}}
    _cache_set(cache_key, merged)
    return merged

def _load_year_payload(resource: str, year: int) -> dict:
    """
    GET a year-scoped resource (e.g., 'drivers', 'driverstandings', 'results', 'sprint', 'races')
    with a high limit so we don't get paginated/truncated data.
    """
    with JolpiClient() as client:
        base = url_for_year(resource, year)  
        sep = '&' if '?' in base else '?'
        url = f"{base}{sep}limit=1000"
        return client.get_url(url)

def _get_round_payload(resource: str, year: int, rnd: int) -> dict:
    """Round-scoped GET with a generous limit to avoid paging edge cases."""
    with JolpiClient() as client:
        base = url_for_round(resource, year, rnd)     
        sep = '&' if '?' in base else '?'
        url = f"{base}{sep}limit=200"
        return client.get_url(url)


def _driver_record_from_year(year: int, driver_id: str) -> dict | None:
    """
    Return the driver's object for the season (name, nationality, permanentNumber, etc.),
    matching by driverId.
    """
    data = _load_year_payload("drivers", year)
    drivers = (data.get("MRData", {}).get("DriverTable", {}).get("Drivers", []))
    did = (driver_id or "").lower()
    for d in drivers:
        if (d.get("driverId") or "").lower() == did:
            return d
    return None


def _standing_for_driver(year: int, driver_id: str) -> dict | None:
    """
    Return the driver's championship standing row for the season,
    including fields like 'position', 'points', 'wins', and 'Constructors'.
    """
    data = _load_year_payload("driverstandings", year)
    lists = (data.get("MRData", {}).get("StandingsTable", {}).get("StandingsLists", []))
    if not lists:
        return None
    did = (driver_id or "").lower()
    for row in lists[0].get("DriverStandings", []):
        if (row.get("Driver", {}).get("driverId") or "").lower() == did:
            return row
    return None


def index(request):
    return render(request, 'f1/index.html')


def _fetch_year_races(year: int) -> list[dict]:
    """Return the list of races for a given year using Jolpica/Ergast 'races' endpoint."""
    client = JolpiClient()
    try:
        url = url_for_year('races', year)
        payload = client.get_url(url)
        races = (
            payload
            .get('MRData', {})
            .get('RaceTable', {})
            .get('Races', [])
        )
        return races
    finally:
        client.close()


def _last_completed_round(races: list[dict]) -> int | None:
    """Infer last completed round by comparing race date to today (local server date)."""
    today = date.today()
    past_rounds = []
    for r in races:
        try:
            r_date = date.fromisoformat(r.get('date'))  
            if r_date <= today:
                past_rounds.append(int(r.get('round')))
        except Exception:
            continue
    return max(past_rounds) if past_rounds else None


def schedule(request):
    """Schedule hub
    - Shows dropdown with the last 5 completed races (by date)
    - Shows a link to view the full CURRENT_YEAR schedule
    """
    races = _fetch_year_races(CURRENT_YEAR)
    last_done = _last_completed_round(races)

    last5 = []
    if last_done:
        rounds = [r for r in races if int(r.get('round', 0)) <= last_done]
        rounds_sorted = sorted(rounds, key=lambda r: int(r['round']))
        last5 = rounds_sorted[-5:]

    ctx = {
        'year': CURRENT_YEAR,
        'last5': last5,
    }
    return render(request, 'f1/schedule.html', ctx)


def schedule_year(request, year: int):
    """Full schedule table for a given year, with a 'Sessions' link per race."""
    races = _fetch_year_races(year)
    if not races:
        raise Http404("No schedule found for this year.")

    ctx = {
        'year': year,
        'races': sorted(races, key=lambda r: int(r['round'])),
    }
    return render(request, 'f1/schedule_year.html', ctx)


def schedule_sessions(request, year: int, rnd: int):
    """Show available sessions for a selected round (race weekend)."""
    client = JolpiClient()
    try:
        sessions = []

        def has_data(url: str) -> bool:
            try:
                data = client.get_url(url)
                total = int(data.get('MRData', {}).get('total', 0) or 0)
                return total > 0
            except Exception:
                return False

        # Race results
        if has_data(url_for_round('results', year, rnd)):
            sessions.append({'label': 'Race Results', 'kind': 'race'})

        # Qualifying
        if has_data(url_for_round('qualifying', year, rnd)):
            sessions.append({'label': 'Qualifying', 'kind': 'qualifying'})

        # Sprint
        if has_data(url_for_round('sprint', year, rnd)):
            sessions.append({'label': 'Sprint', 'kind': 'sprint'})

        # Pit Stops
        if has_data(url_for_round('pitstops', year, rnd)):
            sessions.append({'label': 'Pit Stops', 'kind': 'pitstops'})

        ctx = {'year': year, 'round': rnd, 'sessions': sessions}
        return render(request, 'f1/schedule_sessions.html', ctx)
    finally:
        client.close()


def schedule_session_detail(request, year: int, rnd: int, kind: str):
    """Render session data in-app for race/quali/sprint/pitstops/laps."""
    kind = (kind or '').lower()
    kind_map = {
        'race': 'results',
        'results': 'results',
        'qualifying': 'qualifying',
        'quali': 'qualifying',
        'sprint': 'sprint',
        'pitstops': 'pitstops',
    }
    resource = kind_map.get(kind)
    if not resource:
        raise Http404("Unknown session type")

    with JolpiClient() as client:
        url = url_for_round(resource, year, rnd)
        data = client.get_url(url)

    mr = data.get('MRData', {})
    race_table = mr.get('RaceTable', {})
    races = race_table.get('Races', [])
    race = races[0] if races else {}

    context = {
        'year': year,
        'round': rnd,
        'kind': kind,          
        'resource': resource,  
        'race': race,          
        'raw': data,           
    }
    return render(request, 'f1/schedule_session_detail.html', context)


def results_season(request, year: int):
    """
    Show the schedule for <year> up to (and including) the latest completed race.
    Reuses schedule_year.html so the UI matches the Schedule section.
    """
    races = _fetch_year_races(year)
    last_done = _last_completed_round(races)

    if last_done:
        filtered = [r for r in races if int(r.get('round', 0)) <= last_done]
    else:
        filtered = []

    context = {
        'year': year,
        'races': sorted(filtered, key=lambda r: int(r['round'])),

        
        'as_results': True,

        
        'completed_rounds': len(filtered),
        'total_rounds': len(races),
    }
    return render(request, 'f1/schedule_year.html', context)


def standings_drivers(request, year: int):
    """
    Driver standings for <year>.
    Pulls https://api.jolpi.ca/ergast/f1/<year>/driverstandings/
    """
    with JolpiClient() as client:
        url = url_for_year('driverstandings', year)
        data = client.get_url(url)

    lists = (data.get('MRData', {})
                .get('StandingsTable', {})
                .get('StandingsLists', []))
    if not lists:
        raise Http404("Standings not available.")

    standings = lists[0].get('DriverStandings', [])
    rows = []
    for s in standings:
        d = s.get('Driver', {})
        rows.append({
            'pos': s.get('position'),
            'driver': f"{d.get('givenName','')} {d.get('familyName','')}".strip(),
            'code': d.get('code') or d.get('driverId'),
            'constructor': (s.get('Constructors') or [{}])[0].get('name'),
            'points': s.get('points'),
            'wins': s.get('wins'),
        })

    context = {'year': year, 'rows': rows}
    return render(request, 'f1/standings_drivers.html', context)


def standings_constructors(request, year: int):
    """
    Constructor standings for <year>.
    Pulls https://api.jolpi.ca/ergast/f1/<year>/constructorstandings/
    """
    with JolpiClient() as client:
        url = url_for_year('constructorstandings', year)
        data = client.get_url(url)

    lists = (data.get('MRData', {})
                .get('StandingsTable', {})
                .get('StandingsLists', []))
    if not lists:
        raise Http404("Standings not available.")

    standings = lists[0].get('ConstructorStandings', [])
    rows = []
    for s in standings:
        c = s.get('Constructor', {})
        rows.append({
            'pos': s.get('position'),
            'constructor': c.get('name'),
            'points': s.get('points'),
            'wins': s.get('wins'),
        })

    context = {'year': year, 'rows': rows}
    return render(request, 'f1/standings_constructors.html', context)


def results_find(request):
    """
    Handle the small Results dropdown search (GET ?year=YYYY).
    Validates the year and redirects to the overview page for that season.
    """
    year_str = (request.GET.get('year') or '').strip()
    try:
        year = int(year_str)
    except ValueError:
        return redirect('f1:results_season', year=date.today().year)

    current_year = date.today().year
    if not (1950 <= year <= current_year + 1):
        return redirect('f1:results_season', year=current_year)

    return redirect('f1:results_year_hub', year=year)


def results_year_hub(request, year: int):
    """
    Year Results Overview page:
      • Shows a button to that year's schedule (with per-round sessions, like current-year)
      • Shows the FINAL (or current) Driver Standings for that year
      • Shows the FINAL (or current) Constructor Standings for that year
    All on ONE page.
    """
    with JolpiClient() as client:
        drv_url = url_for_year('driverstandings', year)     
        drv_data = client.get_url(drv_url)

    drv_lists = (drv_data.get('MRData', {})
                           .get('StandingsTable', {})
                           .get('StandingsLists', []))
    if not drv_lists:
        raise Http404("No standings available for this season.")
    drv_rows = drv_lists[0].get('DriverStandings', [])

    driver_rows = []
    for s in drv_rows:
        d = s.get('Driver', {})
        driver_rows.append({
            'pos': s.get('position'),
            'driver': f"{d.get('givenName','')} {d.get('familyName','')}".strip(),
            'code': d.get('code') or d.get('driverId'),
            'constructor': (s.get('Constructors') or [{}])[0].get('name'),
            'wins': s.get('wins'),
            'points': s.get('points'),
        })

    with JolpiClient() as client:
        con_url = url_for_year('constructorstandings', year)  
        con_data = client.get_url(con_url)

    con_lists = (con_data.get('MRData', {})
                           .get('StandingsTable', {})
                           .get('StandingsLists', []))
    con_rows = con_lists[0].get('ConstructorStandings', []) if con_lists else []

    constructor_rows = []
    for s in con_rows:
        c = s.get('Constructor', {})
        constructor_rows.append({
            'pos': s.get('position'),
            'constructor': c.get('name'),
            'wins': s.get('wins'),
            'points': s.get('points'),
        })

    standings_round = drv_lists[0].get('round')
    context = {
        'year': year,
        'standings_round': standings_round,  
        'driver_rows': driver_rows,
        'constructor_rows': constructor_rows,
    }
    return render(request, 'f1/results_year_hub.html', context)


def _slug_full_image_name(driver: dict) -> str:
    """
    Build full-size image filename 'lastname-firstname.png' (lowercase; spaces -> hyphens).
    Matches your /static/f1/img/drivers/full/<...>.png files, e.g.:
      norris-lando.png, albon-alex.png, antonelli-kimi-andrea.png
    """
    fam = (driver.get("familyName") or "").strip().lower().replace(" ", "-")
    giv = (driver.get("givenName") or "").strip().lower().replace(" ", "-")
    return f"{fam}-{giv}.png" if fam or giv else "placeholder.png"


def _parse_iso(d: str) -> date | None:
    try:
        return date.fromisoformat(d)
    except Exception:
        return None

_NON_MECH_TERMS = {
    "accident", "collision", "spin", "crash", "contact",
    "disqualified", "excluded", "black flag", "illegal",
    "finished", "lap", "laps", "time penalty", "did not qualify",
    "not classified", "injury", "illness", "withdrew",
}

_MECH_TERMS = {
    "retired", "mechanical", "engine", "power unit", "gearbox",
    "hydraul", "electrical", "suspension", "brake", "brakes",
    "clutch", "driveshaft", "exhaust", "fuel", "oil",
    "overheating", "steering", "battery", "radiator", "turbo",
    "ers", "ignition", "water pressure", "throttle", "wheel",
    "puncture", "tyre", "cooling",
}

def _is_mechanical_dnf_from_status(status: str, position_text: str | None) -> bool:
    """
    Count as mechanical DNF if:
      - positionText == 'R' (retired) OR status includes 'retired'/'mechanical' **AND**
      - status doesn't contain any explicitly non-mechanical words (accident/collision/etc.) **AND**
      - status doesn't indicate a finish ('Finished', '+1 Lap', etc.) or DSQ/excluded
    """
    s = (status or "").strip().lower()
    ptxt = (position_text or "").strip().lower()

    if "finished" in s or "lap" in s or "disqualified" in s or "excluded" in s:
        return False

    if any(term in s for term in _NON_MECH_TERMS):
        return False

    if ptxt == "r":
        return True
    if any(term in s for term in _MECH_TERMS):
        return True

    return False

def _season_races_ordered(year: int) -> list[dict]:
    """All season races, with round(int) and date parsed, sorted by round asc."""
    data = _load_year_payload("races", year)
    races = (data.get("MRData", {}).get("RaceTable", {}).get("Races", []))
    out = []
    for r in races:
        out.append({
            "round": int(r.get("round", 0) or 0),
            "date": _parse_iso(r.get("date")),
            "raceName": r.get("raceName"),
            "Circuit": r.get("Circuit", {}),
            "_raw": r,
        })
    out.sort(key=lambda x: x["round"])
    return out


def _gp_results_for_driver_completed(year: int, driver_id: str) -> list[dict]:
    """
    Use season-wide /<year>/results with pagination to gather *all* races,
    then keep only completed rounds up to today and the specific driver's row.
    """
    today = date.today()
    races = _season_races_ordered(year) 

    data = _load_year_collection("results", year, per_page=200)
    result_races = (data.get("MRData", {}).get("RaceTable", {}).get("Races", []))

    by_round = {int(r.get("round", 0) or 0): r for r in result_races}

    items: list[dict] = []
    for r in races:
        if not r["date"] or r["date"] > today:
            break  
        rr = by_round.get(r["round"])
        if not rr:
            continue
        found = next(
            (res for res in rr.get("Results", []) or []
             if (res.get("Driver", {}).get("driverId") or "").lower() == driver_id.lower()),
            None
        )
        if not found:
            continue
        items.append({
            "round": r["round"],
            "date": r["date"],
            "raceName": r["raceName"],
            "country": r["Circuit"].get("Location", {}).get("country"),
            "circuit": r["Circuit"].get("circuitName"),
            "position": found.get("position"),
            "positionText": found.get("positionText"),
            "grid": found.get("grid"),
            "points": found.get("points"),
            "status": found.get("status"),
            "Time": (found.get("Time") or {}).get("time"),
        })
    return items


def _sprint_results_for_driver_completed(year: int, driver_id: str) -> list[dict]:
    """
    Use season-wide /<year>/sprint with pagination to gather *all* sprints,
    then keep only completed sprints up to today and the specific driver's row.
    """
    today = date.today()
    races = _season_races_ordered(year) 

    data = _load_year_collection("sprint", year, per_page=200)
    sprint_races = (data.get("MRData", {}).get("RaceTable", {}).get("Races", []))

    by_round = {int(r.get("round", 0) or 0): r for r in sprint_races}

    items: list[dict] = []
    for r in races:
        if not r["date"] or r["date"] > today:
            break
        rr = by_round.get(r["round"])
        if not rr:
            continue
        found = next(
            (res for res in rr.get("SprintResults", []) or []
             if (res.get("Driver", {}).get("driverId") or "").lower() == driver_id.lower()),
            None
        )
        if not found:
            continue
        items.append({
            "round": r["round"],
            "date": r["date"],
            "raceName": r["raceName"],
            "position": found.get("position"),
            "positionText": found.get("positionText"),
            "points": found.get("points"),
            "status": found.get("status"),
            "Time": (found.get("Time") or {}).get("time"),
        })
    return items


def driver_detail(request, driver_id: str, year: int | None = None):
    """
    Driver detail page (current season by default).
    """
    season = year or date.today().year

    driver = _driver_record_from_year(season, driver_id)
    if not driver:
        raise Http404("Driver not found for this season.")

    standing = _standing_for_driver(season, driver_id)
    wdc_pos = standing.get("position") if standing else None
    wdc_pts = standing.get("points") if standing else None
    constructor_name = None
    if standing:
        constructors = standing.get("Constructors") or []
        if constructors:
            constructor_name = constructors[0].get("name")

    gp_completed = _gp_results_for_driver_completed(season, driver_id)

    gp_entered = len(gp_completed)
    gp_points = sum(float(r.get("points") or 0.0) for r in gp_completed)
    gp_wins = sum(1 for r in gp_completed if str(r.get("position")) == "1")
    gp_podiums = sum(1 for r in gp_completed if (r.get("position") and int(r["position"]) <= 3))
    gp_poles = sum(1 for r in gp_completed if str(r.get("grid")) == "1")
    gp_top10 = sum(1 for r in gp_completed if (r.get("position") and int(r["position"]) <= 10))
    gp_dnfs = sum(
        1
        for r in gp_completed
        if _is_mechanical_dnf_from_status(str(r.get("status") or ""), r.get("positionText"))
    )

    sp_completed = _sprint_results_for_driver_completed(season, driver_id)
    sp_entered = len(sp_completed)
    sp_points = sum(float(r.get("points") or 0.0) for r in sp_completed)
    sp_wins = sum(1 for r in sp_completed if str(r.get("position")) == "1")
    sp_podiums = sum(1 for r in sp_completed if (r.get("position") and int(r["position"]) <= 3))
    sp_top8 = sum(1 for r in sp_completed if (r.get("position") and int(r["position"]) <= 8))

    last5_gp_src = gp_completed[-5:] if gp_completed else []
    last5_gp = list(reversed([
        {
            "round": r["round"],
            "raceName": r["raceName"],
            "position": r.get("position"),
            "points": r.get("points"),
            "time": r.get("Time"),
            "status": r.get("status"),
        }
        for r in last5_gp_src
    ]))

    full_img = _slug_full_image_name(driver)
    nationality = (driver.get("nationality") or "").lower()

    is_favorite = False
    if request.user.is_authenticated:
        is_favorite = FavoriteDriver.objects.filter(user=request.user, driver_id=driver_id).exists()

    ctx = {
        "year": season,
        "driver": driver,
        "full_img": full_img,
        "nationality": nationality,
        "constructor_name": constructor_name,
        "wdc_pos": wdc_pos,
        "wdc_pts": wdc_pts,

        "gp_entered": gp_entered,
        "gp_points": gp_points,
        "gp_wins": gp_wins,
        "gp_podiums": gp_podiums,
        "gp_poles": gp_poles,
        "gp_top10": gp_top10,
        "gp_dnfs": gp_dnfs,

        "sp_entered": sp_entered,
        "sp_points": sp_points,
        "sp_wins": sp_wins,
        "sp_podiums": sp_podiums,
        "sp_top8": sp_top8,

        "last5_gp": last5_gp,

        "is_favorite": is_favorite,
    }
    return render(request, "f1/driver_detail.html", ctx)


def _load_collection(base_url: str, per_page: int = 200) -> dict:
    """
    Generic pagination-aware loader for any Ergast/Jolpi collection endpoint.
    Returns a merged payload with all pages appended.
    """
    merged: dict | None = None
    offset = 0
    with JolpiClient() as client:
        while True:
            sep = '&' if '?' in base_url else '?'
            url = f"{base_url}{sep}limit={per_page}&offset={offset}"
            page = client.get_url(url)

            if merged is None:
                merged = page
            else:
                mr = page.get("MRData", {})
                if "RaceTable" in mr:
                    merged["MRData"]["RaceTable"]["Races"] += mr.get("RaceTable", {}).get("Races", [])
                elif "DriverTable" in mr:
                    merged["MRData"]["DriverTable"]["Drivers"] += mr.get("DriverTable", {}).get("Drivers", [])
                elif "ConstructorTable" in mr:
                    merged["MRData"]["ConstructorTable"]["Constructors"] += mr.get("ConstructorTable", {}).get("Constructors", [])
                else:
                    merged = page

            mr = page.get("MRData", {})
            total = int(mr.get("total") or 0)
            limit = int(mr.get("limit") or per_page)
            off = int(mr.get("offset") or 0)
            offset = off + limit
            if offset >= total or total == 0:
                break

    return merged or {"MRData": {}}


def _constructor_drivers(year: int, constructor_id: str) -> list[dict]:
    """
    List the two (or more) drivers for a constructor in a given year,
    with basic driver info (name, nationality, permanentNumber, driverId).
    """

    base = f"https://api.jolpi.ca/ergast/f1/{year}/constructors/{constructor_id}/drivers/"
    data = _load_collection(base, per_page=200)
    drivers = (data.get("MRData", {}).get("DriverTable", {}).get("Drivers", []))
    drivers.sort(key=lambda d: (d.get("familyName") or "").lower())

    if str(year) == "2025":
        if constructor_id.lower() == "alpine":
            drivers = [d for d in drivers if (d.get("driverId") or "").lower() in ["gasly", "colapinto"]]

        elif constructor_id.lower() in ["red_bull", "redbull", "red-bull"]:
            drivers = [d for d in drivers if (d.get("driverId") or "").lower() in ["max_verstappen", "tsunoda"]]

    return drivers



def _constructor_results(year: int, constructor_id: str) -> list[dict]:
    """
    Season-wide GP results for a constructor: list of races (with Results array).
    """
    base = f"https://api.jolpi.ca/ergast/f1/{year}/constructors/{constructor_id}/results/"
    data = _load_collection(base, per_page=200)
    return (data.get("MRData", {}).get("RaceTable", {}).get("Races", []))


def _constructor_sprint(year: int, constructor_id: str) -> list[dict]:
    """
    Season-wide Sprint results for a constructor: list of races (with SprintResults array).
    """
    base = f"https://api.jolpi.ca/ergast/f1/{year}/constructors/{constructor_id}/sprint/"
    data = _load_collection(base, per_page=200)
    return (data.get("MRData", {}).get("RaceTable", {}).get("Races", []))


def _constructor_standing(year: int, constructor_id: str) -> dict | None:
    """
    Constructor standings row for the current year (position, points, wins).
    """
    data = _load_year_payload("constructorstandings", year)
    lists = (data.get("MRData", {}).get("StandingsTable", {}).get("StandingsLists", []))
    if not lists:
        return None
    for row in lists[0].get("ConstructorStandings", []):
        if (row.get("Constructor", {}).get("constructorId") or "").lower() == constructor_id.lower():
            return row
    return None


def constructor_detail(request, constructor_id: str, year: int | None = None):
    """
    Constructor detail page (current season by default).
    Layout:
      - Two driver cards (photo, name, number, nationality flag)
      - Big car livery image
      - Team stats: season pos/points, GP stats, Sprint stats
    """
    season = year or date.today().year

    drivers = _constructor_drivers(season, constructor_id)

    driver_cards = []
    for d in drivers[:2]:
        fam = (d.get("familyName") or "").strip().lower().replace(" ", "-")
        giv = (d.get("givenName") or "").strip().lower().replace(" ", "-")
        full_img = f"{fam}-{giv}.png" if (fam or giv) else "placeholder.png"
        driver_cards.append({
            "name": f"{d.get('givenName','')} {d.get('familyName','')}".strip(),
            "number": d.get("permanentNumber") or "—",
            "nationality": (d.get("nationality") or "").lower(),
            "driverId": d.get("driverId"),
            "img": full_img,
        })

    livery_img = f"{constructor_id.replace('_', '-').lower()}.png"

    standing = _constructor_standing(season, constructor_id) or {}
    season_pos = standing.get("position")
    season_pts = standing.get("points")

    races_calendar = _season_races_ordered(season)
    by_round_date = {r["round"]: r["date"] for r in races_calendar}
    today = date.today()

    gp_races = _constructor_results(season, constructor_id)
    gp_entered = 0
    gp_points = 0.0
    gp_wins = 0
    gp_podiums = 0
    gp_poles = 0
    gp_top10 = 0
    gp_dnfs = 0

    for race in gp_races:
        rnd = int(race.get("round", 0) or 0)
        rdate = by_round_date.get(rnd)
        if not rdate or rdate > today:
            continue
        results = race.get("Results", []) or []
        if not results:
            continue
        gp_entered += 1

        for res in results:
            gp_points += float(res.get("points") or 0.0)
            pos = res.get("position")
            grid = res.get("grid")
            pos_text = res.get("positionText")
            status = res.get("status") or ""

            if str(pos) == "1":
                gp_wins += 1
            if pos and int(pos) <= 3:
                gp_podiums += 1
            if str(grid) == "1":
                gp_poles += 1
            if pos and int(pos) <= 10:
                gp_top10 += 1
            if _is_mechanical_dnf_from_status(status, pos_text):
                gp_dnfs += 1

    sp_races = _constructor_sprint(season, constructor_id)
    sp_entered = 0
    sp_points = 0.0
    sp_wins = 0
    sp_podiums = 0
    sp_top8 = 0

    for race in sp_races:
        rnd = int(race.get("round", 0) or 0)
        rdate = by_round_date.get(rnd)
        if not rdate or rdate > today:
            continue
        results = race.get("SprintResults", []) or []
        if not results:
            continue
        sp_entered += 1

        for res in results:
            sp_points += float(res.get("points") or 0.0)
            pos = res.get("position")
            if str(pos) == "1":
                sp_wins += 1
            if pos and int(pos) <= 3:
                sp_podiums += 1
            if pos and int(pos) <= 8:
                sp_top8 += 1

    is_favorite = False
    if request.user.is_authenticated:
        is_favorite = FavoriteConstructor.objects.filter(
            user=request.user, constructor_id=constructor_id
        ).exists()

    ctx = {
        "year": season,
        "constructor_id": constructor_id,
        "driver_cards": driver_cards,
        "livery_img": livery_img,

        "season_pos": season_pos,
        "season_pts": season_pts,

        "gp_entered": gp_entered,
        "gp_points": gp_points,
        "gp_wins": gp_wins,
        "gp_podiums": gp_podiums,
        "gp_poles": gp_poles,
        "gp_top10": gp_top10,
        "gp_dnfs": gp_dnfs,

        "sp_entered": sp_entered,
        "sp_points": sp_points,
        "sp_wins": sp_wins,
        "sp_podiums": sp_podiums,
        "sp_top8": sp_top8,

        "is_favorite": is_favorite,
    }
    return render(request, "f1/constructor_detail.html", ctx)



@require_POST
@login_required
def favorite_driver_toggle(request, driver_id):
    obj, created = FavoriteDriver.objects.get_or_create(user=request.user, driver_id=driver_id)
    if created:
        messages.success(request, "Added driver to your favorites.")
    else:
        obj.delete()
        messages.info(request, "Removed driver from your favorites.")
    return redirect("f1:driver_detail", driver_id=driver_id)

@require_POST
@login_required
def favorite_constructor_toggle(request, constructor_id):
    obj, created = FavoriteConstructor.objects.get_or_create(user=request.user, constructor_id=constructor_id)
    if created:
        messages.success(request, "Added team to your favorites.")
    else:
        obj.delete()
        messages.info(request, "Removed team from your favorites.")
    return redirect("f1:constructor_detail", constructor_id=constructor_id)


def signup(request):
    """
    Sign up with a custom template located at templates/f1/signup.html.
    On success, the user is logged in and redirected to My Hub.
    """
    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Welcome! Your account has been created.")
            return redirect("f1:my_hub")
    else:
        form = SignUpForm()

    return render(request, "f1/signup.html", {"form": form})


@login_required
def my_hub(request):
    fav_drivers = list(FavoriteDriver.objects.filter(user=request.user).order_by("-added_at"))
    fav_teams   = list(FavoriteConstructor.objects.filter(user=request.user).order_by("-added_at"))

    limit   = getattr(settings, "NEWS_RSS_LIMIT", 8)
    timeout = getattr(settings, "NEWS_RSS_TIMEOUT", 5.0)
    ttl     = getattr(settings, "NEWS_RSS_TTL", 1800)

    for fd in fav_drivers:
        given  = getattr(fd, "given_name", "")
        family = getattr(fd, "family_name", "")
        cons   = getattr(fd, "constructor_name", None)
        q = driver_query(given, family, cons)
        fd.news = fetch_news_rss(q, limit=limit, timeout=timeout, ttl=ttl)

    for ft in fav_teams:
        name = getattr(ft, "constructor_name", ft.constructor_id)
        q = team_query(name)
        ft.news = fetch_news_rss(q, limit=limit, timeout=timeout, ttl=ttl)

    global_news = fetch_news_rss("Formula 1 OR F1", limit=10, timeout=timeout, ttl=ttl)

    context = {
        "fav_drivers": fav_drivers,
        "fav_teams": fav_teams,
        "global_news": global_news,
        "news_enabled": True,
        "news_provider": "Google News (RSS)",
    }
    return render(request, "f1/my_hub.html", context)