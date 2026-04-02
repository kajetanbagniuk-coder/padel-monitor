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

Pricing:
  - Price map built from future availability (all slots visible with prices)
  - Per club, per court type (single/double x indoor/outdoor), per day type
    (weekday/weekend), per hour
  - Updated weekly or when fully-available courts reveal new prices
"""

import requests
import json
import logging
import time
from datetime import datetime, timedelta

from database import (save_playtomic_observations, get_playtomic_daily_summary,
                      save_daily_snapshot, save_playtomic_prices,
                      get_playtomic_price)

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


def get_bookable_hours(tenant_id, day_type):
    """Determine actual bookable hours by checking a future date with lots of availability.

    Uses next Wednesday for weekday, next Saturday for weekend.
    The hours that appear as available across ALL courts = the real bookable range.
    """
    today = datetime.now()
    if day_type == "weekday":
        days_ahead = (2 - today.weekday()) % 7  # next Wednesday
        if days_ahead < 3:
            days_ahead += 7  # at least 3 days out for good availability
    else:
        days_ahead = (5 - today.weekday()) % 7  # next Saturday
        if days_ahead < 3:
            days_ahead += 7
    check_date = (today + timedelta(days=days_ahead)).strftime("%Y-%m-%d")

    availability = get_availability(tenant_id, check_date)
    if not availability:
        return None

    all_hours = set()
    for entry in availability:
        for slot in entry.get("slots", []):
            if slot["duration"] == 60:
                all_hours.add(int(slot["start_time"].split(":")[0]))
    return sorted(all_hours) if all_hours else None


# Cache bookable hours per tenant+day_type to avoid repeated API calls
_bookable_hours_cache = {}


def get_schedule_hours(tenant_id, date_str):
    """Get the actual bookable hours for a date, using cache."""
    day_type = get_day_type(date_str)
    cache_key = f"{tenant_id}_{day_type}"
    if cache_key not in _bookable_hours_cache:
        hours = get_bookable_hours(tenant_id, day_type)
        if hours:
            _bookable_hours_cache[cache_key] = hours
        else:
            # Fallback to opening hours if API check fails
            return None
    return _bookable_hours_cache[cache_key]


def classify_court(resource):
    """Classify a court by type using API properties."""
    props = resource.get("properties", {})
    size = props.get("resource_size", "double")  # single or double
    location = props.get("resource_type", "indoor")  # indoor or outdoor
    return f"{size}_{location}"


def get_day_type(date_str):
    """Return 'weekend' for Sat/Sun, 'weekday' otherwise."""
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    return "weekend" if dt.weekday() >= 5 else "weekday"


def build_price_map(club_slug, clubs_dict=None):
    """Build the price map for a club by scraping a future weekday and weekend day.

    Picks the next Wednesday (weekday) and next Saturday (weekend) to get
    full availability with prices for all court types.
    """
    if clubs_dict is None:
        from clubs import CLUBS
        clubs_dict = CLUBS
    club = clubs_dict.get(club_slug)
    if not club or not club.get("playtomic_id"):
        return None

    tenant_id = club["playtomic_id"]
    tenant_info = get_tenant_info(tenant_id)
    if not tenant_info:
        return None

    # Pick future dates with good availability (at least 5 days out)
    today = datetime.now()
    days_until_wed = (2 - today.weekday()) % 7
    if days_until_wed < 5:
        days_until_wed += 7
    weekday_date = (today + timedelta(days=days_until_wed)).strftime("%Y-%m-%d")
    days_until_sat = (5 - today.weekday()) % 7
    if days_until_sat < 5:
        days_until_sat += 7
    weekend_date = (today + timedelta(days=days_until_sat)).strftime("%Y-%m-%d")

    # Build resource info: resource_id -> (name, court_type)
    resource_info = {}
    for r in tenant_info.get("resources", []):
        if r.get("sport_id") == "PADEL" and r.get("is_active", True):
            resource_info[r["resource_id"]] = {
                "name": r["name"].strip(),
                "court_type": classify_court(r),
            }

    if not resource_info:
        return None

    prices_to_save = []
    total_prices = 0

    for date_str, day_type in [(weekday_date, "weekday"), (weekend_date, "weekend")]:
        availability = get_availability(tenant_id, date_str)
        if not availability:
            continue

        for entry in availability:
            rid = entry["resource_id"]
            if rid not in resource_info:
                continue
            court_type = resource_info[rid]["court_type"]

            for slot in entry.get("slots", []):
                duration = slot["duration"]
                if duration != 60:
                    continue  # Only use 60-min slots for exact hourly pricing
                start_h = int(slot["start_time"].split(":")[0])
                price_str = slot.get("price", "0 PLN")
                price = float(price_str.replace(",", ".").split()[0])

                prices_to_save.append({
                    "court_type": court_type,
                    "day_type": day_type,
                    "hour": start_h,
                    "price": price,
                })
                total_prices += 1

    if prices_to_save:
        save_playtomic_prices(club_slug, prices_to_save)
        logger.info(f"Price map built for {club_slug}: {total_prices} entries")

    return total_prices


def build_all_price_maps(clubs_dict=None):
    """Build price maps for all Playtomic clubs."""
    if clubs_dict is None:
        from clubs import CLUBS
        clubs_dict = CLUBS
    playtomic_slugs = [slug for slug, c in clubs_dict.items()
                       if c.get("booking_system") in ("playtomic", "both")]
    logger.info(f"Building price maps for {len(playtomic_slugs)} Playtomic clubs...")
    ok = 0
    for slug in playtomic_slugs:
        try:
            count = build_price_map(slug, clubs_dict)
            if count:
                ok += 1
        except Exception as e:
            logger.error(f"Price map failed for {slug}: {e}")
        time.sleep(1)
    logger.info(f"Price maps done: {ok}/{len(playtomic_slugs)} clubs")
    return ok


def get_price_for_slot(club_slug, court_type, day_type, hour):
    """Look up price from the map, with fallbacks."""
    # Exact match
    price = get_playtomic_price(club_slug, court_type, day_type, hour)
    if price is not None:
        return price
    # Try same court_type, opposite day_type (better than nothing)
    other_day = "weekend" if day_type == "weekday" else "weekday"
    price = get_playtomic_price(club_slug, court_type, other_day, hour)
    if price is not None:
        return price
    # Try double_indoor as default court type
    if court_type != "double_indoor":
        price = get_playtomic_price(club_slug, "double_indoor", day_type, hour)
        if price is not None:
            return price
    return None


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

    # Get actual bookable hours (from cached future availability check)
    schedule_hours = get_schedule_hours(tenant_id, date_str)
    if not schedule_hours:
        logger.warning(f"Could not determine bookable hours for {club_slug}")
        return None

    # For today: only observe FUTURE hours (current hour +1 onwards).
    # The current hour's slot is no longer bookable on Playtomic (it already
    # started), so it disappears from availability — but that does NOT mean
    # it was booked.  The previous scrape (at XX:45 of the prior hour)
    # already recorded the correct state when the slot was still in the future.
    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    if date_str == today_str:
        next_hour = now.hour + 1
        observable_hours = [h for h in schedule_hours if h >= next_hour]
    else:
        observable_hours = schedule_hours

    # Build resource map with court type classification
    resource_info = {}
    for r in tenant_info.get("resources", []):
        if r.get("sport_id") == "PADEL" and r.get("is_active", True):
            resource_info[r["resource_id"]] = {
                "name": r["name"].strip(),
                "court_type": classify_court(r),
            }

    if not resource_info:
        logger.warning(f"No active padel courts for {club_slug}")
        return None

    # Day type for price lookup
    day_type = get_day_type(date_str)

    # Build availability map: resource_id -> set of available hours + prices
    avail_hours = {}
    avail_prices = {}
    prices_for_map = []

    for entry in availability:
        rid = entry["resource_id"]
        if rid not in resource_info:
            continue
        court_type = resource_info[rid]["court_type"]
        avail_hours.setdefault(rid, set())
        avail_prices.setdefault(rid, {})

        for slot in entry.get("slots", []):
            start_h = int(slot["start_time"].split(":")[0])
            start_m = int(slot["start_time"].split(":")[1])
            duration = slot["duration"]
            price_str = slot.get("price", "0 PLN")
            price = float(price_str.replace(",", ".").split()[0])

            avail_hours[rid].add(start_h)

            # Record exact 60-min prices for the price map
            if duration == 60:
                avail_prices[rid][start_h] = price
                prices_for_map.append({
                    "court_type": court_type,
                    "day_type": day_type,
                    "hour": start_h,
                    "price": price,
                })

            # Longer slots mark subsequent hours as available
            if start_m == 0 and duration >= 120:
                for extra in range(1, duration // 60):
                    extra_h = (start_h + extra) % 24
                    avail_hours[rid].add(extra_h)

    # Update price map with any new prices we found
    if prices_for_map:
        save_playtomic_prices(club_slug, prices_for_map)

    # Build observations
    observations = []
    for rid, info in resource_info.items():
        court_name = info["name"]
        court_type = info["court_type"]
        court_avail = avail_hours.get(rid, set())

        for hour in observable_hours:
            if hour in court_avail:
                is_booked = False
                price = 0.0
            else:
                is_booked = True
                # Look up price from the map
                price = get_price_for_slot(club_slug, court_type, day_type, hour)
                if price is None:
                    # Fallback: use price from available slots on this court
                    court_prices = avail_prices.get(rid, {})
                    if court_prices:
                        all_p = list(court_prices.values())
                        price = sum(all_p) / len(all_p)
                    else:
                        price = 150.0  # last resort default

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
    # Pass schedule_hours to clean up any stale observations from wrong schedule
    save_playtomic_observations(date_str, club_slug, observations, valid_hours=schedule_hours)

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

    total_booked = summary["total_booked"] if summary else 0
    total_income = summary["total_income"] if summary else 0

    logger.info(f"Playtomic {club_slug} {date_str}: {total_booked} booked, {total_income:.2f} PLN")

    return {
        "date": date_str,
        "club": club_slug,
        "total_booked": total_booked,
        "total_income": total_income,
        "courts": summary["courts_summary"] if summary else {},
        "slot_count": len(observations),
        "observed_hours": len(observable_hours),
    }
