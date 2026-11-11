"""Schreiben des Freigabe-Vermerks in die PDF-Datei.

Der Vermerk wird direkt in den Seiteninhalt von Seite 1 gestempelt und ist
damit in jedem PDF-Betrachter sichtbar (Annotations-Freitext wird von manchen
Browser-Viewern naemlich nicht gerendert).
"""
from __future__ import annotations

import io
from datetime import datetime
from pathlib import Path

from pypdf import PdfReader, PdfWriter

FONT_SIZE = 10
LINE_HEIGHT = 15
AVG_CHAR_WIDTH = FONT_SIZE * 0.55


def _escape(text: str) -> str:
    return text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


def _wrap(text: str, max_chars: int) -> list[str]:
    lines: list[str] = []
    for part in text.splitlines() or [""]:
        while len(part) > max_chars:
            cut = part.rfind(" ", 0, max_chars)
            if cut <= 0:
                cut = max_chars
            lines.append(part[:cut])
            part = part[cut:].lstrip()
        lines.append(part)
    return lines


def _overlay_pdf(width: float, height: float, lines: list[str]) -> bytes:
    margin = 30
    box_w = min(540.0, width - 2 * margin)
    box_h = 16 + LINE_HEIGHT * len(lines)
    if box_h > height - 2 * margin:
        box_h = height - 2 * margin
    x, y = margin, margin

    max_chars = max(20, int((box_w - 16) / AVG_CHAR_WIDTH))
    stream_lines: list[str] = [
        f"q 0.910 0.961 0.914 rg {x} {y} {box_w:.2f} {box_h:.2f} re f Q",
        f"q 0.180 0.490 0.196 RG 1 w {x} {y} {box_w:.2f} {box_h:.2f} re S Q",
    ]
    ty = y + box_h - 8 - FONT_SIZE
    for line in lines:
        if ty < y + 4:
            break
        stream_lines.append(
            f"BT /F1 {FONT_SIZE} Tf 0.05 0.05 0.05 rg {x + 8} {ty:.2f} Td "
            f"({_escape(line[:max_chars])}) Tj ET"
        )
        ty -= LINE_HEIGHT
    stream = "\n".join(stream_lines).encode("cp1252", errors="replace")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {width:.2f} {height:.2f}] "
            f"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>".encode()
        ),
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref_pos = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode() + b"0000000000 65535 f \n"
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_pos}\n%%EOF\n"
    ).encode()
    return bytes(out)


def write_approval_stamp(src: Path, dst: Path, approver: str, comment: str,
                         when: datetime) -> None:
    writer = PdfWriter(clone_from=str(src))
    page = writer.pages[0]
    box = page.mediabox
    width = float(box.width)
    height = float(box.height)

    stamp = f"Freigegeben von {approver} am {when:%d.%m.%Y %H:%M} Uhr"
    lines = _wrap(stamp, 70)
    if comment:
        lines.append("")
        lines.extend(_wrap("Kommentar: " + comment, 95))

    overlay = PdfReader(io.BytesIO(_overlay_pdf(width, height, lines)))
    page.merge_page(overlay.pages[0])

    writer.add_metadata(
        {
            "/ApprovedBy": approver,
            "/ApprovedDate": when.isoformat(timespec="seconds"),
            "/ApprovalComment": comment,
        }
    )
    with open(dst, "wb") as handle:
        writer.write(handle)
