import os
import psycopg2
import psycopg2.extras
from datetime import datetime, timedelta

DATABASE_URL = os.environ.get("DATABASE_URL")


def get_connection():
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    return conn


def _dictrows(cursor):
    """Convert cursor results to list of dicts."""
    cols = [d[0] for d in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]


def _dictrow(cursor):
    """Convert single cursor result to dict."""
    row = cursor.fetchone()
    if not row:
        return None
    cols = [d[0] for d in cursor.description]
    return dict(zip(cols, row))


def init_db():
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS scrape_log (
            id SERIAL PRIMARY KEY,
            scraped_at TEXT NOT NULL,
            target_date TEXT NOT NULL,
            club_slug TEXT NOT NULL DEFAULT 'loba-padel'
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS bookings (
            id SERIAL PRIMARY KEY,
            scrape_id INTEGER NOT NULL REFERENCES scrape_log(id),
            target_date TEXT NOT NULL,
            club_slug TEXT NOT NULL DEFAULT 'loba-padel',
            court_name TEXT NOT NULL,
            slot_start TEXT NOT NULL,
            slot_end TEXT NOT NULL,
            is_booked INTEGER NOT NULL,
            booking_label TEXT,
            income REAL NOT NULL DEFAULT 0
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS daily_snapshot (
            id SERIAL PRIMARY KEY,
            target_date TEXT NOT NULL,
            club_slug TEXT NOT NULL DEFAULT 'loba-padel',
            snapshot_at TEXT NOT NULL,
            total_booked_slots INTEGER NOT NULL,
            total_income REAL NOT NULL,
            courts_data TEXT NOT NULL
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS club_pricing (
            id SERIAL PRIMARY KEY,
            club_slug TEXT NOT NULL UNIQUE,
            pricing_json TEXT NOT NULL,
            raw_html TEXT,
            scraped_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'ok',
            notes TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS playtomic_observations (
            target_date TEXT NOT NULL,
            club_slug TEXT NOT NULL,
            court_name TEXT NOT NULL,
            hour INTEGER NOT NULL,
            is_booked INTEGER NOT NULL,
            price REAL NOT NULL DEFAULT 0,
            observed_at TEXT NOT NULL,
            PRIMARY KEY (target_date, club_slug, court_name, hour)
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS playtomic_price_map (
            club_slug TEXT NOT NULL,
            court_type TEXT NOT NULL,
            day_type TEXT NOT NULL,
            hour INTEGER NOT NULL,
            price REAL NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (club_slug, court_type, day_type, hour)
        )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS idx_bookings_date_club ON bookings(target_date, club_slug)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_snapshot_date_club ON daily_snapshot(target_date, club_slug)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_ptobs_date_club ON playtomic_observations(target_date, club_slug)")
    conn.commit()
    conn.close()


def save_scrape(target_date, slots, club_slug="loba-padel"):
    conn = get_connection()
    c = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("INSERT INTO scrape_log (scraped_at, target_date, club_slug) VALUES (%s, %s, %s) RETURNING id",
              (now, target_date, club_slug))
    scrape_id = c.fetchone()[0]
    for s in slots:
        c.execute("""
            INSERT INTO bookings (scrape_id, target_date, club_slug, court_name, slot_start, slot_end, is_booked, booking_label, income)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (scrape_id, target_date, club_slug, s["court"], s["start"], s["end"],
              1 if s["booked"] else 0, s.get("label", ""), s["income"]))
    conn.commit()
    conn.close()
    return scrape_id


def save_daily_snapshot(target_date, total_booked, total_income, courts_json, club_slug="loba-padel"):
    conn = get_connection()
    c = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("""
        INSERT INTO daily_snapshot (target_date, club_slug, snapshot_at, total_booked_slots, total_income, courts_data)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (target_date, club_slug, now, total_booked, total_income, courts_json))
    conn.commit()
    conn.close()


def get_latest_snapshot_for_date(target_date, club_slug="loba-padel"):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT * FROM daily_snapshot WHERE target_date = %s AND club_slug = %s ORDER BY snapshot_at DESC LIMIT 1
    """, (target_date, club_slug))
    row = _dictrow(c)
    conn.close()
    return row


def get_income_range(start_date, end_date, club_slug="loba-padel"):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT target_date, MAX(snapshot_at) as latest, MAX(total_income) as total_income
        FROM daily_snapshot
        WHERE target_date >= %s AND target_date <= %s AND club_slug = %s
        GROUP BY target_date
    """, (start_date, end_date, club_slug))
    rows = _dictrows(c)
    conn.close()
    return rows


def get_all_snapshots_for_date(target_date, club_slug="loba-padel"):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT * FROM daily_snapshot WHERE target_date = %s AND club_slug = %s ORDER BY snapshot_at ASC
    """, (target_date, club_slug))
    rows = _dictrows(c)
    conn.close()
    return rows


def get_aggregated_daily(target_date, city=None):
    from clubs import CLUBS
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT DISTINCT ON (club_slug) club_slug, total_income, total_booked_slots
        FROM daily_snapshot
        WHERE target_date = %s
        ORDER BY club_slug, snapshot_at DESC
    """, (target_date,))
    rows = _dictrows(c)
    conn.close()

    clubs = []
    total_income = 0
    total_booked = 0
    for row in rows:
        slug = row["club_slug"]
        if slug not in CLUBS:
            continue
        if city and CLUBS[slug]["city"] != city:
            continue
        clubs.append({
            "club_slug": slug,
            "total_income": row["total_income"],
            "total_booked_slots": row["total_booked_slots"],
        })
        total_income += row["total_income"]
        total_booked += row["total_booked_slots"]

    return {"clubs": clubs, "total_income": total_income, "total_booked": total_booked}


def get_aggregated_range(start_date, end_date, city=None):
    from clubs import CLUBS
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT club_slug, SUM(total_income) as total_income
        FROM (
            SELECT DISTINCT ON (club_slug, target_date) club_slug, target_date, total_income
            FROM daily_snapshot
            WHERE target_date >= %s AND target_date <= %s
            ORDER BY club_slug, target_date, snapshot_at DESC
        ) sub
        GROUP BY club_slug
    """, (start_date, end_date))
    rows = _dictrows(c)
    conn.close()

    clubs = []
    total_income = 0
    for row in rows:
        slug = row["club_slug"]
        if slug not in CLUBS:
            continue
        if city and CLUBS[slug]["city"] != city:
            continue
        clubs.append({"club_slug": slug, "total_income": row["total_income"]})
        total_income += row["total_income"]

    return {"clubs": clubs, "total_income": total_income}


def get_date_coverage():
    """Get all dates that have snapshot data, with totals."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT target_date,
               COUNT(DISTINCT club_slug) as club_count,
               SUM(total_income) as total_income,
               SUM(total_booked_slots) as total_booked,
               MAX(snapshot_at) as last_snapshot
        FROM (
            SELECT DISTINCT ON (club_slug, target_date)
                   club_slug, target_date, total_income, total_booked_slots, snapshot_at
            FROM daily_snapshot
            ORDER BY club_slug, target_date, snapshot_at DESC
        ) sub
        GROUP BY target_date
        ORDER BY target_date
    """)
    rows = _dictrows(c)
    conn.close()
    for r in rows:
        r["target_date"] = str(r["target_date"])
        r["last_snapshot"] = str(r["last_snapshot"]) if r["last_snapshot"] else None
        r["total_income"] = float(r["total_income"] or 0)
        r["total_booked"] = int(r["total_booked"] or 0)
    return rows


def save_playtomic_prices(club_slug, prices):
    conn = get_connection()
    c = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for p in prices:
        c.execute("""
            INSERT INTO playtomic_price_map (club_slug, court_type, day_type, hour, price, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (club_slug, court_type, day_type, hour) DO UPDATE SET
                price = EXCLUDED.price,
                updated_at = EXCLUDED.updated_at
        """, (club_slug, p["court_type"], p["day_type"], p["hour"], p["price"], now))
    conn.commit()
    conn.close()


def get_playtomic_price(club_slug, court_type, day_type, hour):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT price FROM playtomic_price_map
        WHERE club_slug = %s AND court_type = %s AND day_type = %s AND hour = %s
    """, (club_slug, court_type, day_type, hour))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None


def get_playtomic_price_map(club_slug):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT court_type, day_type, hour, price, updated_at
        FROM playtomic_price_map
        WHERE club_slug = %s
        ORDER BY court_type, day_type, hour
    """, (club_slug,))
    rows = _dictrows(c)
    conn.close()
    return rows


def save_playtomic_observations(target_date, club_slug, observations, valid_hours=None):
    conn = get_connection()
    c = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if valid_hours is not None:
        c.execute("""
            DELETE FROM playtomic_observations
            WHERE target_date = %s AND club_slug = %s AND hour != ALL(%s)
        """, (target_date, club_slug, valid_hours))

    for obs in observations:
        c.execute("""
            INSERT INTO playtomic_observations (target_date, club_slug, court_name, hour, is_booked, price, observed_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (target_date, club_slug, court_name, hour) DO UPDATE SET
                is_booked = EXCLUDED.is_booked,
                price = EXCLUDED.price,
                observed_at = EXCLUDED.observed_at
        """, (target_date, club_slug, obs["court_name"], obs["hour"],
              1 if obs["is_booked"] else 0, obs["price"], now))
    conn.commit()
    conn.close()


def get_playtomic_daily_summary(target_date, club_slug):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT court_name, hour, is_booked, price
        FROM playtomic_observations
        WHERE target_date = %s AND club_slug = %s
        ORDER BY court_name, hour
    """, (target_date, club_slug))
    rows = _dictrows(c)
    conn.close()

    if not rows:
        return None

    courts_summary = {}
    total_booked = 0
    total_income = 0.0
    for row in rows:
        court = row["court_name"]
        if court not in courts_summary:
            courts_summary[court] = {"booked": 0, "available": 0, "income": 0.0}
        if row["is_booked"]:
            courts_summary[court]["booked"] += 1
            courts_summary[court]["income"] += row["price"]
            total_booked += 1
            total_income += row["price"]
        else:
            courts_summary[court]["available"] += 1

    return {"total_booked": total_booked, "total_income": total_income, "courts_summary": courts_summary}


def save_club_pricing(club_slug, pricing_json, raw_html, status="ok", notes=None):
    conn = get_connection()
    c = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("""
        INSERT INTO club_pricing (club_slug, pricing_json, raw_html, scraped_at, status, notes)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (club_slug) DO UPDATE SET
            pricing_json = EXCLUDED.pricing_json,
            raw_html = EXCLUDED.raw_html,
            scraped_at = EXCLUDED.scraped_at,
            status = EXCLUDED.status,
            notes = EXCLUDED.notes
    """, (club_slug, pricing_json, raw_html, now, status, notes))
    conn.commit()
    conn.close()


def get_club_pricing(club_slug):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM club_pricing WHERE club_slug = %s", (club_slug,))
    row = _dictrow(c)
    conn.close()
    return row


def get_all_club_pricing():
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT club_slug, status, scraped_at, notes FROM club_pricing ORDER BY club_slug")
    rows = _dictrows(c)
    conn.close()
    return rows
