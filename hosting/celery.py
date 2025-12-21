import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hosting.settings')

app = Celery('hosting')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

# Periodic tasks
app.conf.beat_schedule = {
    'check-renewals-daily': {
        'task': 'core.tasks.check_service_renewals',
        'schedule': crontab(hour=0, minute=0),  # Daily at midnight
    },
    'check-suspended-services': {
        'task': 'core.tasks.check_suspended_services',
        'schedule': crontab(hour='*/6'),  # Every 6 hours
    },
}