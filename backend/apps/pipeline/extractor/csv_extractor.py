"""
CSV extractor using stdlib csv with delimiter sniffing.
"""
import csv
import io
import logging
from .base import ExtractedDocument, ExtractedTable

logger = logging.getLogger(__name__)


def extract_csv(file_bytes: bytes) -> ExtractedDocument:
    # Try common encodings
    for encoding in ('utf-8-sig', 'utf-8', 'latin-1', 'cp1252'):
        try:
            text = file_bytes.decode(encoding)
            break
        except (UnicodeDecodeError, LookupError):
            continue
    else:
        return ExtractedDocument(extractor_type='csv', error='Cannot decode CSV — unknown encoding')

    # Sniff delimiter
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=',;\t|')
    except csv.Error:
        dialect = None  # fallback to comma

    delimiter = dialect.delimiter if dialect else ','

    try:
        reader = csv.reader(io.StringIO(text), delimiter=delimiter)
        rows_raw = list(reader)
    except Exception as exc:
        return ExtractedDocument(extractor_type='csv', error=f'CSV parse error: {exc}')

    if not rows_raw:
        return ExtractedDocument(extractor_type='csv', raw_text=text)

    headers = [str(h).strip() for h in rows_raw[0]]
    rows = [[str(c).strip() for c in row] for row in rows_raw[1:] if any(c.strip() for c in row)]

    table = ExtractedTable(
        source_ref='csv:1',
        headers=headers,
        rows=rows,
    )

    return ExtractedDocument(
        extractor_type='csv',
        raw_text=text,
        tables=[table],
        metadata={'delimiter': delimiter, 'row_count': len(rows), 'col_count': len(headers)},
    )
