"""Schreiben des Freigabe-Vermerks in die PDF-Datei."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from pypdf.annotations import FreeText


def write_approval_stamp(src: Path, dst: Path, approver: str, comment: str,
                         when: datetime) -> None:
    writer = PdfWriter(clone_from=str(src))
    stamp = f"Freigegeben von {approver} am {when:%d.%m.%Y %H:%M}"
    if comment:
        stamp += f"\nKommentar: {comment}"

    page = writer.pages[0]
    box = page.mediabox
    x1 = float(box.left) + 30
    y1 = float(box.bottom) + 30
    writer.add_annotation(
        page_number=0,
        annotation=FreeText(
            text=stamp,
            rect=(x1, y1, x1 + 380, y1 + 80),
            font="Helv",
            font_size=10,
            font_color="#000000",
            border_color="#2e7d32",
            background_color="#e8f5e9",
        ),
    )
    writer.add_metadata(
        {
            "/ApprovedBy": approver,
            "/ApprovedDate": when.isoformat(timespec="seconds"),
            "/ApprovalComment": comment,
        }
    )
    with open(dst, "wb") as handle:
        writer.write(handle)
