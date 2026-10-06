"""
apps.intelligence — Serializers for Query API and History.
"""

from rest_framework import serializers
from .models import AIQueryLog


class AIQueryInputSerializer(serializers.Serializer):
    message = serializers.CharField(
        max_length=1000,
        required=False,
        allow_blank=True,
        help_text='Natural language query (compatible with chat endpoint).',
    )
    question = serializers.CharField(
        max_length=1000,
        required=False,
        allow_blank=True,
        help_text='Alternative field for question.',
    )
    context = serializers.DictField(
        required=False,
        default=dict,
        help_text='Optional query context parameters.',
    )

    document_id = serializers.IntegerField(
        required=False,
        allow_null=True,
        help_text='Optional ID of specific document to restrict query to.',
    )

    def validate(self, attrs):
        query = attrs.get('message') or attrs.get('question')
        if not query or not query.strip():
            raise serializers.ValidationError('Query text cannot be empty.')
        if len(query.strip()) > 1000:
            raise serializers.ValidationError('Query text exceeds maximum length of 1000 characters.')
        attrs['query'] = query.strip()

        # Extract document_id from top-level field or context dict
        doc_id = attrs.get('document_id')
        if doc_id is None:
            ctx = attrs.get('context') or {}
            raw_id = ctx.get('document_id')
            if raw_id is not None:
                try:
                    doc_id = int(raw_id)
                except (TypeError, ValueError):
                    doc_id = None
        attrs['document_id'] = doc_id
        return attrs


class AIQueryLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AIQueryLog
        fields = [
            'id',
            'question',
            'query_type',
            'answer',
            'confidence',
            'sources',
            'evidence_count',
            'source_count',
            'created_at',
        ]
        read_only_fields = fields
