# Rechnungsprüfung

Lokale Web-App zum Einlesen, Prüfen und Freigeben von PDF-Rechnungen aus einem
Netzlaufwerk – für mehrere Nutzer gleichzeitig im Firmennetzwerk.

## Funktionen

- **Rechnungsliste:** PDFs aus dem Eingangsordner werden automatisch eingelesen.
  Angezeigt werden (soweit in der PDF erkennbar) Rechnungssteller, Empfänger,
  Bruttobetrag und Eingangsdatum (Erstell-/Änderungsdatum der PDF-Datei).
- **Vorschau:** Klick auf eine Rechnung zeigt die PDF im rechten Bereich.
- **Kommentare:** Der Nutzer kann einen Kommentar speichern; bei der Freigabe
  wird der Kommentar dauerhaft in die PDF-Datei geschrieben (Annotation auf
  Seite 1) und in der Historie abgelegt.
- **Freigabe (Pflichtfeld Name):** Ohne Eingabe des Prüfer-Namens ist keine
  Freigabe möglich. Die Datei wird in den Archiv-Ordner verschoben, verschwindet
  aus der Liste und erscheint unter **Historische Freigaben** mit Prüfer,
  Kommentar, Zeitstempel und Archivpfad.
- **Mehrere Nutzer:** Gleichzeitige Nutzung mehrerer Nutzer im Netzwerk wird
  unterstützt (SQLite im WAL-Modus, Listen-Aktualisierung alle 15 Sekunden).

## Installation

Voraussetzung: Python 3.10 oder neuer.

- **Windows:** `start.bat` doppelklicken (legt automatisch eine venv an und startet den Server).
- **Linux/macOS:** `./start.sh`

Alternativ manuell:

```bash
python -m venv venv
venv/bin/pip install -r requirements.txt      # Windows: venv\Scripts\pip install -r requirements.txt
venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Konfiguration

`config.json` im Projektordner anlegen (Vorlage: `config.example.json`):

```json
{
    "input_dir": "\\\\SERVER\\Freigabe\\Rechnungen\\Eingang",
    "archive_dir": "\\\\SERVER\\Freigabe\\Rechnungen\\Archiv",
    "db_path": "daten/rechnungen.db",
    "host": "0.0.0.0",
    "port": 8000
}
```

- `input_dir`: Netzlaufwerk-Ordner mit den eingehenden PDF-Rechnungen
  (UNC-Pfade wie `\\SERVER\Freigabe\...` oder Laufwerksbuchstaben wie `R:\Rechnungen`).
- `archive_dir`: Zielordner für freigegebene Rechnungen.
- `host`: `0.0.0.0` macht die App im gesamten Netzwerk erreichbar
  (Aufruf im Browser z. B. unter `http://<Server-IP>:8000`).
  Nur lokal nutzen: `127.0.0.1`. Die App ist nicht für das Internet gedacht.
- `port`: Port des Webservers (Standard 8000).

Ohne `config.json` werden die lokalen Ordner `eingang/` und `archiv/` verwendet.

## Nutzung

1. App starten und im Browser `http://<Server-IP>:8000` öffnen.
2. Rechnung in der Liste anklicken → PDF erscheint rechts.
3. Kommentar eintragen und ggf. über **Kommentar speichern** zwischenspeichern.
4. **Prüfer-Namen eintragen (Pflichtfeld)** und auf
   **Freigeben & archivieren** klicken. Die PDF wird mit einem Freigabe-Vermerk
   (Name, Datum, Kommentar) versehen und in den Archiv-Ordner verschoben.
5. Unter **Historische Freigaben** sind alle Freigaben mit Prüfer, Kommentar und
   Datum nachvollziehbar; ein Klick zeigt die archivierte PDF an.

## Hinweise

- Die Datenextraktion (Steller, Empfänger, Betrag) basiert auf Textmustern und
  funktioniert am besten mit textbasierten Rechnungen. Fehlende Werte werden
  als „–“ angezeigt; geprüft wird ohnehin in der PDF-Vorschau.
- Die Datenbank (`daten/rechnungen.db`) enthält die Historie und sollte
  regelmäßig gesichert werden.
- Es ist keine Registrierung oder Anmeldung nötig; die Nachvollziehbarkeit
  erfolgt über das Pflichtfeld „Prüfer“.
- Die App ist für den Betrieb im internen Netzwerk (LAN) vorgesehen und nicht
  aus dem Internet erreichbar bzw. dafür nicht abgesichert.
