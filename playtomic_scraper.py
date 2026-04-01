"""
Scraper for padel booking schedules from Playtomic.

Uses the Playtomic API to get availability and calculate income.
Available slots are returned by the API; missing hours = booked.
"""

import requests
import json
import logging
import time
from datetime import datetime

from database import save_scrape, save_daily_snapshot

logger = logging.getLogger(__name__)

API_BASE = "https://api.playtomic.io/v1"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
}

# Cache tenant info to avoid repeated API calls
_tenant_cache = {}


def get_tenant_info(tenant_id):
    """Get full tenant info including resources and opening hours."""
    if tenant_id in _tenant_cache:
        return _tenant_cache[tenant_id]
    url = f"{API_BASE}/tenants/{tenant_id}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        _tenant_cache[tenant_id] = data
        return data
    except Exception as e:
        logger.error(f"Failed to get tenant info for {tenant_id}: {e}")
        return None


def get_availability(tenant_id, date_str):
    """Get available slots for a tenant on a given date."""
    url = f"{API_BASE}/availability"
    params = {
        "user_id": "me",
        "tenant_id": tenant_id,
        "sport_id": "PADEL",
        "local_start_min": f"{date_str}T00:00:00",
        "local_start_max": f"{date_str}T23:59:59",
    }
    try:
        resp = requests.get(url, headers=HEADERS, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.error(f"Failed to get availability for {tenant_id} on {date_str}: {e}")
        return None


def parse_opening_hours(tenant_info, date_str):
    """Get opening/closing hour integers for a specific date."""
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    day_name = dt.strftime("%A").upper()
    hours = tenant_info.get("opening_hours", {})
    day_hours = hours.get(day_name, hours.get("MONDAY", {"opening_time": "06:00", "closing_time": "23:00"}))
    open_h = int(day_hours["opening_time"].split(":")[0])
    close_h = int(day_hours["closing_time"].split(":")[0])
    return open_h, close_h


def generate_hourly_slots(open_h, close_h):
    """Generate all possible hourly start times between open and close."""
    if close_h <= open_h:
        # Closes after midnight (e.g., 06:00-02:00)
        hours = list(range(open_h, 24)) + list(range(0, close_h))
    else:
        hours = list(range(open_h, close_h))
    return hours


def scrape_playtomic_date(date_str, club_slug, clubs_dict=None):
    """
    Scrape Playtomic availability for a given date and club.
    Returns summary dict compatible with kluby.org scraper output.
    """
    if clubs_dict is None:
        from clubs import CLUBS
        clubs_dict = CLUBS
    club = clubs_dict.get(club_slug)
    if not club or not club.get("playtomic_id"):
        logger.error(f"No Playtomic ID for club: {club_slug}")
        return None

    tenant_id = club["playtomic_id"]

    # Get tenant info for opening hours and resource names
    tenant_info = get_tenant_info(tenant_id)
    if not tenant_info:
        return None

    # Get availability
    availability = get_availability(tenant_id, date_str)
    if availability is None:
        return None

    # Parse opening hours and generate schedule
    open_h, close_h = parse_opening_hours(tenant_info, date_str)
    schedule_hours = generate_hourly_slots(open_h, close_h)

    # Build resource map: resource_id -> name (only active PADEL courts)
    resource_map = {}
    for r in tenant_info.get("resources", []):
        if r.get("sport_id") == "PADEL" and r.get("is_active", True):
            resource_map[r["resource_id"]] = r["name"].strip()

    if not resource_map:
        logger.warning(f"No active padel courts for {club_slug}")
        return None

    # Build availability map: resource_id -> set of available hour ints
    # Also track prices: resource_id -> {hour: price_per_hour}
    avail_hours = {}
    avail_prices = {}
    for entry in availability:
        rid = entry["resource_id"]
        if rid not in resource_map:
            continue
        avail_hours.setdefault(rid, set())
        avail_prices.setdefault(rid, {})
        for slot in entry.get("slots", []):
            start_h = int(slot["start_time"].split(":")[0])
            start_m = int(slot["start_time"].split(":")[1])
            duration = slot["duration"]
            price_str = slot.get("price", "0 PLN")
            price = float(price_str.replace(",", ".").split()[0])
            hourly_price = round(price / (duration / 60), 2)

            # Mark the starting hour as available
            avail_hours[rid].add(start_h)
            # Prefer 60-min price as it's the most accurate hourly rate
            if start_h not in avail_prices[rid] or duration == 60:
                avail_prices[rid][start_h] = hourly_price

            # For longer slots, also mark subsequent hours as available
            if start_m == 0 and duration >= 120:
                for extra in range(1, duration // 60):
                    extra_h = (start_h + extra) % 24
                    avail_hours[rid].add(extra_h)

    # Calculate bookings per court
    slots = []
    total_income = 0.0
    total_booked = 0
    courts_summary = {}

    for rid, court_name in resource_map.items():
        courts_summary[court_name] = {"booked": 0, "available": 0, "income": 0.0}
        court_avail = avail_hours.get(rid, set())
        court_prices = avail_prices.get(rid, {})

        # Build a default price from available slots for this court
        all_prices = list(court_prices.values())
        default_price = sum(all_prices) / len(all_prices) if all_prices else 150.0

        for hour in schedule_hours:
            hour_str = f"{hour:02d}:00"
            next_h = (hour + 1) % 24
            end_str = f"{next_h:02d}:00"

            if hour in court_avail:
                is_booked = False
                price = 0.0
                courts_summary[court_name]["available"] += 1
            else:
                is_booked = True
                # Estimate price from nearby available slots
                price = default_price
                for offset in range(0, 4):
                    for direction in [offset, -offset]:
                        check_h = (hour + direction) % 24
                        if check_h in court_prices:
                            price = court_prices[check_h]
                            break
                    else:
                        continue
                    break

                total_booked += 1
                total_income += price
                courts_summary[court_name]["booked"] += 1
                courts_summary[court_name]["income"] += price

            slots.append({
                "court": court_name,
                "start": hour_str,
                "end": end_str,
                "booked": is_booked,
                "label": "Booked" if is_booked else "",
                "income": price,
            })

    if not slots:
        logger.warning(f"No slots parsed for Playtomic {club_slug} on {date_str}")
        return None

    # Save to database (same tables as kluby.org scraper)
    scrape_id = save_scrape(date_str, slots, club_slug)
    save_daily_snapshot(date_str, total_booked, total_income, json.dumps(courts_summary), club_slug)

    logger.info(f"Scraped Playtomic {club_slug} {date_str}: {total_booked} booked, {total_income:.2f} PLN")

    return {
        "date": date_str,
        "club": club_slug,
        "total_booked": total_booked,
        "total_income": total_income,
        "courts": courts_summary,
        "slot_count": len(slots),
        "scrape_id": scrape_id,
    }
