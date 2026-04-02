"""
Padel Market Monitor - Main Application

A web dashboard that tracks court bookings and calculates income
for padel clubs across the entire Polish market, based on data
scraped from kluby.org and Playtomic.
"""

import logging
import json
import os
import time
from datetime import datetime, timedelta
from flask import Flask, render_template, jsonify, request
from apscheduler.schedulers.background import BackgroundScheduler

from database import (init_db, get_latest_snapshot_for_date, get_income_range,
                      get_all_snapshots_for_date, get_club_pricing, get_all_club_pricing,
                      get_aggregated_daily, get_aggregated_range, get_date_coverage)
from scraper import scrape_date
from playtomic_scraper import scrape_playtomic_hourly, build_all_price_maps
from pricing_scraper import scrape_club_pricing, scrape_all_pricing
from clubs import CLUBS, DEFAULT_CLUB

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# ── Scheduler ──────────────────────────────────────────────────────
scheduler = BackgroundScheduler(job_defaults={"misfire_grace_time": 60, "coalesce": True, "max_instances": 1})


def scrape_club(club_slug, date_str):
    """Scrape a single club using the appropriate scraper based on booking_system."""
    club = CLUBS.get(club_slug)
    if not club:
        return None
    system = club.get("booking_system", "kluby_org")
    if system == "playtomic":
        return scrape_playtomic_hourly(date_str, club_slug)
    elif system == "both":
        # Use Playtomic as primary (has real prices), fall back to kluby.org
        result = scrape_playtomic_hourly(date_str, club_slug)
        if not result:
            result = scrape_date(date_str, club_slug)
        return result
    else:
        return scrape_date(date_str, club_slug)


def scheduled_scrape_kluby():
    """Scrape today + 7 days ahead for kluby.org clubs."""
    today = datetime.now()
    dates = [today + timedelta(days=d) for d in range(8)]  # today .. today+7
    kluby_slugs = [slug for slug, c in CLUBS.items()
                   if c.get("booking_system", "kluby_org") != "playtomic"]
    logger.info(f"Kluby scrape: {len(kluby_slugs)} clubs x {len(dates)} days")
    for club_slug in kluby_slugs:
        for date in dates:
            date_str = date.strftime("%Y-%m-%d")
            try:
                result = scrape_date(date_str, club_slug)
                if result:
                    logger.info(f"  kluby {club_slug} {date_str}: {result['total_booked']} booked, {result['total_income']:.2f} PLN")
            except Exception as e:
                logger.error(f"  kluby {club_slug} {date_str} failed: {e}")
            time.sleep(1)  # Rate limiting
        time.sleep(1)


def scheduled_scrape_playtomic():
    """Hourly scrape of Playtomic clubs for TODAY only — called at XX:45.

    Today needs hourly observations because past slots are hidden.
    """
    today_str = datetime.now().strftime("%Y-%m-%d")
    playtomic_slugs = [slug for slug, c in CLUBS.items()
                       if c.get("booking_system") in ("playtomic", "both")]
    logger.info(f"Playtomic hourly scrape: {len(playtomic_slugs)} clubs for {today_str}")
    for club_slug in playtomic_slugs:
        try:
            result = scrape_playtomic_hourly(today_str, club_slug)
            if result:
                logger.info(f"  playtomic {club_slug}: {result['total_booked']} booked, {result['total_income']:.2f} PLN")
        except Exception as e:
            logger.error(f"  playtomic {club_slug} failed: {e}")
        time.sleep(1)


def scheduled_scrape_playtomic_future():
    """Scrape Playtomic clubs for tomorrow + 7 days ahead.

    Future dates show the FULL schedule (no hidden slots), so this
    only needs to run a few times a day, not every hour.
    """
    today = datetime.now()
    dates = [today + timedelta(days=d) for d in range(1, 8)]  # tomorrow .. today+7
    playtomic_slugs = [slug for slug, c in CLUBS.items()
                       if c.get("booking_system") in ("playtomic", "both")]
    logger.info(f"Playtomic future scrape: {len(playtomic_slugs)} clubs x {len(dates)} days")
    for date in dates:
        date_str = date.strftime("%Y-%m-%d")
        for club_slug in playtomic_slugs:
            try:
                result = scrape_playtomic_hourly(date_str, club_slug)
                if result:
                    logger.info(f"  playtomic {club_slug} {date_str}: {result['total_booked']} booked, {result['total_income']:.2f} PLN")
            except Exception as e:
                logger.error(f"  playtomic {club_slug} {date_str} failed: {e}")
            time.sleep(1)
        time.sleep(1)  # Rate limiting


def scheduled_pricing_scrape():
    """Weekly re-scrape of all club pricing."""
    logger.info("Starting weekly pricing re-scrape...")
    try:
        summary = scrape_all_pricing()
        logger.info(f"Weekly pricing scrape done: {summary['ok']} ok, {summary['not_found']} not found, {summary['parse_error']} errors")
    except Exception as e:
        logger.error(f"Weekly pricing scrape failed: {e}")


def scheduled_playtomic_price_maps():
    """Weekly rebuild of Playtomic price maps from future availability."""
    logger.info("Rebuilding Playtomic price maps...")
    try:
        ok = build_all_price_maps()
        logger.info(f"Playtomic price maps rebuilt: {ok} clubs")
    except Exception as e:
        logger.error(f"Playtomic price map rebuild failed: {e}")


# Kluby.org: today + 7 days ahead at 10:00, 18:00, 23:40
scheduler.add_job(scheduled_scrape_kluby, "cron", hour=10, minute=0, id="kluby_10am")
scheduler.add_job(scheduled_scrape_kluby, "cron", hour=18, minute=0, id="kluby_6pm")
scheduler.add_job(scheduled_scrape_kluby, "cron", hour=23, minute=40, id="kluby_1140pm")
# Playtomic TODAY: every 30 min at :15 and :45 (captures each 30-min booking window)
scheduler.add_job(scheduled_scrape_playtomic, "cron", minute="15,45", id="playtomic_30min")
# Playtomic FUTURE: tomorrow + 7 days at 10:00, 18:00, 23:40
scheduler.add_job(scheduled_scrape_playtomic_future, "cron", hour=10, minute=0, id="playtomic_future_10am")
scheduler.add_job(scheduled_scrape_playtomic_future, "cron", hour=18, minute=0, id="playtomic_future_6pm")
scheduler.add_job(scheduled_scrape_playtomic_future, "cron", hour=23, minute=40, id="playtomic_future_1140pm")
# Weekly pricing re-scrape: Monday 3 AM
scheduler.add_job(scheduled_pricing_scrape, "cron", day_of_week="mon", hour=3, minute=0, id="pricing_weekly")
# Weekly Playtomic price maps: Monday 4 AM
scheduler.add_job(scheduled_playtomic_price_maps, "cron", day_of_week="mon", hour=4, minute=0, id="playtomic_prices_weekly")


# ── Routes ─────────────────────────────────────────────────────────

@app.route("/")
def dashboard():
    return render_template("dashboard.html")


@app.route("/api/clubs")
def api_clubs():
    """List all available clubs."""
    return jsonify(CLUBS)


@app.route("/api/scrape-now")
def api_scrape_now():
    """Manually trigger a scrape. ?date=YYYY-MM-DD&club=slug"""
    date_str = request.args.get("date", datetime.now().strftime("%Y-%m-%d"))
    club_slug = request.args.get("club", DEFAULT_CLUB)
    if club_slug not in CLUBS:
        return jsonify({"status": "error", "message": f"Unknown club: {club_slug}"}), 400
    try:
        result = scrape_club(club_slug, date_str)
        if result:
            return jsonify({"status": "ok", "data": result})
        return jsonify({"status": "error", "message": "Scrape returned no data"}), 500
    except Exception as e:
        logger.error(f"Scrape error for {club_slug}: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/db-health")
def api_db_health():
    """Check database health."""
    try:
        from database import get_connection
        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM daily_snapshot")
        count = c.fetchone()[0]
        conn.close()
        return jsonify({"status": "ok", "snapshots": count})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/daily")
def api_daily():
    """Get daily income. ?date=YYYY-MM-DD&club=slug"""
    date_str = request.args.get("date", datetime.now().strftime("%Y-%m-%d"))
    club_slug = request.args.get("club", DEFAULT_CLUB)
    snapshot = get_latest_snapshot_for_date(date_str, club_slug)
    if snapshot:
        snapshot["courts_data"] = json.loads(snapshot["courts_data"])
        return jsonify(snapshot)
    return jsonify({"target_date": date_str, "club_slug": club_slug, "total_income": 0, "total_booked_slots": 0, "courts_data": {}, "message": "No data yet"})


@app.route("/api/daily-history")
def api_daily_history():
    """Get all snapshots for a day. ?date=YYYY-MM-DD&club=slug"""
    date_str = request.args.get("date", datetime.now().strftime("%Y-%m-%d"))
    club_slug = request.args.get("club", DEFAULT_CLUB)
    snapshots = get_all_snapshots_for_date(date_str, club_slug)
    for s in snapshots:
        s["courts_data"] = json.loads(s["courts_data"])
    return jsonify(snapshots)


@app.route("/api/weekly")
def api_weekly():
    """Get weekly income. ?week_start=YYYY-MM-DD&club=slug"""
    today = datetime.now()
    default_start = (today - timedelta(days=today.weekday())).strftime("%Y-%m-%d")
    start = request.args.get("week_start", default_start)
    club_slug = request.args.get("club", DEFAULT_CLUB)
    start_dt = datetime.strptime(start, "%Y-%m-%d")
    end = (start_dt + timedelta(days=6)).strftime("%Y-%m-%d")
    rows = get_income_range(start, end, club_slug)
    total = sum(r["total_income"] for r in rows)
    return jsonify({"week_start": start, "week_end": end, "total_income": total, "days": rows})


@app.route("/api/monthly")
def api_monthly():
    """Get monthly income. ?month=YYYY-MM&club=slug"""
    today = datetime.now()
    month_str = request.args.get("month", today.strftime("%Y-%m"))
    club_slug = request.args.get("club", DEFAULT_CLUB)
    year, month = map(int, month_str.split("-"))
    start = f"{year}-{month:02d}-01"
    if month == 12:
        end = f"{year + 1}-01-01"
    else:
        end = f"{year}-{month + 1:02d}-01"
    end_dt = datetime.strptime(end, "%Y-%m-%d") - timedelta(days=1)
    end = end_dt.strftime("%Y-%m-%d")
    rows = get_income_range(start, end, club_slug)
    total = sum(r["total_income"] for r in rows)
    return jsonify({"month": month_str, "start": start, "end": end, "total_income": total, "days": rows})


# ── Aggregated API ─────────────────────────────────────────────────

@app.route("/api/aggregated-daily")
def api_aggregated_daily():
    """Aggregated income across all clubs for a single date. ?date=YYYY-MM-DD&city=CityName"""
    date_str = request.args.get("date", datetime.now().strftime("%Y-%m-%d"))
    city = request.args.get("city")
    if city == "ALL":
        city = None
    result = get_aggregated_daily(date_str, city)
    # Enrich club data with name/city/courts from CLUBS dict
    clubs_enriched = []
    for c in result["clubs"]:
        info = CLUBS.get(c["club_slug"], {})
        clubs_enriched.append({
            "slug": c["club_slug"],
            "name": info.get("name", c["club_slug"]),
            "city": info.get("city", ""),
            "courts": info.get("courts", 0),
            "income": c["total_income"],
            "booked": c.get("total_booked_slots", 0),
            "booking_system": info.get("booking_system", "kluby_org"),
        })
    return jsonify({
        "date": date_str,
        "city": city or "ALL",
        "total_income": result["total_income"],
        "total_booked": result["total_booked"],
        "clubs": clubs_enriched,
    })


@app.route("/api/aggregated-range")
def api_aggregated_range():
    """Aggregated income across all clubs for a date range. ?start=YYYY-MM-DD&end=YYYY-MM-DD&city=CityName"""
    today = datetime.now()
    start = request.args.get("start", today.strftime("%Y-%m-%d"))
    end = request.args.get("end", today.strftime("%Y-%m-%d"))
    city = request.args.get("city")
    if city == "ALL":
        city = None
    result = get_aggregated_range(start, end, city)
    clubs_enriched = []
    for c in result["clubs"]:
        info = CLUBS.get(c["club_slug"], {})
        clubs_enriched.append({
            "slug": c["club_slug"],
            "name": info.get("name", c["club_slug"]),
            "city": info.get("city", ""),
            "courts": info.get("courts", 0),
            "income": c["total_income"],
            "booking_system": info.get("booking_system", "kluby_org"),
        })
    return jsonify({
        "start": start,
        "end": end,
        "city": city or "ALL",
        "total_income": result["total_income"],
        "clubs": clubs_enriched,
    })


# ── Pricing API ────────────────────────────────────────────────────

def _playtomic_price_map_to_rules(price_map_rows):
    """Convert playtomic_price_map rows into display rules grouped by court_type and day_type.

    Groups consecutive hours with the same price into time ranges.
    """
    from collections import defaultdict

    # Group by (court_type, day_type, price) to find consecutive hour ranges
    grouped = defaultdict(list)
    for row in price_map_rows:
        key = (row["court_type"], row["day_type"])
        grouped[key].append((row["hour"], row["price"]))

    court_labels = {
        "double_indoor": "Double Indoor",
        "double_outdoor": "Double Outdoor",
        "single_indoor": "Single Indoor",
        "single_outdoor": "Single Outdoor",
    }
    day_labels = {"weekday": "Mon-Fri", "weekend": "Sat-Sun"}

    rules = []
    for (court_type, day_type), hours_prices in sorted(grouped.items()):
        hours_prices.sort(key=lambda x: x[0])
        # Group consecutive hours with same price
        i = 0
        while i < len(hours_prices):
            start_h, price = hours_prices[i]
            end_h = start_h + 1
            j = i + 1
            while j < len(hours_prices) and hours_prices[j][1] == price and hours_prices[j][0] == end_h:
                end_h = hours_prices[j][0] + 1
                j += 1
            court_label = court_labels.get(court_type, court_type)
            day_label = day_labels.get(day_type, day_type)
            rules.append({
                "day_type": f"{day_label} | {court_label}",
                "start_hour": start_h, "start_min": 0,
                "end_hour": end_h, "end_min": 0,
                "price_per_hour": price,
            })
            i = j
    return rules


@app.route("/api/date-coverage")
def api_date_coverage():
    """Get all dates with data, including totals."""
    return jsonify(get_date_coverage())


@app.route("/api/club-pricing")
def api_club_pricing():
    """Get pricing rules for a club. ?club=slug"""
    club_slug = request.args.get("club", DEFAULT_CLUB)
    club = CLUBS.get(club_slug, {})
    system = club.get("booking_system", "kluby_org")

    # For Playtomic clubs, use the playtomic_price_map
    if system in ("playtomic", "both") and club.get("playtomic_id"):
        from database import get_playtomic_price_map
        price_map = get_playtomic_price_map(club_slug)
        if price_map:
            rules = _playtomic_price_map_to_rules(price_map)
            updated = price_map[0]["updated_at"] if price_map else None
            return jsonify({
                "club_slug": club_slug,
                "pricing_type": "per_club",
                "rules": rules,
                "scraped_at": updated,
                "notes": "From Playtomic API",
            })

    # For kluby.org clubs, use club_pricing table
    row = get_club_pricing(club_slug)
    if row and row["status"] == "ok":
        return jsonify({
            "club_slug": club_slug,
            "pricing_type": "per_club",
            "rules": json.loads(row["pricing_json"]),
            "scraped_at": row["scraped_at"],
            "notes": row["notes"],
        })
    # Generic fallback
    return jsonify({
        "club_slug": club_slug,
        "pricing_type": "generic",
        "rules": [
            {"day_type": "weekday", "start_hour": 6, "start_min": 0, "end_hour": 16, "end_min": 0, "price_per_hour": 120},
            {"day_type": "weekday", "start_hour": 16, "start_min": 0, "end_hour": 22, "end_min": 0, "price_per_hour": 200},
            {"day_type": "weekday", "start_hour": 22, "start_min": 0, "end_hour": 23, "end_min": 59, "price_per_hour": 140},
            {"day_type": "weekend", "start_hour": 6, "start_min": 0, "end_hour": 23, "end_min": 59, "price_per_hour": 200},
        ],
        "scraped_at": None,
        "notes": row["notes"] if row else "No pricing data scraped yet",
    })


@app.route("/api/scrape-pricing")
def api_scrape_pricing():
    """Trigger pricing scrape. ?club=slug or ?all=true"""
    if request.args.get("all") == "true":
        import threading
        threading.Thread(target=scrape_all_pricing, daemon=True).start()
        return jsonify({"status": "ok", "message": "Scraping all clubs in background..."})
    club_slug = request.args.get("club")
    if not club_slug:
        return jsonify({"status": "error", "message": "Provide ?club=slug or ?all=true"}), 400
    if club_slug not in CLUBS:
        return jsonify({"status": "error", "message": f"Unknown club: {club_slug}"}), 400
    result = scrape_club_pricing(club_slug)
    return jsonify({"status": "ok", "data": {"slug": club_slug, "scrape_status": result["status"], "notes": result["notes"], "rule_count": len(result["rules"])}})


@app.route("/api/pricing-status")
def api_pricing_status():
    """Overview of all clubs' pricing scrape status."""
    all_pricing = get_all_club_pricing()
    scraped_slugs = {p["club_slug"] for p in all_pricing}
    total = len(CLUBS)
    ok = sum(1 for p in all_pricing if p["status"] == "ok")
    not_found = sum(1 for p in all_pricing if p["status"] == "not_found")
    parse_error = sum(1 for p in all_pricing if p["status"] == "parse_error")
    not_scraped = total - len(scraped_slugs)
    return jsonify({
        "total_clubs": total,
        "ok": ok,
        "not_found": not_found,
        "parse_error": parse_error,
        "not_scraped": not_scraped,
        "clubs": all_pricing,
    })


# ── Startup ────────────────────────────────────────────────────────

def _startup_pricing_scrape():
    """If club_pricing table is empty, scrape all pricing in background."""
    all_pricing = get_all_club_pricing()
    if not all_pricing:
        logger.info("Club pricing table empty - scraping all club pricing...")
        scrape_all_pricing()
        logger.info("Initial pricing scrape complete.")
    else:
        logger.info(f"Club pricing table has {len(all_pricing)} entries, skipping auto-scrape.")


def _startup_playtomic_prices():
    """Build Playtomic price maps if not yet populated — deferred to avoid blocking."""
    import time as _time
    _time.sleep(60)  # Wait for app to stabilize before heavy DB work
    from database import get_playtomic_price_map
    test = get_playtomic_price_map("interpadel-warszawa")
    if not test:
        logger.info("Playtomic price maps empty - building from future availability...")
        build_all_price_maps()
        logger.info("Initial Playtomic price map build complete.")
    else:
        logger.info("Playtomic price maps already populated, skipping.")


# ── Initialization (runs under both gunicorn and local dev) ───────
import threading

try:
    init_db()
    logger.info("Database initialized.")
except Exception as e:
    logger.error(f"init_db failed (will retry on first request): {e}")

scheduler.start()
logger.info("App started. Scheduler running.")

# Delay startup tasks to let the web server become responsive first
def _delayed_startup():
    time.sleep(30)  # Wait 30s before any background DB work
    try:
        _startup_pricing_scrape()
    except Exception as e:
        logger.error(f"Startup pricing scrape failed: {e}")
    try:
        _startup_playtomic_prices()
    except Exception as e:
        logger.error(f"Startup playtomic prices failed: {e}")

threading.Thread(target=_delayed_startup, daemon=True).start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    logger.info(f"Starting Padel Income Monitor on http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
