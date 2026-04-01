"""
Scraper for padel booking schedules from Playtomic.

Key difference from kluby.org: Playtomic hides past slots behind a moving
time line. Past slots are NOT necessarily booked — they're just hidden.

Strategy:
  - Scrape every hour at :45 (e.g., 10:45, 11:45, ...)
  - At XX:45, the XX:00 slot is about to end — its fate is sealed
  - Future slots NOT in the available list = booked (grey squares)
  - Past slots = already captured by earlier :45 observations
  - Build full daily picture from accumulated hourly observations
"""

import requests
import json
import logging
import time
from datetime import datetime

from database import (save_playtomic_observations, get_playtomic_daily_summary,
                      save_daily_snapshot)

logger = logging.getLogger(__name__)

API_BASE = "https://api.playtomic.io/v1"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
}

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
        return list(range(open_h, 24)) + list(range(0, close_h))
    return list(range(open_h, close_h))


def scrape_playtomic_hourly(date_str, club_slug, clubs_dict=None):
    """
    Hourly Playtomic scrape — called at XX:45.

    Only records observations for the CURRENT hour and FUTURE hours.
    Past hours keep their earlier observations untouched.
    After recording, rebuilds the daily snapshot from all observations.
    """
    if clubs_dict is None:
        from clubs import CLUBS
        clubs_dict = CLUBS
    club = clubs_dict.get(club_slug)
    if not club or not club.get("playtomic_id"):
        logger.error(f"No Playtomic ID for club: {club_slug}")
        return None

    tenant_id = club["playtomic_id"]

    tenant_info = get_tenant_info(tenant_id)
    if not tenant_info:
        return None

    availability = get_availability(tenant_id, date_str)
    if availability is None:
        return None

    # Opening hours and full schedule
    open_h, close_h = parse_opening_hours(tenant_info, date_str)
    schedule_hours = generate_hourly_slots(open_h, close_h)

    # Current hour — only observe from this hour onwards
    now = datetime.now()
    current_hour = now.hour

    # Filter: only hours >= current hour (future + current)
    # For dates other than today, observe all hours (historical or future date)
    today_str = now.strftime("%Y-%m-%d")
    if date_str == today_str:
        observable_hours = [h for h in schedule_hours if h >= current_hour]
        # Handle wrap-around (club open past midnight)
        if close_h <= open_h and current_hour < open_h:
            observable_hours = [h for h in schedule_hours if h >= current_hour or h < close_h]
    else:
        observable_hours = schedule_hours

    # Build resource map
    resource_map = {}
    for r in tenant_info.get("resources", []):
        if r.get("sport_id") == "PADEL" and r.get("is_active", True):
            resource_map[r["resource_id"]] = r["name"].strip()

    if not resource_map:
        logger.warning(f"No active padel courts for {club_slug}")
        return None

    # Build availability map: resource_id -> set of available hours + prices
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
            duration = slot["duration"]
            price_str = slot.get("price", "0 PLN")
            price = float(price_str.replace(",", ".").split()[0])
            hourly_price = round(price / (duration / 60), 2)

            avail_hours[rid].add(start_h)
            if start_h not in avail_prices[rid] or duration == 60:
                avail_prices[rid][start_h] = hourly_price

            # Longer slots mark subsequent hours as available too
            if int(slot["start_time"].split(":")[1]) == 0 and duration >= 120:
                for extra in range(1, duration // 60):
                    extra_h = (start_h + extra) % 24
                    avail_hours[rid].add(extra_h)

    # Build observations for current + future hours only
    observations = []
    for rid, court_name in resource_map.items():
        court_avail = avail_hours.get(rid, set())
        court_prices = avail_prices.get(rid, {})
        all_prices = list(court_prices.values())
        default_price = sum(all_prices) / len(all_prices) if all_prices else 150.0

        for hour in observable_hours:
            if hour in court_avail:
                is_booked = False
                price = 0.0
            else:
                is_booked = True
                # Estimate price from nearby available slots
                price = default_price
                for offset in range(0, 4):
                    found = False
                    for direction in [offset, -offset]:
                        check_h = (hour + direction) % 24
                        if check_h in court_prices:
                            price = court_prices[check_h]
                            found = True
                            break
                    if found:
                        break

            observations.append({
                "court_name": court_name,
                "hour": hour,
                "is_booked": is_booked,
                "price": price,
            })

    if not observations:
        logger.warning(f"No observable slots for Playtomic {club_slug} on {date_str}")
        return None

    # Save observations (upsert — updates future hours, preserves past)
    save_playtomic_observations(date_str, club_slug, observations)

    # Rebuild daily snapshot from ALL accumulated observations
    summary = get_playtomic_daily_summary(date_str, club_slug)
    if summary:
        save_daily_snapshot(
            date_str,
            summary["total_booked"],
            summary["total_income"],
            json.dumps(summary["courts_summary"]),
            club_slug,
        )

    booked_now = sum(1 for o in observations if o["is_booked"])
    income_now = sum(o["price"] for o in observations if o["is_booked"])
    total_booked = summary["total_booked"] if summary else booked_now
    total_income = summary["total_income"] if summary else income_now

    logger.info(f"Playtomic {club_slug} {date_str}: observed {len(observations)} slots, "
                f"daily total: {total_booked} booked, {total_income:.2f} PLN")

    return {
        "date": date_str,
        "club": club_slug,
        "total_booked": total_booked,
        "total_income": total_income,
        "courts": summary["courts_summary"] if summary else {},
        "slot_count": len(observations),
        "observed_hours": len(observable_hours),
    }
