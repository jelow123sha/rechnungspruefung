"""Extraktion von Rechnungsdaten (Steller, Empfaenger, Betrag, Eingangsdatum) aus PDFs."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from pypdf import PdfReader

MAX_PAGES_TEXT = 3

SENDER_PATTERNS = [
    r"^\s*Rechnungssteller\s*[:\-]\s*(.+)$",
    r"^\s*Lieferant\s*[:\-]\s*(.+)$",
    r"^\s*Sender\s*[:\-]\s*(.+)$",
    r"^\s*Supplier\s*[:\-]\s*(.+)$",
    r"^\s*Vendor\s*[:\-]\s*(.+)$",
]

RECIPIENT_PATTERNS = [
    r"^\s*Rechnungsempf(?:ä|ae|a)nger\s*[:\-]\s*(.+)$",
    r"^\s*Empf(?:ä|ae|a)nger\s*[:\-]\s*(.+)$",
    r"^\s*Kunde\s*[:\-]\s*(.+)$",
    r"^\s*Auftraggeber\s*[:\-]\s*(.+)$",
    r"^\s*Bill\s*To\s*[:\-]\s*(.+)$",
    r"^\s*Customer\s*[:\-]\s*(.+)$",
]

AMOUNT_KEYWORDS_HIGH = [
    "bruttobetrag",
    "gesamtsumme",
    "gesamtbetrag",
    "gesamt (brutto)",
    "gesamt brutto",
    "rechnungsbetrag",
    "zahlbetrag",
    "fälliger betrag",
    "zu zahlen",
    "grand total",
    "total amount",
    "amount due",
]
AMOUNT_KEYWORDS_LOW = ["brutto", "gesamt", "total", "summe"]

AMOUNT_RE = re.compile(
    r"(?<![0-9.,])(\d{1,3}(?:[.\s]\d{3})*[,.]\d{2})(?![0-9])\s*(?:€|EUR|eur)?"
)


def _clean(value: str) -> str:
    return value.strip().strip(".,;").strip()


def _find_labeled(lines: list[str], patterns: list[str]) -> str | None:
    for line in lines:
        for pattern in patterns:
            match = re.match(pattern, line, flags=re.IGNORECASE)
            if match:
                value = _clean(match.group(1))
                if value:
                    return value
    return None


def _to_float(raw: str) -> float | None:
    text = raw.strip()
    if "." in text and "," in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        text = text.replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def _find_amount(lines: list[str]) -> float | None:
    candidates: list[tuple[int, int, float]] = []
    for index, line in enumerate(lines):
        lowered = line.lower()
        if not any(k in lowered for k in AMOUNT_KEYWORDS_HIGH + AMOUNT_KEYWORDS_LOW):
            continue
        matches = AMOUNT_RE.findall(line)
        if not matches:
            continue
        value = _to_float(matches[-1])
        if value is None:
            continue
        score = 2 if any(k in lowered for k in AMOUNT_KEYWORDS_HIGH) else 1
        candidates.append((score, index, value))
    if candidates:
        candidates.sort(key=lambda c: (c[0], c[1]))
        return candidates[-1][2]
    for line in reversed(lines):
        matches = AMOUNT_RE.findall(line)
        if matches:
            value = _to_float(matches[-1])
            if value is not None:
                return value
    return None


def _received_at(reader: PdfReader, path: Path) -> str:
    try:
        created = reader.metadata.creation_date if reader.metadata else None
    except Exception:
        created = None
    if created is None:
        created = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    return created.isoformat()


def extract_invoice_data(path: Path) -> dict:
    reader = PdfReader(str(path))
    parts: list[str] = []
    for page in reader.pages[:MAX_PAGES_TEXT]:
        try:
            parts.append(page.extract_text() or "")
        except Exception:
            continue
    lines = [line for line in "\n".join(parts).splitlines() if line.strip()]
    amount = _find_amount(lines)
    return {
        "sender": _find_labeled(lines, SENDER_PATTERNS),
        "recipient": _find_labeled(lines, RECIPIENT_PATTERNS),
        "amount": amount,
        "received_at": _received_at(reader, path),
    }
