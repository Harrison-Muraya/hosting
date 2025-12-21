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
        'schedule': crontab(hour=0, minute=0),
    },
    'check-suspended-services': {
        'task': 'core.tasks.check_suspended_services',
        'schedule': crontab(hour='*/6'),
    },
}

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')