"""OCR-Fallback fuer gescannte PDFs (Tesseract + PyMuPDF).

Die Abhaengigkeiten sind optional: Ist Tesseract (Binary) oder PyMuPDF
nicht installiert, liefert dieses Modul einfach None und die App arbeitet
weiterhin mit Text-Heuristik bzw. ZUGFeRD-XML.
"""
from __future__ import annotations

import traceback
from pathlib import Path

_ocr_available: bool | None = None


def ocr_available() -> bool:
    """Pruefen, ob Tesseract-Binary und Python-Pakete vorhanden sind (gecacht)."""
    global _ocr_available
    if _ocr_available is not None:
        return _ocr_available
    try:
        import pytesseract  # type: ignore

        pytesseract.get_tesseract_version()
        import PIL  # noqa: F401  (Pillow wird von pytesseract benoetigt)
        _ocr_available = True
    except Exception:
        _ocr_available = False
    return _ocr_available


def ocr_pages_text(path: Path, max_pages: int = 2, lang: str = "deu+eng") -> str | None:
    """Erste PDF-Seiten per OCR in Text umwandeln (Scan-Erkennung).

    Gibt None zurueck, wenn OCR nicht verfuegbar ist oder fehlschlaegt.
    """
    if not ocr_available():
        return None
    try:
        import fitz  # PyMuPDF  # type: ignore
        import pytesseract  # type: ignore
        from PIL import Image  # type: ignore

        doc = fitz.open(str(path))
        texts: list[str] = []
        try:
            for page in list(doc)[:max_pages]:
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), colorspace=fitz.csGRAY)
                img = Image.frombytes("L", (pix.width, pix.height), pix.samples)
                texts.append(pytesseract.image_to_string(img, lang=lang))
        finally:
            doc.close()
        combined = "\n".join(t for t in texts if t.strip())
        return combined or None
    except Exception:
        traceback.print_exc()
        return None
