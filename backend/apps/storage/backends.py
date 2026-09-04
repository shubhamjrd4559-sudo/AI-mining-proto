"""
apps.storage — Storage Backend Abstraction

Provides a clean interface for file storage operations that allows swapping
between local filesystem storage and S3-compatible object storage without
changing application business logic.

Current Phase 1 implementation: LocalStorageBackend (filesystem).
Future Phase 5: S3StorageBackend with identical interface.

Usage:
    from apps.storage.service import get_storage_service

    storage = get_storage_service()
    storage.save('documents/2026/report.pdf', file_content)
    url = storage.url('documents/2026/report.pdf')
    exists = storage.exists('documents/2026/report.pdf')
    storage.delete('documents/2026/report.pdf')
"""

import os
import logging
from abc import ABC, abstractmethod
from pathlib import Path

from django.conf import settings

logger = logging.getLogger(__name__)


class StorageBackend(ABC):
    """
    Abstract base class defining the storage interface.

    All storage backends must implement these methods.
    This ensures application code is backend-agnostic.
    """

    @abstractmethod
    def save(self, name: str, content: bytes) -> str:
        """
        Save content to storage at the given path name.
        Returns the final storage path/key.
        """

    @abstractmethod
    def open(self, name: str) -> bytes:
        """
        Open and return the content at the given path name.
        Raises FileNotFoundError if not found.
        """

    @abstractmethod
    def delete(self, name: str) -> None:
        """
        Delete the file at the given path name.
        Does not raise if the file does not exist.
        """

    @abstractmethod
    def exists(self, name: str) -> bool:
        """Return True if the given path name exists in storage."""

    @abstractmethod
    def url(self, name: str) -> str:
        """Return a URL for accessing the file at the given path name."""

    @abstractmethod
    def size(self, name: str) -> int:
        """Return the size in bytes of the file at the given path name."""

    @abstractmethod
    def list(self, prefix: str = '') -> list[str]:
        """List all files under the given prefix."""


class LocalStorageBackend(StorageBackend):
    """
    Local filesystem storage backend.

    Stores files under settings.MEDIA_ROOT.
    Used for Phase 1 and 2 (development and initial production).

    To migrate to S3 in Phase 5:
      1. Create S3StorageBackend(StorageBackend) with identical interface.
      2. Change STORAGE_BACKEND env var to 's3'.
      3. No application business logic changes required.
    """

    def __init__(self, root: str | None = None):
        self.root = Path(root or settings.MEDIA_ROOT)
        self.root.mkdir(parents=True, exist_ok=True)
        logger.debug('LocalStorageBackend initialised at: %s', self.root)

    def _full_path(self, name: str) -> Path:
        """Resolve a storage name to an absolute filesystem path."""
        # Security: prevent path traversal attacks
        resolved = (self.root / name).resolve()
        if not str(resolved).startswith(str(self.root.resolve())):
            raise ValueError(f'Path traversal detected: {name!r}')
        return resolved

    def save(self, name: str, content: bytes) -> str:
        """Save bytes to disk, creating parent directories as needed."""
        path = self._full_path(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        logger.info('Saved file: %s (%d bytes)', name, len(content))
        return name

    def open(self, name: str) -> bytes:
        """Read and return file contents as bytes."""
        path = self._full_path(name)
        if not path.exists():
            raise FileNotFoundError(f'File not found in storage: {name!r}')
        return path.read_bytes()

    def delete(self, name: str) -> None:
        """Delete a file. No-op if not found."""
        path = self._full_path(name)
        if path.exists():
            path.unlink()
            logger.info('Deleted file: %s', name)

    def exists(self, name: str) -> bool:
        """Check if a file exists."""
        try:
            return self._full_path(name).exists()
        except ValueError:
            return False

    def url(self, name: str) -> str:
        """Return the URL to access the file via Django's MEDIA_URL."""
        return f'{settings.MEDIA_URL}{name}'

    def size(self, name: str) -> int:
        """Return file size in bytes."""
        path = self._full_path(name)
        if not path.exists():
            raise FileNotFoundError(f'File not found: {name!r}')
        return path.stat().st_size

    def list(self, prefix: str = '') -> list[str]:
        """List all files under prefix, returned as relative paths."""
        base = self._full_path(prefix) if prefix else self.root
        if not base.exists():
            return []
        results = []
        for path in base.rglob('*'):
            if path.is_file():
                results.append(str(path.relative_to(self.root)))
        return sorted(results)


# ============================================================
# Future stub — NOT implemented yet, structure shown for Phase 5
# ============================================================
# class S3StorageBackend(StorageBackend):
#     """
#     S3-compatible object storage backend.
#     Identical interface to LocalStorageBackend.
#     Implement in Phase 5 using boto3 or django-storages.
#     """
#     def __init__(self, bucket: str, region: str, ...): ...
#     def save(self, name, content): ...
#     def open(self, name): ...
#     def delete(self, name): ...
#     def exists(self, name): ...
#     def url(self, name): ...
#     def size(self, name): ...
#     def list(self, prefix=''): ...
