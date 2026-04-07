"""Weekly discovery of new padel clubs on Playtomic and kluby.org.

Strategy:
  - Playtomic: query /v1/tenants for major Polish cities (ACTIVE only),
    filter to PADEL sport, dedupe by tenant_id.
  - kluby.org: scrape the main page for candidate club slugs, then probe
    each with /grafik?dyscyplina=4 — a padel club is one whose grafik has
    at least one court column.
  - Compare discovered results against the static CLUBS registry (matched
    by playtomic_id or slug) and return only the new ones.

New clubs are written to the discovered_clubs DB table and merged into
the live CLUBS registry so the existing scrapers pick them up on the
next scheduled run — no code deploy required.
"""

import logging
import re
import time
from datetime import datetime, timedelta

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Major Polish cities — covers the country with overlapping 80km radii.
POLISH_CITIES = [
    ("Warszawa", 52.2297, 21.0122),
    ("Krakow", 50.0614, 19.9366),
    ("Lodz", 51.7592, 19.4560),
    ("Wroclaw", 51.1079, 17.0385),
    ("Poznan", 52.4064, 16.9252),
    ("Gdansk", 54.3520, 18.6466),
    ("Szczecin", 53.4285, 14.5528),
    ("Bydgoszcz", 53.1235, 18.0084),
    ("Lublin", 51.2465, 22.5684),
    ("Bialystok", 53.1325, 23.1688),
    ("Katowice", 50.2649, 19.0238),
    ("Torun", 53.0137, 18.5984),
    ("Rzeszow", 50.0413, 21.9990),
    ("Kielce", 50.8661, 20.6286),
    ("Olsztyn", 53.7784, 20.4801),
]

PLAYTOMIC_API = "https://api.playtomic.io/v1/tenants"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Accept-Language": "pl-PL,pl;q=0.9,en;q=0.8",
}

# kluby.org system/non-club paths — skip these when scanning slugs.
# Other sport categories (tennis, squash, etc.) are filtered later by
# probing the grafik with dyscyplina=4 (padel).
KLUBY_SYSTEM_PATHS = {
    "tenis", "padel", "kluby", "gracze", "rankingi", "o-nas", "regulamin",
    "kontakt", "aplikacja-mobilna", "trenerzy", "sparingpartnerzy",
    "o-kluby-org", "licz-si-rankingu", "nauka", "obozy", "boiska",
    "badminton", "bilard", "beach-tennis", "squash", "tenis-stolowy",
    "fitness", "golf", "americano", "challenge", "cykl", "liga",
    "turnieje", "aktywnosci", "rozgrywki", "padlowe",
}


def _slugify(text):
    """Create a kluby.org-style slug from a name."""
    s = text.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")[:40]


def discover_playtomic_clubs():
    """Query Playtomic tenants API across major Polish cities.

    Returns dict keyed by tenant_id:
        {tenant_id: {"name", "city", "slug", "courts"}}
    """
    seen = {}
    for city_name, lat, lon in POLISH_CITIES:
        try:
            r = requests.get(
                PLAYTOMIC_API,
                params={
                    "sport_id": "PADEL",
                    "coordinate": f"{lat},{lon}",
                    "radius": 80000,  # 80 km
                    "size": 50,
                    "playtomic_status": "ACTIVE",
                },
                headers=HEADERS,
                timeout=30,
            )
            r.raise_for_status()
            tenants = r.json() or []
        except Exception as e:
            logger.warning(f"Playtomic discovery failed for {city_name}: {e}")
            continue

        for t in tenants:
            tid = t.get("tenant_id")
            if not tid or tid in seen:
                continue
            if "PADEL" not in (t.get("sport_ids") or []):
                continue
            name = (t.get("tenant_name") or "").strip()
            if not name or "test" in name.lower():
                continue
            if (t.get("address") or {}).get("country_code") not in (None, "PL"):
                continue
            resources = t.get("resources") or []
            padel_courts = sum(
                1
                for rsrc in resources
                if rsrc.get("sport_id") == "PADEL" and rsrc.get("is_active", True)
            )
            addr = t.get("address") or {}
            seen[tid] = {
                "name": name,
                "city": addr.get("city") or city_name,
                "slug": (t.get("slug") or "").strip(),
                "courts": padel_courts,
            }
        time.sleep(0.5)

    logger.info(f"Playtomic discovery: found {len(seen)} active tenants")
    return seen


def discover_kluby_org_clubs():
    """Scrape kluby.org main page for club slugs, probe each for padel courts.

    Returns dict keyed by slug:
        {slug: {"name", "courts"}}
    """
    try:
        r = requests.get("https://kluby.org/", headers=HEADERS, timeout=30)
        r.raise_for_status()
    except Exception as e:
        logger.warning(f"kluby.org main page fetch failed: {e}")
        return {}

    hrefs = set(re.findall(r'href="(/[a-z][a-z0-9-]{3,40})"', r.text))
    candidates = sorted(
        h.lstrip("/") for h in hrefs if h.lstrip("/") not in KLUBY_SYSTEM_PATHS
    )
    logger.info(f"kluby.org discovery: probing {len(candidates)} candidate slugs")

    probe_date = (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d")
    found = {}
    for slug in candidates:
        try:
            url = f"https://kluby.org/{slug}/grafik?dyscyplina=4&data_grafiku={probe_date}"
            resp = requests.get(url, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                continue
            soup = BeautifulSoup(resp.text, "html.parser")
            tbl = soup.find("table", id="grafik")
            if not tbl:
                continue
            rows = tbl.find_all("tr")
            if not rows:
                continue
            ths = rows[0].find_all("th")
            courts = max(0, len(ths) - 1)
            if courts <= 0:
                continue
            h1 = soup.find("h1")
            name = h1.get_text(strip=True) if h1 else ""
            if not name:
                title = soup.find("title")
                name = (
                    title.get_text(strip=True).split("|")[0].strip()
                    if title
                    else slug
                )
            found[slug] = {"name": name or slug, "courts": courts}
        except Exception as e:
            logger.debug(f"Probe failed for {slug}: {e}")
        time.sleep(0.3)

    logger.info(f"kluby.org discovery: found {len(found)} padel clubs")
    return found


def discover_new_clubs(existing_clubs):
    """Run both discovery sources and return clubs not in existing_clubs.

    Matching rules:
      - Playtomic: match by tenant_id (UUID is authoritative).
      - kluby.org: match by slug.
      - If a discovered Playtomic tenant_id would land on a slug already in
        use, append a numeric suffix to the slug.

    Returns a list of dicts shaped for the discovered_clubs table.
    """
    existing_tenant_ids = {
        c.get("playtomic_id")
        for c in existing_clubs.values()
        if c.get("playtomic_id")
    }
    existing_slugs = set(existing_clubs.keys())

    new_clubs = []

    for tid, info in discover_playtomic_clubs().items():
        if tid in existing_tenant_ids:
            continue
        base_slug = info["slug"] or _slugify(info["name"])
        if not base_slug:
            continue
        slug = base_slug
        suffix = 2
        while slug in existing_slugs:
            slug = f"{base_slug}-{suffix}"
            suffix += 1
        existing_slugs.add(slug)
        new_clubs.append({
            "slug": slug,
            "name": info["name"],
            "city": info["city"],
            "courts": info["courts"],
            "booking_system": "playtomic",
            "playtomic_id": tid,
            "playtomic_slug": info["slug"] or None,
        })

    for slug, info in discover_kluby_org_clubs().items():
        if slug in existing_slugs:
            continue
        existing_slugs.add(slug)
        new_clubs.append({
            "slug": slug,
            "name": info["name"],
            "city": "",
            "courts": info["courts"],
            "booking_system": "kluby_org",
            "playtomic_id": None,
            "playtomic_slug": None,
        })

    logger.info(f"Discovery total new clubs: {len(new_clubs)}")
    return new_clubs
