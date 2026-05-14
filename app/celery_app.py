import os
from celery import Celery
from celery.schedules import crontab

redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

celery_app = Celery('zametki_worker', broker=redis_url, backend=redis_url, include=['app.tasks'])

celery_app.conf.update(
    task_serializer='json',
    result_serializer='json',
    accept_content=['json'],
    timezone='UTC',
    enable_utc=True,
)

celery_app.conf.beat_schedule = {
    'daily-morning-summary': {
        'task': 'app.tasks.daily_summary',
        'schedule': crontab(hour=7, minute=0),  # Каждое утро в 7:00 UTC
    },
    'check-reminders-every-minute': {
        'task': 'app.tasks.check_reminders',
        'schedule': 3.0,  # Каждые 3 секунды для тестов, в проде можно поставить crontab(minute='*/1') для проверки каждую минуту
    },
}
