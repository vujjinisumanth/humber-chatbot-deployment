import time
import threading
import traceback
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler

from scraper import run_fulltime, run_cpl


RUN_ON_START = False
MONTHLY_DAY = 1
MONTHLY_HOUR = 2
MONTHLY_MINUTE = 0

scheduler = BackgroundScheduler()


def scrape_job():
    started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n[SCRAPER] Monthly job started at {started_at}")

    try:
        run_fulltime()
        run_cpl()
        finished_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[SCRAPER] Monthly job finished successfully at {finished_at}")
    except Exception as e:
        failed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[SCRAPER] Monthly job failed at {failed_at}")
        print(f"[SCRAPER] Error: {e}")
        traceback.print_exc()


def start_scheduler():
    print("[SCHEDULER] Starting monthly scheduler...")

    if RUN_ON_START:
        scrape_job()

    if not scheduler.running:
        scheduler.add_job(
            scrape_job,
            trigger="cron",
            day=MONTHLY_DAY,
            hour=MONTHLY_HOUR,
            minute=MONTHLY_MINUTE,
            id="monthly_humber_scrape",
            replace_existing=True,
            max_instances=1,
        )
        scheduler.start()

    print(
        f"[SCHEDULER] Monthly scrape scheduled for day {MONTHLY_DAY} "
        f"at {MONTHLY_HOUR:02d}:{MONTHLY_MINUTE:02d}"
    )

    try:
        while True:
            time.sleep(30)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()


def start_scheduler_thread():
    t = threading.Thread(target=start_scheduler, daemon=True)
    t.start()
    print("[SCHEDULER] Background monthly scheduler thread started")
    return t


if __name__ == "__main__":
    start_scheduler()