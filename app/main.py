"""Rechnungspruefung: lokale Web-App zum Einlesen, Pruefen und Freigeben von PDF-Rechnungen."""
from __future__ import annotations

import os
import shutil
import tempfile
import traceback
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from pypdf import PdfReader, PdfWriter

from .config import Config
from .db import Database
from .extract import extract_invoice_data
from .pdfwrite import write_approval_stamp

config = Config.load()
db = Database(config.db_path)

app = FastAPI(title="Rechnungsprüfung")


STAMP_POSITIONS = ("bottom-left", "bottom-right", "top-left", "top-right",
                   "last-page")


class CommentPayload(BaseModel):
    comment: str = ""


class ApprovePayload(BaseModel):
    approver: str
    comment: str = ""
    position: str = "bottom-left"


class MergePayload(BaseModel):
    other_id: int


def _scan() -> int:
    config.input_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    entries: list[dict] = []
    for path in sorted(config.input_dir.glob("*")):
        if not path.is_file() or path.suffix.lower() != ".pdf":
            continue
        try:
            data = extract_invoice_data(path)
        except Exception:
            data = {"sender": None, "recipient": None, "amount": None,
                    "received_at": datetime.fromtimestamp(
                        path.stat().st_mtime, tz=timezone.utc).isoformat()}
        entries.append(
            {
                "filename": path.name,
                "filepath": str(path.resolve()),
                "sender": data["sender"],
                "recipient": data["recipient"],
                "amount": data["amount"],
                "received_at": data["received_at"],
                "added_at": now,
            }
        )
    return db.scan_insert(entries)


@app.get("/api/invoices")
def list_invoices() -> dict:
    added = _scan()
    return {"invoices": db.list_pending(), "added": added}


@app.get("/api/invoices/{invoice_id}/file")
def invoice_file(invoice_id: int) -> FileResponse:
    invoice = db.get_invoice(invoice_id)
    if invoice is None:
        raise HTTPException(status_code=404, detail="Rechnung nicht gefunden")
    path = Path(invoice["filepath"])
    if not path.exists():
        raise HTTPException(status_code=410, detail="Datei existiert nicht mehr")
    return FileResponse(path, media_type="application/pdf",
                        filename=invoice["filename"],
                        content_disposition_type="inline")


@app.post("/api/invoices/{invoice_id}/comment")
def save_comment(invoice_id: int, payload: CommentPayload) -> dict:
    if db.get_invoice(invoice_id) is None:
        raise HTTPException(status_code=404, detail="Rechnung nicht gefunden")
    db.set_comment(invoice_id, payload.comment.strip())
    return {"ok": True}


@app.post("/api/invoices/{invoice_id}/approve")
def approve_invoice(invoice_id: int, payload: ApprovePayload) -> dict:
    invoice = db.get_invoice(invoice_id)
    if invoice is None:
        raise HTTPException(status_code=404, detail="Rechnung nicht gefunden")
    approver = payload.approver.strip()
    if not approver:
        raise HTTPException(status_code=400,
                            detail="Der Name des Prüfers ist ein Pflichtfeld.")
    comment = payload.comment.strip()

    src = Path(invoice["filepath"])
    if not src.exists():
        db.delete_invoice(invoice_id)
        raise HTTPException(status_code=410,
                            detail="Datei existiert nicht mehr im Eingangsordner.")

    now = datetime.now(timezone.utc)
    position = payload.position if payload.position in STAMP_POSITIONS else "bottom-left"
    config.archive_dir.mkdir(parents=True, exist_ok=True)
    dest = config.archive_dir / src.name
    if dest.exists():
        dest = config.archive_dir / f"{src.stem}_{now:%Y%m%d-%H%M%S}{src.suffix}"

    handle, tmp_name = tempfile.mkstemp(
        suffix=".pdf", dir=str(config.archive_dir))
    os.close(handle)
    tmp = Path(tmp_name)
    try:
        try:
            write_approval_stamp(src, tmp, approver, comment, now, position)
        except Exception:
            shutil.copyfile(src, tmp)
        os.replace(tmp, dest)
        src.unlink(missing_ok=True)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise HTTPException(status_code=500,
                            detail="Archivierung fehlgeschlagen (Netzlaufwerk prüfen).")

    db.record_approval(
        {
            "filename": invoice["filename"],
            "sender": invoice["sender"],
            "recipient": invoice["recipient"],
            "amount": invoice["amount"],
            "received_at": invoice["received_at"],
            "approver": approver,
            "comment": comment,
            "approved_at": now.isoformat(timespec="seconds"),
            "archive_path": str(dest),
        }
    )
    db.delete_invoice(invoice_id)
    return {"ok": True, "archive_path": str(dest)}


@app.post("/api/invoices/{invoice_id}/merge")
def merge_invoice(invoice_id: int, payload: MergePayload) -> dict:
    invoice = db.get_invoice(invoice_id)
    if invoice is None:
        raise HTTPException(status_code=404, detail="Rechnung nicht gefunden")
    other = db.get_invoice(payload.other_id)
    if other is None:
        raise HTTPException(status_code=404, detail="Anzuhängende PDF nicht gefunden")
    if payload.other_id == invoice_id:
        raise HTTPException(status_code=400,
                            detail="Eine Rechnung kann nicht mit sich selbst zusammengefügt werden.")

    src = Path(invoice["filepath"])
    other_path = Path(other["filepath"])
    if not src.exists():
        db.delete_invoice(invoice_id)
        raise HTTPException(status_code=410, detail="Rechnungsdatei existiert nicht mehr.")
    if not other_path.exists():
        db.delete_invoice(payload.other_id)
        raise HTTPException(status_code=410,
                            detail="Die anzuhängende Datei existiert nicht mehr.")

    handle, tmp_name = tempfile.mkstemp(suffix=".pdf", dir=str(src.parent))
    os.close(handle)
    tmp = Path(tmp_name)
    try:
        writer = PdfWriter(clone_from=str(src))
        for page in PdfReader(str(other_path)).pages:
            writer.add_page(page)
        with open(tmp, "wb") as fh:
            writer.write(fh)
        os.replace(tmp, src)
    except Exception:
        traceback.print_exc()
        tmp.unlink(missing_ok=True)
        raise HTTPException(status_code=500,
                            detail="Zusammenfügen fehlgeschlagen "
                                   "(PDF beschädigt oder passwortgeschützt?).")
    other_path.unlink(missing_ok=True)
    db.delete_invoice(payload.other_id)

    page_count = len(PdfReader(str(src)).pages)
    return {"ok": True, "filename": invoice["filename"], "pages": page_count}


@app.get("/api/history")
def list_history() -> dict:
    return {"history": db.list_history()}


@app.get("/api/history/{entry_id}/file")
def history_file(entry_id: int) -> FileResponse:
    entry = db.get_history_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Eintrag nicht gefunden")
    path = Path(entry["archive_path"])
    if not path.exists():
        raise HTTPException(status_code=410, detail="Archivdatei existiert nicht mehr")
    return FileResponse(path, media_type="application/pdf",
                        filename=entry["filename"],
                        content_disposition_type="inline")


class NoCacheStaticFiles(StaticFiles):
    def file_response(self, *args, **kwargs):
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = "no-cache"
        return response


app.mount("/", NoCacheStaticFiles(
    directory=str(Path(__file__).resolve().parent.parent / "static"),
    html=True), name="static")
