"""
Minimal Celery application stub — expanded fully in Phase 2.
"""
import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("warehouse")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
