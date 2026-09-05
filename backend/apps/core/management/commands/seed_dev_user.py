"""
Management command: seed_dev_user

Creates (or updates) a development/demo superuser from environment variables.
Safe to run multiple times — idempotent.

Usage:
    python manage.py seed_dev_user

Required environment variables (set in .env):
    DEV_USER_USERNAME   — e.g. admin
    DEV_USER_PASSWORD   — e.g. a strong local password
    DEV_USER_EMAIL      — e.g. admin@cmpdi.local  (optional, has sensible default)

The command aborts if DEV_USER_USERNAME or DEV_USER_PASSWORD are unset,
so no predictable default credentials can be silently created.
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

_UNSET = object()   # sentinel to detect truly missing values


class Command(BaseCommand):
    help = 'Create or update the development demo superuser from env vars.'

    def handle(self, *args, **options):
        User = get_user_model()

        username = getattr(settings, 'DEV_USER_USERNAME', _UNSET)
        password = getattr(settings, 'DEV_USER_PASSWORD', _UNSET)
        email    = getattr(settings, 'DEV_USER_EMAIL', 'admin@cmpdi.local')

        # Require both credentials to be explicitly configured — no silent defaults
        missing = []
        if username is _UNSET or not str(username).strip():
            missing.append('DEV_USER_USERNAME')
        if password is _UNSET or not str(password).strip():
            missing.append('DEV_USER_PASSWORD')

        if missing:
            raise CommandError(
                f"[seed_dev_user] Missing required environment variable(s): "
                f"{', '.join(missing)}. "
                f"Set them in your .env file and re-run. "
                f"Example: DEV_USER_USERNAME=admin  DEV_USER_PASSWORD=<choose-a-password>"
            )

        username = str(username).strip()
        password = str(password).strip()

        user, created = User.objects.get_or_create(
            username=username,
            defaults={'email': email, 'is_staff': True, 'is_superuser': True},
        )

        if created:
            user.set_password(password)
            user.save()
            self.stdout.write(
                self.style.SUCCESS(
                    f'[seed_dev_user] Created superuser: username="{username}"'
                )
            )
        else:
            # Update password to match env (useful after rotating DEV_USER_PASSWORD)
            user.set_password(password)
            user.is_staff = True
            user.is_superuser = True
            user.save(update_fields=['password', 'is_staff', 'is_superuser'])
            self.stdout.write(
                self.style.WARNING(
                    f'[seed_dev_user] Updated existing user: username="{username}"'
                )
            )

