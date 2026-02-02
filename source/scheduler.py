"""
APScheduler-based job management for daily verse sending.
"""
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

scheduler = AsyncIOScheduler()

def setup_user_schedule(user_id: str, time: str, timezone: str, send_verse_callback):
    """
    Creates daily job for user.
    
    Args:
        user_id: Discord user ID
        time: Time in HH:MM format
        timezone: Timezone string (e.g., 'America/New_York')
        send_verse_callback: Async function to send verse
    """
    try:
        # Parse time
        hour, minute = map(int, time.split(':'))
        
        # Create timezone-aware cron trigger
        tz = pytz.timezone(timezone)
        trigger = CronTrigger(hour=hour, minute=minute, timezone=tz)
        
        # Remove existing job if it exists
        job_id = f"daily_verse_{user_id}"
        if scheduler.get_job(job_id):
            scheduler.remove_job(job_id)
        
        # Add new job
        scheduler.add_job(
            send_verse_callback,
            trigger=trigger,
            args=[user_id],
            id=job_id,
            replace_existing=True
        )
        print(f"Scheduled daily verse for user {user_id} at {time} {timezone}")
        return True
    except Exception as e:
        print(f"Error setting up schedule for user {user_id}: {e}")
        return False

def remove_user_schedule(user_id: str):
    """Removes existing schedule for user."""
    try:
        job_id = f"daily_verse_{user_id}"
        if scheduler.get_job(job_id):
            scheduler.remove_job(job_id)
            print(f"Removed schedule for user {user_id}")
            return True
        return False
    except Exception as e:
        print(f"Error removing schedule for user {user_id}: {e}")
        return False

def load_all_schedules(users_data: dict, send_verse_callback):
    """
    Loads all user schedules on bot startup.
    
    Args:
        users_data: Dictionary of user settings from storage
        send_verse_callback: Async function to send verse
    """
    count = 0
    for user_id, settings in users_data.items():
        time = settings.get('scheduled_time')
        timezone = settings.get('timezone', 'America/New_York')
        if time:
            if setup_user_schedule(user_id, time, timezone, send_verse_callback):
                count += 1
    print(f"Loaded {count} user schedules")

def start_scheduler():
    """Start the scheduler."""
    if not scheduler.running:
        scheduler.start()
        print("Scheduler started")
