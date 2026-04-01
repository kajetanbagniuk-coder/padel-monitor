"""
Standalone scrape script for PythonAnywhere scheduled tasks.
Run this via PythonAnywhere's task scheduler (daily at 23:30).
It scrapes today's and tomorrow's data for all clubs.
"""
import sys
import os

# Ensure project directory is in path
project_dir = os.path.dirname(os.path.abspath(__file__))
if project_dir not in sys.path:
    sys.path.insert(0, project_dir)

from datetime import datetime, timedelta
from database import init_db
from scraper import scrape_date
from clubs import CLUBS

def run_scrape():
    init_db()
    today = datetime.now()
    tomorrow = today + timedelta(days=1)

    success = 0
    errors = 0

    for club_slug in CLUBS:
        for date in [today, tomorrow]:
            date_str = date.strftime("%Y-%m-%d")
            try:
                result = scrape_date(date_str, club_slug)
                if result:
                    print(f"OK  {club_slug} {date_str}: {result['total_booked']} booked, {result['total_income']:.2f} PLN")
                    success += 1
                else:
                    print(f"FAIL {club_slug} {date_str}: no result")
                    errors += 1
            except Exception as e:
                print(f"ERR {club_slug} {date_str}: {e}")
                errors += 1

    print(f"\nDone: {success} ok, {errors} errors")

if __name__ == "__main__":
    run_scrape()
