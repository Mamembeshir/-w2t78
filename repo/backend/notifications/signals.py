"""
notifications/signals.py — Auto-provision DigestSchedule on user creation.

Every new user gets a DigestSchedule row with the default 18:00 send time
so they receive the 6 PM daily digest without needing to visit the settings
endpoint first (SPEC: "6:00 PM daily").
"""
from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_digest_schedule(sender, instance, created, **kwargs):
    if not created:
        return
    from .models import DigestSchedule
    DigestSchedule.objects.get_or_create(user=instance)
