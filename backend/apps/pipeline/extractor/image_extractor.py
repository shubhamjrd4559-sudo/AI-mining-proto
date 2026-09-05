"""
Image OCR extractor using Pillow + pytesseract.
"""
import io
import logging
from .base import ExtractedDocument

logger = logging.getLogger(__name__)


def extract_image(file_bytes: bytes) -> ExtractedDocument:
    # Open image with Pillow
    try:
        from PIL import Image
        image = Image.open(io.BytesIO(file_bytes))
        image.load()  # force decode to catch corrupt images early
    except ImportError:
        return ExtractedDocument(extractor_type='image_ocr', error='Pillow not installed')
    except Exception as exc:
        return ExtractedDocument(extractor_type='image_ocr', error=f'Cannot open image: {exc}')

    # Run OCR
    try:
        import pytesseract
        data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
        texts = [t for t, c in zip(data['text'], data['conf']) if int(c) > 0 and str(t).strip()]
        confs = [int(c) for c in data['conf'] if int(c) > 0]
        ocr_text = ' '.join(texts)
        confidence = (sum(confs) / len(confs) / 100.0) if confs else None

        return ExtractedDocument(
            extractor_type='image_ocr',
            ocr_used=True,
            raw_text=ocr_text,
            metadata={'ocr_confidence': confidence, 'image_size': image.size, 'image_mode': image.mode},
        )
    except ImportError:
        return ExtractedDocument(
            extractor_type='image_ocr',
            status_note='ocr_unavailable',
            error='pytesseract not installed. Install Tesseract OCR engine and pytesseract.',
            metadata={'ocr_available': False, 'image_size': image.size},
        )
    except Exception as exc:
        logger.warning('OCR failed: %s', exc)
        return ExtractedDocument(
            extractor_type='image_ocr',
            error=f'OCR failed: {exc}',
            metadata={'image_size': image.size},
        )
