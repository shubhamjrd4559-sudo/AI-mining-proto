"""
Plain text extractor.
"""
from .base import ExtractedDocument


def extract_txt(file_bytes: bytes) -> ExtractedDocument:
    for encoding in ('utf-8-sig', 'utf-8', 'latin-1', 'cp1252'):
        try:
            text = file_bytes.decode(encoding)
            return ExtractedDocument(
                extractor_type='txt',
                raw_text=text,
                metadata={'encoding': encoding, 'char_count': len(text)},
            )
        except (UnicodeDecodeError, LookupError):
            continue
    return ExtractedDocument(extractor_type='txt', error='Cannot decode text file')
