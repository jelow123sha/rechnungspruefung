"""Konfiguration der Rechnungspruefungs-App."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class Config:
    input_dir: Path
    archive_dir: Path
    db_path: Path
    host: str
    port: int

    @staticmethod
    def load() -> "Config":
        cfg_file = PROJECT_ROOT / "config.json"
        data: dict = {}
        if cfg_file.exists():
            data = json.loads(cfg_file.read_text(encoding="utf-8"))
        return Config(
            input_dir=Path(data.get("input_dir", PROJECT_ROOT / "eingang")),
            archive_dir=Path(data.get("archive_dir", PROJECT_ROOT / "archiv")),
            db_path=Path(data.get("db_path", PROJECT_ROOT / "daten" / "rechnungen.db")),
            host=str(data.get("host", "0.0.0.0")),
            port=int(data.get("port", 8000)),
        )
