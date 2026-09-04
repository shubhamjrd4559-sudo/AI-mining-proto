"""
SIH26023 — Storage Abstraction
Provides a pluggable storage interface for file operations.
Phase 1: Local filesystem storage.
Future: S3-compatible object storage.
"""

import os
import shutil
import uuid
from abc import ABC, abstractmethod
from pathlib import Path

from django.conf import settings


class BaseStorage(ABC):
    """Abstract base class for file storage backends."""

    @abstractmethod
    def save(self, file_obj, filename=None, subdir=""):
        """
        Save a file and return a storage key (relative path or object key).

        Args:
            file_obj: File-like object to save.
            filename: Optional filename. If None, a UUID-based name is generated.
            subdir: Optional subdirectory within the storage root.

        Returns:
            str: Storage key that can be used with retrieve/delete/exists/url.
        """
        pass

    @abstractmethod
    def retrieve(self, storage_key):
        """
        Retrieve a file by its storage key.

        Args:
            storage_key: The key returned by save().

        Returns:
            File path or file-like object depending on backend.
        """
        pass

    @abstractmethod
    def delete(self, storage_key):
        """
        Delete a file by its storage key.

        Args:
            storage_key: The key returned by save().

        Returns:
            bool: True if deleted, False if not found.
        """
        pass

    @abstractmethod
    def exists(self, storage_key):
        """
        Check if a file exists.

        Args:
            storage_key: The key returned by save().

        Returns:
            bool: True if the file exists.
        """
        pass

    @abstractmethod
    def url(self, storage_key):
        """
        Get a URL or path for accessing the file.

        Args:
            storage_key: The key returned by save().

        Returns:
            str: URL or file path.
        """
        pass


class LocalStorage(BaseStorage):
    """
    Local filesystem storage backend.
    Stores files under MEDIA_ROOT.
    """

    def __init__(self, base_dir=None):
        self.base_dir = Path(base_dir or getattr(settings, 'MEDIA_ROOT', 'media'))
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _resolve_path(self, storage_key):
        """Resolve a storage key to an absolute file path."""
        return self.base_dir / storage_key

    def _generate_key(self, filename, subdir=""):
        """Generate a unique storage key to avoid filename collisions."""
        ext = Path(filename).suffix if filename else ""
        unique_name = f"{uuid.uuid4().hex}{ext}"
        if subdir:
            return str(Path(subdir) / unique_name)
        return unique_name

    def save(self, file_obj, filename=None, subdir=""):
        storage_key = self._generate_key(filename or "upload", subdir)
        file_path = self._resolve_path(storage_key)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        with open(file_path, 'wb') as dest:
            if hasattr(file_obj, 'read'):
                shutil.copyfileobj(file_obj, dest)
            elif isinstance(file_obj, (bytes, bytearray)):
                dest.write(file_obj)
            else:
                dest.write(file_obj)

        return storage_key

    def retrieve(self, storage_key):
        file_path = self._resolve_path(storage_key)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {storage_key}")
        return str(file_path)

    def delete(self, storage_key):
        file_path = self._resolve_path(storage_key)
        if file_path.exists():
            file_path.unlink()
            return True
        return False

    def exists(self, storage_key):
        return self._resolve_path(storage_key).exists()

    def url(self, storage_key):
        media_url = getattr(settings, 'MEDIA_URL', '/media/')
        return f"{media_url}{storage_key}"


def get_storage(backend=None):
    """
    Factory function to get the configured storage backend.

    Args:
        backend: Optional override. Defaults to settings or 'local'.

    Returns:
        BaseStorage instance.
    """
    backend = backend or getattr(settings, 'STORAGE_BACKEND', 'local')

    if backend == 'local':
        return LocalStorage()
    # Future: add 's3' case here
    # elif backend == 's3':
    #     return S3Storage()
    else:
        raise ValueError(f"Unknown storage backend: {backend}")
