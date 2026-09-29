"""
Text extraction for uploaded research documents: PDF, DOCX, and images (via OCR).

Each extractor is defensive — a corrupt or unusual file should never crash the
upload endpoint, just return an empty string with a logged warning so the
research flow degrades gracefully instead of failing outright.
"""
from __future__ import annotations

import logging

logger = logging.getLogger("research_agent.file_extract")

MAX_EXTRACTED_CHARS = 20000


def extract_text(filename: str, content: bytes) -> str:
    """Dispatch to the right extractor based on file extension."""
    lower = filename.lower()
    try:
        if lower.endswith(".pdf"):
            return _extract_pdf(content)
        if lower.endswith(".docx"):
            return _extract_docx(content)
        if lower.endswith((".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff")):
            return _extract_image(content)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Failed to extract text from %s: %s", filename, exc)
        return ""
    logger.warning("Unsupported file type for %s", filename)
    return ""


def _extract_pdf(content: bytes) -> str:
    import io

    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(content))
    text_parts = [page.extract_text() or "" for page in reader.pages]
    return "\n\n".join(text_parts).strip()[:MAX_EXTRACTED_CHARS]


def _extract_docx(content: bytes) -> str:
    import io

    import docx

    doc = docx.Document(io.BytesIO(content))
    text_parts = [p.text for p in doc.paragraphs if p.text.strip()]
    return "\n".join(text_parts).strip()[:MAX_EXTRACTED_CHARS]


def _extract_image(content: bytes) -> str:
    import io

    import pytesseract
    from PIL import Image

    img = Image.open(io.BytesIO(content))
    text = pytesseract.image_to_string(img)
    return text.strip()[:MAX_EXTRACTED_CHARS]
