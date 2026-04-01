import sqlite3
import os
from datetime import datetime, timedelta

DATA_DIR = os.environ.get("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(DATA_DIR, "padel_income.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    # Check if existing database is healthy; if corrupted, remove and recreate
    if os.path.exists(DB_PATH):
        try:
            test_conn = sqlite3.connect(DB_PATH, timeout=10)
            test_conn.execute("PRAGMA integrity_check")
            test_conn.close()
        except Exception:
            import logging
            logging.getLogger(__name__).warning(f"Database corrupted, recreating: {DB_PATH}")
            os.remove(DB_PATH)
            # Also remove WAL/SHM files if present
            for suffix in ["-wal", "-shm"]:
                path = DB_PATH + suffix
                if os.path.exists(path):
                    os.remove(path)

    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS scrape_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scraped_at TEXT NOT NULL,
            target_date TEXT NOT NULL,
            club_slug TEXT NOT NULL DEFAULT 'loba-padel'
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scrape_id INTEGER NOT NULL,
            target_date TEXT NOT NULL,
            club_slug TEXT NOT NULL DEFAULT 'loba-padel',
            court_name TEXT NOT NULL,
            slot_start TEXT NOT NULL,
            slot_end TEXT NOT NULL,
            is_booked INTEGER NOT NULL,
            booking_label TEXT,
            income REAL NOT NULL DEFAULT 0,
            FOREIGN KEY (scrape_id) REFERENCES scrape_log(id)
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS daily_snapshot (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            target_date TEXT NOT NULL,
            club_slug TEXT NOT NULL DEFAULT 'loba-padel',
            snapshot_at TEXT NOT NULL,
            total_booked_slots INTEGER NOT NULL,
            total_income REAL NOT NULL,
            courts_data TEXT NOT NULL
        )
    """)
    # Migrate: add club_slug column if missing (existing databases)
    for table in ["scrape_log", "bookings", "daily_snapshot"]:
        try:
            c.execute(f"ALTER TABLE {table} ADD COLUMN club_slug TEXT NOT NULL DEFAULT 'loba-padel'")
        except sqlite3.OperationalError:
            pass  # column already exists

    c.execute("""
        CREATE TABLE IF NOT EXISTS club_pricing (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            club_slug TEXT NOT NULL UNIQUE,
            pricing_json TEXT NOT NULL,
            raw_html TEXT,
            scraped_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'ok',
            notes TEXT
        )
    """)

    # Playtomic hourly observations: one row per court per hour, upserted each :45 scrape
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
    c.execute("CREATE INDEX IF NOT EXISTS idx_bookings_date_club ON bookings(target_date, club_slug)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_snapshot_date_club ON daily_snapshot(target_date, club_slug)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_ptobs_date_club ON playtomic_observations(target_date, club_slug)")
    conn.commit()
    conn.close()


def save_scrape(target_date, slots, club_slug="loba-padel"):
    conn = get_connection()
    c = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("INSERT INTO scrape_log (scraped_at, target_date, club_slug) VALUES (?, ?, ?)",
              (now, target_date, club_slug))
    scrape_id = c.lastrowid
    for s in slots:
        c.execute("""
            INSERT INTO bookings (scrape_id, target_date, club_slug, court_name, slot_start, slot_end, is_booked, booking_label, income)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        VALUES (?, ?, ?, ?, ?, ?)
    """, (target_date, club_slug, now, total_booked, total_income, courts_json))
    conn.commit()
    conn.close()


def get_latest_snapshot_for_date(target_date, club_slug="loba-padel"):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT * FROM daily_snapshot WHERE target_date = ? AND club_slug = ? ORDER BY snapshot_at DESC LIMIT 1
    """, (target_date, club_slug))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def get_income_range(start_date, end_date, club_slug="loba-padel"):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT target_date, MAX(snapshot_at) as latest, total_income
        FROM daily_snapshot
        WHERE target_date >= ? AND target_date <= ? AND club_slug = ?
        GROUP BY target_date
    """, (start_date, end_date, club_slug))
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_snapshots_for_date(target_date, club_slug="loba-padel"):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT * FROM daily_snapshot WHERE target_date = ? AND club_slug = ? ORDER BY snapshot_at ASC
    """, (target_date, club_slug))
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_aggregated_daily(target_date, city=None):
    """Get aggregated income across all clubs for a single date.

    For each club, takes the latest snapshot for that date.
    If city is provided, only includes clubs in that city.
    Returns list of per-club results plus grand totals.
    """
    from clubs import CLUBS
    conn = get_connection()
    c = conn.cursor()

    # Get latest snapshot per club for this date
    c.execute("""
        SELECT club_slug, total_income, total_booked_slots
        FROM daily_snapshot ds1
        WHERE target_date = ?
          AND snapshot_at = (
              SELECT MAX(ds2.snapshot_at)
              FROM daily_snapshot ds2
              WHERE ds2.target_date = ds1.target_date
                AND ds2.club_slug = ds1.club_slug
          )
    """, (target_date,))
    rows = c.fetchall()
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

    return {
        "clubs": clubs,
        "total_income": total_income,
        "total_booked": total_booked,
    }


def get_aggregated_range(start_date, end_date, city=None):
    """Get aggregated income across all clubs for a date range.

    For each club, sums the latest-per-day income across the range.
    Returns per-club totals and grand total.
    """
    from clubs import CLUBS
    conn = get_connection()
    c = conn.cursor()

    # For each club+date, get the latest snapshot, then sum per club
    c.execute("""
        SELECT club_slug, SUM(total_income) as total_income
        FROM (
            SELECT ds1.club_slug, ds1.target_date, ds1.total_income
            FROM daily_snapshot ds1
            WHERE ds1.target_date >= ? AND ds1.target_date <= ?
              AND ds1.snapshot_at = (
                  SELECT MAX(ds2.snapshot_at)
                  FROM daily_snapshot ds2
                  WHERE ds2.target_date = ds1.target_date
                    AND ds2.club_slug = ds1.club_slug
              )
        )
        GROUP BY club_slug
    """, (start_date, end_date))
    rows = c.fetchall()
    conn.close()

    clubs = []
    total_income = 0
    for row in rows:
        slug = row["club_slug"]
        if slug not in CLUBS:
            continue
        if city and CLUBS[slug]["city"] != city:
            continue
        clubs.append({
            "club_slug": slug,
            "total_income": row["total_income"],
        })
        total_income += row["total_income"]

    return {
        "clubs": clubs,
        "total_income": total_income,
    }


def save_playtomic_observations(target_date, club_slug, observations):
    """Upsert hourly observations for a Playtomic club.

    observations: list of dicts with keys: court_name, hour, is_booked, price
    """
    conn = get_connection()
    c = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for obs in observations:
        c.execute("""
            INSERT INTO playtomic_observations (target_date, club_slug, court_name, hour, is_booked, price, observed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(target_date, club_slug, court_name, hour) DO UPDATE SET
                is_booked=excluded.is_booked,
                price=excluded.price,
                observed_at=excluded.observed_at
        """, (target_date, club_slug, obs["court_name"], obs["hour"],
              1 if obs["is_booked"] else 0, obs["price"], now))
    conn.commit()
    conn.close()


def get_playtomic_daily_summary(target_date, club_slug):
    """Build daily summary from accumulated hourly observations."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT court_name, hour, is_booked, price
        FROM playtomic_observations
        WHERE target_date = ? AND club_slug = ?
        ORDER BY court_name, hour
    """, (target_date, club_slug))
    rows = c.fetchall()
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

    return {
        "total_booked": total_booked,
        "total_income": total_income,
        "courts_summary": courts_summary,
    }


def save_club_pricing(club_slug, pricing_json, raw_html, status="ok", notes=None):
    conn = get_connection()
    c = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("""
        INSERT INTO club_pricing (club_slug, pricing_json, raw_html, scraped_at, status, notes)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(club_slug) DO UPDATE SET
            pricing_json=excluded.pricing_json,
            raw_html=excluded.raw_html,
            scraped_at=excluded.scraped_at,
            status=excluded.status,
            notes=excluded.notes
    """, (club_slug, pricing_json, raw_html, now, status, notes))
    conn.commit()
    conn.close()


def get_club_pricing(club_slug):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM club_pricing WHERE club_slug = ?", (club_slug,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def get_all_club_pricing():
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT club_slug, status, scraped_at, notes FROM club_pricing ORDER BY club_slug")
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]
