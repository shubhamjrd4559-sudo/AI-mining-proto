from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

@dataclass
class ExtractedTable:
    """A single extracted table (from one page, sheet, or section)."""
    source_ref: str          # e.g. 'page:3', 'sheet:Sheet1', 'section:Table 1'
    headers: List[str]       # column headers (may be empty)
    rows: List[List[Any]]    # raw row data
    page_number: Optional[int] = None
    sheet_name: Optional[str] = None
    section_heading: Optional[str] = None
    confidence: Optional[float] = None


@dataclass
class ExtractedDocument:
    """Output of a document extractor."""
    extractor_type: str       # 'pdf_text', 'pdf_ocr', 'docx', 'xlsx', 'csv', 'txt', 'image_ocr'
    ocr_used: bool = False
    page_count: int = 0
    raw_text: str = ''
    tables: List[ExtractedTable] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)  # extra info: confidence, sheet_names, etc.
    error: Optional[str] = None  # non-None means partial or full failure
    status_note: Optional[str] = None
