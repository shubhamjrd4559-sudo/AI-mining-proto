"""
PDF extractor using pdfplumber.
Falls back to pytesseract OCR for scanned pages (text < OCR_TEXT_THRESHOLD chars).
"""
import io
import logging
from typing import Optional

from .base import ExtractedDocument, ExtractedTable

logger = logging.getLogger(__name__)

OCR_TEXT_THRESHOLD = 80  # chars per page below which we consider it scanned


def _ocr_page(pil_image) -> tuple[str, Optional[float]]:
    """Run OCR on a PIL image. Returns (text, confidence or None)."""
    try:
        import pytesseract
        data = pytesseract.image_to_data(pil_image, output_type=pytesseract.Output.DICT)
        texts = [t for t, c in zip(data['text'], data['conf']) if int(c) > 0 and t.strip()]
        confs = [int(c) for c in data['conf'] if int(c) > 0]
        text = ' '.join(texts)
        confidence = (sum(confs) / len(confs) / 100.0) if confs else None
        return text, confidence
    except ImportError:
        raise RuntimeError('pytesseract not installed')
    except Exception as exc:
        logger.warning('OCR failed for page: %s', exc)
        return '', None


def extract_pdf(file_bytes: bytes) -> ExtractedDocument:
    """Extract text and tables from PDF bytes."""
    try:
        import pdfplumber
    except ImportError:
        return ExtractedDocument(
            extractor_type='pdf_text',
            error='pdfplumber not installed — cannot extract PDF'
        )

    pages_text = []
    tables = []
    page_metadata = []
    ocr_used = False
    errors = []

    pdfium_doc = None
    try:
        import pypdfium2 as pdfium
        pdfium_doc = pdfium.PdfDocument(file_bytes)
    except Exception as exc:
        logger.info('pypdfium2 native text extraction unavailable (%s); using pdfplumber fallback', exc)
        pdfium_doc = None

    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            page_count = len(pdf.pages)
            for page_num, page in enumerate(pdf.pages, start=1):
                page_text = ''
                # 1. High-performance native text extraction via pypdfium2
                if pdfium_doc is not None:
                    try:
                        page_idx = page_num - 1
                        if 0 <= page_idx < len(pdfium_doc):
                            p_obj = pdfium_doc[page_idx]
                            textpage = p_obj.get_textpage()
                            raw_t = textpage.get_text_range()
                            if raw_t:
                                page_text = raw_t.replace('\r\n', '\n').replace('\r', '\n')
                    except Exception as p_exc:
                        logger.warning('pypdfium2 extraction failed on page %d: %s; falling back to pdfplumber', page_num, p_exc)
                        page_text = ''

                # 2. Fallback to pdfplumber text extraction if pypdfium2 returned empty or failed
                if not page_text:
                    page_text = page.extract_text() or ''

                page_info = {'page': page_num, 'text_chars': len(page_text), 'ocr': False}

                # 3. Extract tables from this page using pdfplumber (preserved completely)
                for t_idx, tbl in enumerate(page.extract_tables() or []):
                    if not tbl:
                        continue
                    headers = [str(h).strip() if h else '' for h in (tbl[0] if tbl else [])]
                    rows = [
                        [str(c).strip() if c is not None else '' for c in row]
                        for row in tbl[1:]
                    ]
                    tables.append(ExtractedTable(
                        source_ref=f'page:{page_num}:table:{t_idx + 1}',
                        headers=headers,
                        rows=rows,
                        page_number=page_num,
                    ))

                # 4. OCR fallback for scanned pages
                if len(page_text.strip()) < OCR_TEXT_THRESHOLD:
                    try:
                        pil_img = page.to_image(resolution=200).original
                        ocr_text, confidence = _ocr_page(pil_img)
                        if ocr_text:
                            page_text = ocr_text
                            page_info['ocr'] = True
                            page_info['ocr_confidence'] = confidence
                            ocr_used = True
                    except RuntimeError as exc:
                        page_info['ocr_unavailable'] = str(exc)
                    except Exception as exc:
                        page_info['ocr_error'] = str(exc)
                        errors.append(f'Page {page_num} OCR error: {exc}')

                pages_text.append(page_text)
                page_metadata.append(page_info)

    except Exception as exc:
        logger.error('PDF extraction failed: %s', exc)
        return ExtractedDocument(
            extractor_type='pdf_text',
            error=f'PDF extraction failed: {exc}'
        )
    finally:
        if pdfium_doc is not None:
            try:
                pdfium_doc.close()
            except Exception:
                pass

    full_text = '\n'.join(pages_text)
    return ExtractedDocument(
        extractor_type='pdf_ocr' if ocr_used else 'pdf_text',
        ocr_used=ocr_used,
        page_count=page_count,
        raw_text=full_text,
        tables=tables,
        metadata={'pages': page_metadata, 'errors': errors},
        error='; '.join(errors) if errors and not full_text.strip() else None,
    )
