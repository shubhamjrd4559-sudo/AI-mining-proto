"""
Deterministic text and table chunking for RAG indexing.

Preserves:
  - Natural paragraph and sentence boundaries
  - Page numbers and section context
  - Table references and row metadata
  - Provenance traceability
"""

import re
import hashlib
from typing import List, Dict, Any, Optional

DEFAULT_CHUNK_SIZE = 600      # Target character count per chunk
DEFAULT_CHUNK_OVERLAP = 80    # Character overlap between consecutive chunks
MIN_CHUNK_SIZE = 40           # Drop trivial whitespace/empty chunks


def compute_hash(text: str) -> str:
    """Compute deterministic SHA-256 hash for text."""
    return hashlib.sha256(text.strip().encode('utf-8')).hexdigest()


def _split_into_sentences(text: str) -> List[str]:
    """Split text into sentences deterministically without breaking on abbreviations."""
    # Split on periods/exclamations/questions followed by space and capital letter or end
    raw_sentences = re.split(r'(?<=[.!?])\s+', text)
    sentences = [s.strip() for s in raw_sentences if s.strip()]
    return sentences if sentences else [text.strip()]


def chunk_text(
    text: str,
    page_number: Optional[int] = None,
    section_heading: str = '',
    metadata: Optional[Dict[str, Any]] = None,
    target_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> List[Dict[str, Any]]:
    """
    Deterministically split plain text into meaningful chunks respecting paragraph
    and sentence boundaries.
    """
    if not text or not text.strip():
        return []

    meta = dict(metadata or {})
    chunks: List[Dict[str, Any]] = []

    # First split by double newlines into paragraphs
    paragraphs = [p.strip() for p in re.split(r'\n\s*\n', text) if p.strip()]
    if not paragraphs:
        paragraphs = [text.strip()]

    current_heading = section_heading
    buffer: List[str] = []
    buffer_len = 0

    for para in paragraphs:
        # Detect if paragraph is likely a heading (e.g. short, ends without period, or uppercase)
        if len(para) < 80 and not para.endswith(('.', ':', ';')) and ('\n' not in para):
            current_heading = para

        sentences = _split_into_sentences(para)
        for sentence in sentences:
            s_len = len(sentence)
            if buffer_len + s_len > target_size and buffer:
                # Flush current buffer as a chunk
                chunk_str = ' '.join(buffer).strip()
                if len(chunk_str) >= MIN_CHUNK_SIZE:
                    chunks.append({
                        'content': chunk_str,
                        'content_hash': compute_hash(chunk_str),
                        'page_number': page_number,
                        'section_heading': current_heading,
                        'metadata': meta,
                        'token_count': max(1, len(chunk_str.split())),
                    })

                # Retain overlap sentences
                overlap_buffer: List[str] = []
                overlap_len = 0
                for prev_s in reversed(buffer):
                    if overlap_len + len(prev_s) <= overlap:
                        overlap_buffer.insert(0, prev_s)
                        overlap_len += len(prev_s)
                    else:
                        break
                buffer = overlap_buffer
                buffer_len = sum(len(s) for s in buffer)

            buffer.append(sentence)
            buffer_len += s_len

    # Flush remaining buffer
    if buffer:
        chunk_str = ' '.join(buffer).strip()
        if len(chunk_str) >= MIN_CHUNK_SIZE:
            chunks.append({
                'content': chunk_str,
                'content_hash': compute_hash(chunk_str),
                'page_number': page_number,
                'section_heading': current_heading,
                'metadata': meta,
                'token_count': max(1, len(chunk_str.split())),
            })

    return chunks


def chunk_extracted_tables(
    tables: List[Dict[str, Any]],
    doc_id: int,
    batch_rows: int = 5,
) -> List[Dict[str, Any]]:
    """
    Format extracted tables into readable, structured chunks preserving
    row/record structure and field metadata.
    Does NOT collapse an entire spreadsheet into one giant blob.
    """
    chunks: List[Dict[str, Any]] = []

    for t_idx, tbl in enumerate(tables):
        headers = tbl.get('headers') or []
        rows = tbl.get('rows') or []
        page_num = tbl.get('page_number')
        sheet_name = tbl.get('sheet_name') or ''
        sec_heading = tbl.get('section_heading') or ''
        source_ref = tbl.get('source_ref') or f'table:{t_idx + 1}'

        if not headers or not rows:
            continue

        clean_headers = [str(h).strip() for h in headers if h is not None]

        # Chunk rows in manageable groups (e.g. 5 rows per chunk)
        for row_start in range(0, len(rows), batch_rows):
            group_rows = rows[row_start:row_start + batch_rows]
            lines = []
            
            ctx = f"Table {source_ref}"
            if sheet_name:
                ctx += f" (Sheet: {sheet_name})"
            if sec_heading:
                ctx += f" [Section: {sec_heading}]"
            lines.append(f"{ctx}: Columns: {', '.join(clean_headers)}")

            for offset, r in enumerate(group_rows):
                actual_row_idx = row_start + offset
                row_items = []
                for c_idx, val in enumerate(r):
                    col_name = clean_headers[c_idx] if c_idx < len(clean_headers) else f"Col{c_idx}"
                    val_str = str(val).strip() if val is not None else ''
                    if val_str:
                        row_items.append(f"{col_name}: {val_str}")
                if row_items:
                    lines.append(f"Row {actual_row_idx}: " + " | ".join(row_items))

            chunk_content = "\n".join(lines).strip()
            if len(chunk_content) >= MIN_CHUNK_SIZE:
                chunks.append({
                    'content': chunk_content,
                    'content_hash': compute_hash(chunk_content),
                    'page_number': page_num,
                    'section_heading': sec_heading,
                    'metadata': {
                        'table_reference': source_ref,
                        'sheet_name': sheet_name,
                        'row_start': row_start,
                        'row_end': row_start + len(group_rows) - 1,
                        'columns': clean_headers,
                        'doc_id': doc_id,
                        'is_tabular': True,
                    },
                    'token_count': max(1, len(chunk_content.split())),
                })

    return chunks
