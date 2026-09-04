"""
apps.storage — Tests
"""

import tempfile
from pathlib import Path
from django.test import TestCase, override_settings
from .backends import LocalStorageBackend


class LocalStorageBackendTestCase(TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.backend = LocalStorageBackend(root=self.tmpdir)

    def test_save_and_open(self):
        """Saved content can be retrieved."""
        content = b'Hello, CMPDI AI!'
        name = 'test/sample.txt'
        self.backend.save(name, content)
        retrieved = self.backend.open(name)
        self.assertEqual(retrieved, content)

    def test_exists_true(self):
        """exists() returns True for saved files."""
        self.backend.save('doc.pdf', b'%PDF-1.4')
        self.assertTrue(self.backend.exists('doc.pdf'))

    def test_exists_false(self):
        """exists() returns False for missing files."""
        self.assertFalse(self.backend.exists('missing.pdf'))

    def test_delete(self):
        """Deleted files no longer exist."""
        self.backend.save('to_delete.txt', b'data')
        self.backend.delete('to_delete.txt')
        self.assertFalse(self.backend.exists('to_delete.txt'))

    def test_delete_nonexistent_no_error(self):
        """Deleting a non-existent file does not raise."""
        self.backend.delete('nonexistent.txt')  # Should not raise

    def test_size(self):
        """size() returns correct byte count."""
        content = b'A' * 100
        self.backend.save('sized.bin', content)
        self.assertEqual(self.backend.size('sized.bin'), 100)

    def test_list(self):
        """list() returns all saved files."""
        self.backend.save('a/file1.txt', b'1')
        self.backend.save('a/file2.txt', b'2')
        self.backend.save('b/file3.txt', b'3')
        files = self.backend.list()
        self.assertEqual(len(files), 3)

    def test_path_traversal_prevention(self):
        """Path traversal attacks are blocked."""
        with self.assertRaises(ValueError):
            self.backend.save('../../etc/passwd', b'attack')

    def test_url_format(self):
        """url() returns MEDIA_URL-prefixed path."""
        url = self.backend.url('documents/report.pdf')
        self.assertIn('documents/report.pdf', url)

    def test_open_missing_raises(self):
        """open() raises FileNotFoundError for missing files."""
        with self.assertRaises(FileNotFoundError):
            self.backend.open('does_not_exist.pdf')
