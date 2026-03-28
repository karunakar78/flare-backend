import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

app = Celery("flare")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()


@app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    from apps.rooms.tasks import check_empty_rooms
    sender.add_periodic_task(
        60.0,
        check_empty_rooms.s(),
        name="check-empty-rooms-every-minute",
    )