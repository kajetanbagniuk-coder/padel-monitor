"""
Scraper for padel booking schedules from kluby.org.

Supports multiple clubs. Table structure is the same across all clubs:
- Row 0: header with <th> (empty + court names)
- Rows 1+: time slots with <td> (time + court cells)
- Booked cells have class "active"
- Available cells have "Rezerwuj" link
- Empty/past cells have no text
- Multi-slot bookings use rowspan
"""

import requests
from bs4 import BeautifulSoup
import json
import logging

from pricing import get_slot_price
from database import save_scrape, save_daily_snapshot

logger = logging.getLogger(__name__)

BASE_URL = "https://kluby.org"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7",
}


def get_slot_end(start):
    """Given '06:00' return '06:30', given '22:30' return '23:00'."""
    h, m = map(int, start.split(":"))
    if m == 0:
        return f"{h:02d}:30"
    else:
        return f"{h + 1:02d}:00"


def scrape_date(date_str, club_slug="loba-padel"):
    """
    Scrape the booking schedule for a given date and club.
    Returns summary dict or None on failure.
    """
    grafik_url = f"{BASE_URL}/{club_slug}/grafik"
    url = f"{grafik_url}?data_grafiku={date_str}&dyscyplina=4&strona=0"
    logger.info(f"Scraping {club_slug} for {date_str}")

    try:
        session = requests.Session()
        session.headers.update(HEADERS)
        session.headers["Referer"] = grafik_url
        session.get(grafik_url, timeout=15)
        resp = session.get(url, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"Failed to fetch {club_slug}: {e}")
        return None

    soup = BeautifulSoup(resp.text, "html.parser")
    table = soup.find("table", id="grafik")
    if not table:
        logger.error(f"No table#grafik for {club_slug}")
        return None

    rows = table.find_all("tr")
    if len(rows) < 2:
        logger.error(f"Table too few rows for {club_slug}")
        return None

    # Parse header to get court count and names
    header_ths = rows[0].find_all("th")
    num_courts = len(header_ths) - 1  # first th is empty (time column)
    if num_courts < 1:
        logger.error(f"No courts found in header for {club_slug}")
        return None

    # Extract clean court names from headers
    court_names = []
    for th in header_ths[1:]:
        # The th text is messy (repeated names). Get first meaningful text node.
        name = th.get_text(strip=True)
        # Take first occurrence before repetition (e.g. "Padel 1PadelPadel 1P" -> "Padel 1")
        # Find the pattern: look for where text starts repeating
        for length in range(3, len(name) // 2 + 1):
            candidate = name[:length]
            if name[length:].startswith(candidate[:3]):
                name = candidate.rstrip()
                break
        court_names.append(name)

    num_cols = num_courts + 1
    data_rows = [r for r in rows if r.find("td")]
    num_rows = len(data_rows)

    # Build grid[row][col] to handle rowspan
    grid = [[None] * num_cols for _ in range(num_rows)]

    for row_idx, row in enumerate(data_rows):
        tds = row.find_all("td")
        td_ptr = 0
        for col_idx in range(num_cols):
            if grid[row_idx][col_idx] is not None:
                continue
            if td_ptr >= len(tds):
                break
            td = tds[td_ptr]
            rowspan = int(td.get("rowspan", 1))
            classes = td.get("class", [])
            text = td.get_text(strip=True)
            # A cell is available only if it has "Rezerwuj" link.
            # Past/closed slots have "bg-gray" class with no booking content.
            # Everything else (active, kolor, or any future class) = booked.
            is_available = "Rezerwuj" in text
            is_empty = "bg-gray" in classes or not text
            is_booked = not is_available and not is_empty
            label = text if is_booked else ""

            cell = (is_booked, label, text)
            for rs in range(rowspan):
                if row_idx + rs < num_rows:
                    grid[row_idx + rs][col_idx] = cell
            td_ptr += 1

    # Extract time from column 0
    time_by_row = {}
    for row_idx in range(num_rows):
        cell = grid[row_idx][0]
        if cell:
            text = cell[2]
            if ":" in text and len(text) <= 5:
                parts = text.split(":")
                time_by_row[row_idx] = f"{int(parts[0]):02d}:{parts[1]}"

    # Extract bookings
    slots = []
    total_income = 0.0
    total_booked = 0
    courts_summary = {}

    for court_idx in range(num_courts):
        col_idx = court_idx + 1
        court_name = court_names[court_idx]
        courts_summary[court_name] = {"booked": 0, "available": 0, "income": 0.0}

        for row_idx in range(num_rows):
            slot_time = time_by_row.get(row_idx)
            if not slot_time:
                continue
            cell = grid[row_idx][col_idx]
            if cell is None:
                continue

            is_booked = cell[0]
            label = cell[1]
            slot_end = get_slot_end(slot_time)
            price = get_slot_price(date_str, slot_time, club_slug) if is_booked else 0.0

            slots.append({
                "court": court_name,
                "start": slot_time,
                "end": slot_end,
                "booked": is_booked,
                "label": label,
                "income": price,
            })

            if is_booked:
                total_booked += 1
                total_income += price
                courts_summary[court_name]["booked"] += 1
                courts_summary[court_name]["income"] += price
            else:
                courts_summary[court_name]["available"] += 1

    if not slots:
        logger.warning(f"No slots parsed for {club_slug} on {date_str}")
        return None

    scrape_id = save_scrape(date_str, slots, club_slug)
    save_daily_snapshot(date_str, total_booked, total_income, json.dumps(courts_summary), club_slug)

    logger.info(f"Scraped {club_slug} {date_str}: {total_booked} booked, {total_income:.2f} PLN")

    return {
        "date": date_str,
        "club": club_slug,
        "total_booked": total_booked,
        "total_income": total_income,
        "courts": courts_summary,
        "slot_count": len(slots),
        "scrape_id": scrape_id,
    }
