"""
Management command to index or re-index documents for RAG Mining Intelligence.

Usage:
  python manage.py reindex_documents
  python manage.py reindex_documents --force
  python manage.py reindex_documents --document-id 5
"""

from django.core.management.base import BaseCommand
from apps.documents.models import Document
from apps.intelligence.indexing.indexer import index_document, reindex_all_documents


class Command(BaseCommand):
    help = 'Indexes processed documents into RAG DocumentChunks for natural language retrieval.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force re-indexing even if document fingerprint has not changed.',
        )
        parser.add_argument(
            '--document-id',
            type=int,
            help='Index a specific document by its ID.',
        )

    def handle(self, *args, **options):
        force = options.get('force', False)
        doc_id = options.get('document_id')

        if doc_id:
            self.stdout.write(f'Indexing document ID {doc_id} (force={force})...')
            chunks, err = index_document(doc_id, force=force)
            if err:
                self.stderr.write(self.style.ERROR(f'Failed: {err}'))
            else:
                self.stdout.write(self.style.SUCCESS(f'Successfully indexed document {doc_id} into {chunks} chunks.'))
            return

        self.stdout.write('Indexing all eligible processed documents...')
        docs_indexed, chunks_created = reindex_all_documents(force=force)
        self.stdout.write(
            self.style.SUCCESS(
                f'Complete. Indexed {docs_indexed} document(s) creating {chunks_created} total chunk(s).'
            )
        )
