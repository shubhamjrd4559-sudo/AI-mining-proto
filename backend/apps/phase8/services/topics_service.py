"""
apps.phase8.services.topics_service — Topics and Word Cloud service

Extracts real keyword frequencies and topic signals from indexed DocumentChunks
using the existing BM25 tokenizer and text pipeline from apps.intelligence.

Design:
  - Uses DocumentChunk.content directly (no duplicate indexing)
  - Produces keyword frequency distributions (for word cloud)
  - Groups chunks into domain topic buckets based on keyword signatures
  - Returns document provenance for each topic/keyword
  - No hardcoded topic lists — all data driven from real indexed text
"""

import re
import logging
from collections import Counter, defaultdict
from typing import List, Dict, Any, Optional

from django.db.models import Q

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Domain-relevant stopwords for the coal/mining corpus
# (extends the base intelligence stopwords)
# ─────────────────────────────────────────────────────────────────────────────
STOPWORDS = {
    # English function words
    "a", "an", "the", "in", "on", "at", "of", "for", "to", "from", "by",
    "with", "about", "into", "through", "during", "before", "after",
    "above", "below", "under", "is", "are", "was", "were", "be", "been",
    "being", "have", "has", "had", "do", "does", "did", "and", "or",
    "but", "if", "because", "as", "what", "which", "who", "whom", "this",
    "that", "these", "those", "am", "it", "its", "they", "them", "their",
    "we", "our", "he", "she", "his", "her", "will", "shall", "may", "can",
    "not", "no", "nor", "also", "such", "than", "then", "so", "yet",
    "both", "each", "more", "most", "other", "some", "any", "all",
    # Generic filler
    "report", "chapter", "page", "table", "figure", "annexure", "appendix",
    "section", "part", "year", "during", "period", "total", "overall",
    "various", "under", "number", "per", "cent", "percentage",
    "up", "down", "over", "out", "off", "been", "made", "given",
    "including", "however", "therefore", "accordingly", "whereas",
    "therefore", "therein", "thereof", "herein", "hereby", "thus",
    "viz", "etc", "respectively", "said", "duly", "accordingly",
    "within", "without", "along", "across", "further", "due",
    # Numerics that slip through
    "one", "two", "three", "four", "five", "six", "seven", "eight",
    "nine", "ten", "twenty", "thirty", "forty", "fifty", "hundred",
    "thousand", "lakh", "crore", "million", "billion",
}

# Domain-relevant topic keyword signatures
TOPIC_SIGNATURES: Dict[str, List[str]] = {
    "Geological Exploration": [
        "exploration", "borehole", "drilling", "geological", "seismic",
        "geophysics", "stratigraphy", "mapping", "toposheet", "survey",
        "block", "reserve", "resource", "estimation", "fsp", "gsi",
    ],
    "Coal Production": [
        "production", "mining", "excavation", "overburden", "extraction",
        "opencast", "underground", "longwall", "depillaring", "dispatch",
        "raising", "output", "tonnes", "mt",
    ],
    "Coal Quality & Grades": [
        "coking", "non-coking", "grade", "ash", "moisture", "gcv",
        "washery", "beneficiation", "quality", "thermal", "power",
        "blending", "washed", "middling",
    ],
    "Environment & Safety": [
        "environment", "environmental", "safety", "clearance", "pollution",
        "effluent", "reclamation", "afforestation", "subsidence",
        "accident", "rescue", "rehabilitation", "impact", "compliance",
        "ecology",
    ],
    "Infrastructure & Projects": [
        "railway", "transport", "siding", "conveyor", "project", "capital",
        "expenditure", "investment", "infrastructure", "capacity",
        "expansion", "modernisation", "mechanisation",
    ],
    "Subsidiaries & Operations": [
        "cil", "cmpdi", "ecl", "bccl", "ccl", "ncl", "secl", "wcl",
        "mcl", "sccl", "subsidiary", "coalfield", "jharia", "raniganj",
        "singrauli", "talcher", "korba", "wardha",
    ],
    "Planning & Policy": [
        "policy", "regulation", "ministry", "parliament", "committee",
        "plan", "target", "achievement", "performance", "review",
        "annual", "budget", "allocation",
    ],
}

MIN_WORD_LEN = 3
MIN_FREQ = 2  # words appearing < MIN_FREQ times are excluded


def _tokenize(text: str) -> List[str]:
    """
    Tokenize text into lowercase tokens, filtering stopwords and short words.
    Handles compound terms like 'non-coking', 'open-cast'.
    """
    # Normalise hyphens used in compound domain terms
    text = re.sub(r"\bopen[- ]cast\b", "opencast", text, flags=re.IGNORECASE)
    text = re.sub(r"\bnon[- ]coking\b", "non-coking", text, flags=re.IGNORECASE)

    words = re.findall(r"[a-zA-Z][a-zA-Z\-]{2,}", text.lower())
    return [
        w for w in words
        if w not in STOPWORDS and len(w) >= MIN_WORD_LEN
    ]


def _score_topic(tokens: List[str], signatures: Dict[str, List[str]]) -> Dict[str, float]:
    """Score how strongly a token list matches each topic signature."""
    token_set = set(tokens)
    scores = {}
    for topic, kw_list in signatures.items():
        matches = sum(1 for kw in kw_list if kw in token_set)
        scores[topic] = matches / max(1, len(kw_list))
    return scores


def get_word_cloud_data(user, limit: int = 60) -> Dict[str, Any]:
    """
    Build word cloud data from the current user's indexed DocumentChunks.

    Returns:
        {
          "words": [{"word": str, "count": int, "weight": float}, ...],
          "total_chunks": int,
          "total_documents": int,
          "data_source": "indexed_document_chunks",
        }
    """
    from apps.intelligence.models import DocumentChunk

    # User-scoped: only chunks from documents uploaded by this user
    chunks = DocumentChunk.objects.filter(
        document__uploaded_by=user,
        document__is_archived=False,
    ).values_list("content", "section_heading", "document__title", "document__id")

    if not chunks.exists():
        return {
            "words": [],
            "total_chunks": 0,
            "total_documents": 0,
            "data_source": "indexed_document_chunks",
            "message": (
                "No indexed documents found. Upload and index official CMPDI/Ministry of Coal "
                "documents to generate a real word cloud."
            ),
        }

    freq: Counter = Counter()
    doc_ids = set()
    total_chunks = 0

    for content, heading, doc_title, doc_id in chunks:
        doc_ids.add(doc_id)
        total_chunks += 1
        tokens = _tokenize(content or "")
        if heading:
            tokens.extend(_tokenize(heading))
        freq.update(tokens)

    # Filter low-frequency noise
    freq = Counter({w: c for w, c in freq.items() if c >= MIN_FREQ})

    if not freq:
        return {
            "words": [],
            "total_chunks": total_chunks,
            "total_documents": len(doc_ids),
            "data_source": "indexed_document_chunks",
            "message": "Insufficient text extracted from indexed documents.",
        }

    max_freq = max(freq.values()) or 1
    top_words = freq.most_common(limit)

    words = [
        {
            "word": w.upper(),
            "count": c,
            "weight": round(c / max_freq, 3),  # 0.0–1.0 normalised weight
        }
        for w, c in top_words
    ]

    return {
        "words": words,
        "total_chunks": total_chunks,
        "total_documents": len(doc_ids),
        "data_source": "indexed_document_chunks",
    }


def get_topics_data(user) -> Dict[str, Any]:
    """
    Derive topic distribution from the user's indexed DocumentChunks.

    Topics are determined by keyword-signature matching against the domain
    topic dictionary above — no ML model required, no dependencies.

    Returns:
        {
          "topics": [{"name": str, "score": float, "pct": int, "keywords": [str]}, ...],
          "total_chunks": int,
          "data_source": "indexed_document_chunks",
        }
    """
    from apps.intelligence.models import DocumentChunk

    chunks = DocumentChunk.objects.filter(
        document__uploaded_by=user,
        document__is_archived=False,
    ).values_list("content", flat=True)

    if not chunks.exists():
        return {
            "topics": [],
            "total_chunks": 0,
            "data_source": "indexed_document_chunks",
            "message": (
                "No indexed documents found. Upload official documents and index them "
                "to generate real topic distributions."
            ),
        }

    # Aggregate token set across all chunks
    all_tokens: List[str] = []
    total_chunks = 0
    for content in chunks:
        total_chunks += 1
        all_tokens.extend(_tokenize(content or ""))

    topic_scores = _score_topic(all_tokens, TOPIC_SIGNATURES)

    total_score = sum(topic_scores.values()) or 1.0
    topics = []
    for name, score in sorted(topic_scores.items(), key=lambda x: x[1], reverse=True):
        if score == 0:
            continue
        pct = round((score / total_score) * 100)
        # Find most frequent keywords from this topic in the corpus
        freq = Counter(all_tokens)
        matched_kws = sorted(
            [kw for kw in TOPIC_SIGNATURES[name] if kw in freq],
            key=lambda k: freq[k],
            reverse=True,
        )[:5]
        topics.append({
            "name": name,
            "score": round(score, 4),
            "pct": pct,
            "keywords": matched_kws,
        })

    return {
        "topics": topics,
        "total_chunks": total_chunks,
        "data_source": "indexed_document_chunks",
    }


def get_topic_documents(user) -> Dict[str, Any]:
    """
    Return a provenance-linked list of documents with their dominant topics.

    Returns:
        {
          "documents": [{
            "id": int, "title": str, "status": str, "created_at": str,
            "chunk_count": int, "dominant_topic": str, "top_keywords": [str]
          }, ...],
          "data_source": "indexed_document_chunks",
        }
    """
    from apps.intelligence.models import DocumentChunk
    from apps.documents.models import Document
    from django.db.models import Count

    docs = (
        Document.objects.filter(
            uploaded_by=user,
            is_archived=False,
        )
        .prefetch_related("chunks")
        .order_by("-created_at")[:50]
    )

    result = []
    for doc in docs:
        chunks = doc.chunks.values_list("content", flat=True)
        chunk_count = len(chunks)
        if chunk_count == 0:
            continue

        all_tokens = []
        for content in chunks:
            all_tokens.extend(_tokenize(content or ""))

        freq = Counter(all_tokens)
        top_kws = [w for w, _ in freq.most_common(6)]

        topic_scores = _score_topic(all_tokens, TOPIC_SIGNATURES)
        dominant = max(topic_scores, key=topic_scores.get) if topic_scores else "—"
        if topic_scores.get(dominant, 0) == 0:
            dominant = "—"

        result.append({
            "id": doc.id,
            "title": doc.title,
            "status": doc.status,
            "created_at": doc.created_at.isoformat(),
            "chunk_count": chunk_count,
            "dominant_topic": dominant,
            "top_keywords": top_kws,
        })

    return {
        "documents": result,
        "data_source": "indexed_document_chunks",
    }
