"""
apps.storage — StorageService

A singleton-like service that provides the active storage backend
based on the STORAGE_BACKEND setting.

Usage:
    from apps.storage.service import get_storage_service

    storage = get_storage_service()
    storage.save('uploads/file.pdf', file_bytes)
"""

import logging
from django.conf import settings
from .backends import StorageBackend, LocalStorageBackend

logger = logging.getLogger(__name__)

_storage_instance: StorageBackend | None = None


def get_storage_service() -> StorageBackend:
    """
    Return the configured storage backend instance.

    Backend is determined by settings.STORAGE_BACKEND:
      'local' → LocalStorageBackend (default, Phase 1-2)
      's3'    → S3StorageBackend (Phase 5, not yet implemented)

    The instance is cached after the first call.
    """
    global _storage_instance

    if _storage_instance is None:
        backend = getattr(settings, 'STORAGE_BACKEND', 'local')

        if backend == 'local':
            _storage_instance = LocalStorageBackend()
            logger.info('Storage service: using LocalStorageBackend')
        else:
            raise NotImplementedError(
                f'Storage backend {backend!r} is not yet implemented. '
                f'Available: "local". S3 support arrives in Phase 5.'
            )

    return _storage_instance


def reset_storage_service() -> None:
    """
    Reset the cached storage instance.
    Used in tests to ensure isolation.
    """
    global _storage_instance
    _storage_instance = None
