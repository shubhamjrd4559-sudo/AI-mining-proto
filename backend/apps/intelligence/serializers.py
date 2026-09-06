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

    def validate(self, attrs):
        query = attrs.get('message') or attrs.get('question')
        if not query or not query.strip():
            raise serializers.ValidationError('Query text cannot be empty.')
        if len(query.strip()) > 1000:
            raise serializers.ValidationError('Query text exceeds maximum length of 1000 characters.')
        attrs['query'] = query.strip()
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
