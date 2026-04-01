"""
Padel pricing engine with per-club support.

Generic pricing (Loba Padel rates, from 20 February 2026):

Monday - Friday:
  06:00 - 16:00  -> 120 PLN/H
  16:00 - 22:00  -> 200 PLN/H
  22:00 - 06:00  -> 140 PLN/H

Saturday - Sunday:
  06:00 onwards  -> 200 PLN/H

Holidays:
  06:00 onwards  -> 200 PLN/H

Slots are 30 minutes, so rates are halved per slot.

Per-club pricing is loaded from the database (scraped from kluby.org)
and cached in memory with a 5-minute TTL.
"""

import json
import logging
from datetime import datetime, time as dt_time

logger = logging.getLogger(__name__)

# Polish public holidays 2026 (fixed + calculated)
HOLIDAYS_2026 = {
    "2026-01-01",  # Nowy Rok
    "2026-01-06",  # Trzech Kroli
    "2026-04-05",  # Wielkanoc (Easter Sunday)
    "2026-04-06",  # Poniedzialek Wielkanocny
    "2026-05-01",  # Swieto Pracy
    "2026-05-03",  # Swieto Konstytucji
    "2026-05-24",  # Zeslanie Ducha Swietego (Pentecost)
    "2026-06-04",  # Boze Cialo (Corpus Christi)
    "2026-08-15",  # Wniebowziecie NMP
    "2026-11-01",  # Wszystkich Swietych
    "2026-11-11",  # Swieto Niepodleglosci
    "2026-12-25",  # Boze Narodzenie
    "2026-12-26",  # Boze Narodzenie 2
}

# Cache: {club_slug: (rules_list, timestamp)}
_pricing_cache = {}
_CACHE_TTL = 300  # 5 minutes


def is_holiday(date_str):
    return date_str in HOLIDAYS_2026


def _generic_slot_price(date_str, slot_start_time):
    """Original Loba Padel pricing (fallback)."""
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    weekday = dt.weekday()  # 0=Mon, 6=Sun
    hour, minute = map(int, slot_start_time.split(":"))
    slot_time = dt_time(hour, minute)

    if is_holiday(date_str):
        return 100.0
    if weekday >= 5:
        return 100.0
    if dt_time(6, 0) <= slot_time < dt_time(16, 0):
        return 60.0
    elif dt_time(16, 0) <= slot_time < dt_time(22, 0):
        return 100.0
    else:
        return 70.0


def clear_pricing_cache(club_slug=None):
    """Clear cached pricing rules. Call after saving new pricing to DB."""
    if club_slug:
        _pricing_cache.pop(club_slug, None)
    else:
        _pricing_cache.clear()


def _load_club_rules(club_slug):
    """Load pricing rules for a club from DB, with caching."""
    now = datetime.now().timestamp()

    if club_slug in _pricing_cache:
        rules, cached_at = _pricing_cache[club_slug]
        if now - cached_at < _CACHE_TTL:
            return rules

    try:
        from database import get_club_pricing
        row = get_club_pricing(club_slug)
        if row and row["status"] == "ok" and row["pricing_json"]:
            rules = json.loads(row["pricing_json"])
            if rules:
                _pricing_cache[club_slug] = (rules, now)
                return rules
    except Exception as e:
        logger.warning(f"Failed to load pricing for {club_slug}: {e}")

    # Cache the miss too, so we don't hit DB every call
    _pricing_cache[club_slug] = (None, now)
    return None


def _calculate_from_rules(date_str, slot_start_time, rules):
    """Match a time slot to a pricing rule and return 30-min price."""
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    weekday = dt.weekday()  # 0=Mon, 6=Sun
    hour, minute = map(int, slot_start_time.split(":"))
    is_hol = is_holiday(date_str)
    is_wknd = weekday >= 5

    # Determine which day_type(s) to match
    if is_hol:
        day_types = ["holiday", "all", "weekend"]  # holidays often use weekend rate
    elif is_wknd:
        day_types = ["weekend", "all"]
    else:
        day_types = ["weekday", "all"]

    best_match = None

    for rule in rules:
        if rule["day_type"] not in day_types:
            continue

        # Check if slot time falls within this rule's range
        rule_start = rule["start_hour"] * 60 + rule["start_min"]
        rule_end = rule["end_hour"] * 60 + rule["end_min"]
        slot_minutes = hour * 60 + minute

        # Handle "23:59" as end-of-day marker
        if rule_end == 23 * 60 + 59:
            rule_end = 24 * 60

        if rule_start <= slot_minutes < rule_end:
            # Prefer more specific day_type match
            priority = day_types.index(rule["day_type"])
            if best_match is None or priority < best_match[0]:
                best_match = (priority, rule)

    if best_match:
        return best_match[1]["price_per_hour"] / 2  # 30-min slot

    return None


def get_slot_price(date_str, slot_start_time, club_slug=None):
    """
    Calculate price for a single 30-min slot.
    date_str: "YYYY-MM-DD"
    slot_start_time: "HH:MM" (e.g. "06:00", "16:30")
    club_slug: optional club identifier for per-club pricing
    Returns price in PLN for that 30-min slot.
    """
    if club_slug:
        rules = _load_club_rules(club_slug)
        if rules:
            price = _calculate_from_rules(date_str, slot_start_time, rules)
            if price is not None:
                return price

    # Fallback to generic Loba pricing
    return _generic_slot_price(date_str, slot_start_time)
