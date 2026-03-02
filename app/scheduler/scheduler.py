import os

from apscheduler.schedulers.background import BackgroundScheduler
from app.pipeline.scan_pipeline import run_daily_scan
from app.utils.config import settings


def start_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(run_daily_scan, 'cron', hour=settings.schedule_hour, minute=settings.schedule_minute)
    if os.getenv("ENV") == "production":
        scheduler.start()
    return scheduler
