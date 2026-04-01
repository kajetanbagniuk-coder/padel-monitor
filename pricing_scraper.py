"""
Scrape per-club pricing from kluby.org "o klubie" pages.

Each club page has a pricing section with Bootstrap tabs:
  Level 1: tab_dys_{sportCode} (4 = Padel)
  Level 2: tab_cen_{sportCode}_{id} with data-sort="order_type_name"
    type 001 = standard pricing, type 006 = fixed/recurring

Pricing tables have 3 columns: day-range | time-range | price (PLN/H).
Day-range cells use rowspan to group multiple time slots.
"""

import re
import json
import time
import logging
import requests
from bs4 import BeautifulSoup

from database import save_club_pricing
from pricing import clear_pricing_cache
from clubs import CLUBS

logger = logging.getLogger(__name__)

BASE_URL = "https://kluby.org"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7",
}


def fetch_club_page(slug):
    """Fetch the club's main page (contains pricing section)."""
    url = f"{BASE_URL}/{slug}"
    try:
        session = requests.Session()
        session.headers.update(HEADERS)
        resp = session.get(url, timeout=30)
        resp.raise_for_status()
        return resp.text
    except requests.RequestException as e:
        logger.error(f"Failed to fetch page for {slug}: {e}")
        return None


def _find_standard_tier_in_panel(soup, panel):
    """Find the best standard pricing tab panel within a discipline panel.

    Looks at Level 2 tabs, preferring data-sort type 001 (standard).
    The tab href may point to tab_cen of ANY discipline number (some clubs
    file padel pricing under discipline 0 instead of 4).
    """
    tier_tabs = panel.find("ul", class_="nav")
    if tier_tabs:
        best_li = None
        for li in tier_tabs.find_all("li"):
            sort_val = li.get("data-sort", "")
            parts = sort_val.split("_")
            # Prefer type 001 (standard one-time pricing)
            if len(parts) >= 2 and parts[1] == "001":
                best_li = li
                break
        # Fallback: just use the first/active tab
        if not best_li:
            best_li = tier_tabs.find("li")
        if best_li:
            a_tag = best_li.find("a")
            if a_tag and a_tag.get("href", "").startswith("#tab_cen_"):
                tab_id = a_tag["href"].lstrip("#")
                # Search entire page — the tab_cen div may be outside the panel
                result = soup.find("div", id=tab_id)
                if result:
                    return result

    # Fallback: find any tab_cen_* panel directly inside
    result = panel.find("div", id=re.compile(r"^tab_cen_"))
    return result


def find_pricing_section(soup):
    """Find the padel standard pricing tab panel from the page.

    Returns the <div> tab panel for the first standard padel pricing tier,
    or None if not found.
    """
    # Strategy 1: Find tab_dys_4 (padel discipline) and get standard tier inside
    padel_panel = soup.find("div", id="tab_dys_4")
    if padel_panel:
        result = _find_standard_tier_in_panel(soup, padel_panel)
        if result:
            return result

    # Strategy 2: Find any tab_cen_4_* panel on the page
    panel = soup.find("div", id=re.compile(r"^tab_cen_4_"))
    if panel:
        return panel

    # Strategy 3: Some clubs file padel pricing under discipline 0 ("Pozostale").
    # Search ALL tab_cen_* panels for one whose table header contains "padel".
    for panel in soup.find_all("div", id=re.compile(r"^tab_cen_")):
        table = panel.find("table")
        if not table:
            continue
        header_row = table.find("tr")
        if header_row:
            h3 = header_row.find("h3")
            if h3 and "padel" in h3.get_text(strip=True).lower():
                return panel

    return None


def _strip_polish(text):
    """Normalize Polish diacritical characters to ASCII equivalents."""
    replacements = {
        'ą': 'a', 'ć': 'c', 'ę': 'e', 'ł': 'l', 'ń': 'n',
        'ó': 'o', 'ś': 's', 'ź': 'z', 'ż': 'z',
    }
    for pl_char, ascii_char in replacements.items():
        text = text.replace(pl_char, ascii_char)
    return text


def _classify_day_type(text):
    """Classify a day-range text into 'weekday', 'weekend', 'holiday', or 'all'."""
    t = _strip_polish(text.lower().strip())

    # Use word boundary-like checks with full words to avoid substring traps
    # ("poniedzialek" contains "niedz" which could false-match "niedziela")
    has_poniedzialek = "poniedzial" in t or t.startswith("pon")
    has_piatek = "piatek" in t or "piat" in t or " pt" in t or t.endswith("pt.")
    has_sobota = "sobota" in t or "sob" in t
    has_niedziela = "niedziela" in t or "niedz" in t and "poniedzial" not in t
    has_swieta = "swieta" in t or "swiet" in t

    if has_swieta and has_sobota:
        return "weekend"  # "Sobota - Święta" means weekend+holidays = weekend rate
    if has_swieta:
        return "holiday"
    if has_sobota and has_niedziela and not has_poniedzialek:
        return "weekend"
    if has_poniedzialek and has_piatek and not has_niedziela:
        return "weekday"
    if has_poniedzialek and has_niedziela:
        return "all"
    if has_sobota and not has_poniedzialek:
        return "weekend"
    if has_poniedzialek or has_piatek:
        return "weekday"
    return "weekday"  # default


def _parse_time_range(text):
    """Parse a time-range text into (start_hour, start_min, end_hour, end_min).

    Handles formats:
      '06:00 - 16:00' -> (6, 0, 16, 0)
      'od 16:00'      -> (16, 0, 23, 59)
      'do 16:00'      -> (0, 0, 16, 0)
      'od 22:00'      -> (22, 0, 23, 59)
      'caly dzien'    -> (0, 0, 23, 59)
    """
    t = text.lower().strip()

    if "caly" in t or "cały" in t:
        return (0, 0, 23, 59)

    # Explicit range: HH:MM - HH:MM
    m = re.search(r'(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})', t)
    if m:
        return (int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4)))

    # "od HH:MM" (from)
    m = re.search(r'od\s+(\d{1,2}):(\d{2})', t)
    if m:
        return (int(m.group(1)), int(m.group(2)), 23, 59)

    # "do HH:MM" (until)
    m = re.search(r'do\s+(\d{1,2}):(\d{2})', t)
    if m:
        return (0, 0, int(m.group(1)), int(m.group(2)))

    # Single time HH:MM (treat as "from")
    m = re.search(r'(\d{1,2}):(\d{2})', t)
    if m:
        return (int(m.group(1)), int(m.group(2)), 23, 59)

    return None


def _parse_price(text):
    """Extract price per hour from text like '120,00 PLN/H' or '140 PLN'."""
    t = text.strip()
    # Match: number with optional comma-decimal, followed by PLN
    m = re.search(r'(\d+)[,.]?(\d*)\s*PLN', t, re.IGNORECASE)
    if m:
        integer_part = m.group(1)
        decimal_part = m.group(2) if m.group(2) else "0"
        return float(f"{integer_part}.{decimal_part}")
    return None


def parse_pricing_rules(section):
    """Parse a pricing tab panel into a list of normalized rules.

    Each rule: {day_type, start_hour, start_min, end_hour, end_min, price_per_hour}
    """
    # Check for empty pricing
    alert = section.find("div", class_="alert")
    if alert and "brak" in alert.get_text(strip=True).lower():
        return []

    table = section.find("table")
    if not table:
        return []

    rows = table.find_all("tr")
    rules = []
    current_day_type = "weekday"

    for row in rows:
        cells = row.find_all("td")
        if not cells:
            continue

        # Skip header row (colspan=3 with h3)
        if cells[0].get("colspan"):
            continue

        # Determine if this row has a day-range cell (with rowspan)
        if len(cells) == 3:
            # First cell is day-range
            day_text = cells[0].get_text(strip=True)
            current_day_type = _classify_day_type(day_text)
            time_text = cells[1].get_text(strip=True)
            price_text = cells[2].get_text(strip=True)
        elif len(cells) == 2:
            # Continuation row (day-range cell is rowspan'd from above)
            time_text = cells[0].get_text(strip=True)
            price_text = cells[1].get_text(strip=True)
        else:
            continue

        time_range = _parse_time_range(time_text)
        price = _parse_price(price_text)

        if time_range and price is not None:
            rules.append({
                "day_type": current_day_type,
                "start_hour": time_range[0],
                "start_min": time_range[1],
                "end_hour": time_range[2],
                "end_min": time_range[3],
                "price_per_hour": price,
            })

    return rules


def scrape_club_pricing(slug):
    """Scrape pricing for a single club.

    Returns dict: {status, rules, notes, raw_html}
    """
    html = fetch_club_page(slug)
    if not html:
        return {"status": "not_found", "rules": [], "notes": "Failed to fetch page", "raw_html": None}

    soup = BeautifulSoup(html, "html.parser")
    section = find_pricing_section(soup)

    if not section:
        return {"status": "not_found", "rules": [], "notes": "No padel pricing section found", "raw_html": None}

    raw_html = str(section)

    try:
        rules = parse_pricing_rules(section)
    except Exception as e:
        logger.error(f"Parse error for {slug}: {e}")
        return {"status": "parse_error", "rules": [], "notes": str(e), "raw_html": raw_html}

    if not rules:
        return {"status": "not_found", "rules": [], "notes": "No pricing rules parsed", "raw_html": raw_html}

    status = "ok"
    notes = f"{len(rules)} rules parsed"
    logger.info(f"Scraped pricing for {slug}: {notes}")

    # Save to DB and invalidate cache so next booking scrape uses new prices
    save_club_pricing(slug, json.dumps(rules), raw_html, status, notes)
    clear_pricing_cache(slug)

    return {"status": status, "rules": rules, "notes": notes, "raw_html": raw_html}


def scrape_all_pricing():
    """Scrape pricing for all 74 clubs with rate limiting.

    Returns summary dict: {ok: int, not_found: int, parse_error: int, details: list}
    """
    summary = {"ok": 0, "not_found": 0, "parse_error": 0, "details": []}

    for i, slug in enumerate(CLUBS):
        logger.info(f"Scraping pricing {i+1}/{len(CLUBS)}: {slug}")
        result = scrape_club_pricing(slug)
        summary[result["status"]] = summary.get(result["status"], 0) + 1
        summary["details"].append({"slug": slug, "status": result["status"], "notes": result["notes"]})

        # Save failures to DB too so we track status
        if result["status"] != "ok":
            save_club_pricing(slug, "[]", result.get("raw_html"), result["status"], result["notes"])
            clear_pricing_cache(slug)

        # Rate limit: 1 second between requests
        if i < len(CLUBS) - 1:
            time.sleep(1)

    logger.info(f"Pricing scrape complete: {summary['ok']} ok, {summary['not_found']} not found, {summary['parse_error']} errors")
    return summary
