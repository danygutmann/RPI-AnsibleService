"""Prüfung externer privater SSH-Schlüssel (ohne den Inhalt preiszugeben)."""
import os
from pathlib import Path

PRIVATE_KEY_MARKERS = (
    "-----BEGIN OPENSSH PRIVATE KEY-----",
    "-----BEGIN RSA PRIVATE KEY-----",
    "-----BEGIN EC PRIVATE KEY-----",
    "-----BEGIN DSA PRIVATE KEY-----",
    "-----BEGIN PRIVATE KEY-----",
    "-----BEGIN ENCRYPTED PRIVATE KEY-----",
)


def check_key_file(path):
    """Gibt (ok, meldung) zurück. Der Dateiinhalt wird nie ausgegeben."""
    if not path or not str(path).strip():
        return False, "Kein Schlüsselpfad konfiguriert."
    if "\x00" in str(path) or not os.path.isabs(str(path)):
        return False, "Ungültiger Schlüsselpfad (absoluter Pfad erforderlich)."
    key = Path(path)
    if not key.exists():
        return False, f"Schlüsseldatei nicht gefunden: {key} (Mount prüfen)."
    if not key.is_file():
        return False, f"Schlüsselpfad ist keine Datei: {key}."
    try:
        with open(key, "r", encoding="utf-8", errors="replace") as handle:
            head = handle.read(200)
    except OSError:
        return False, f"Schlüsseldatei nicht lesbar: {key} (Rechte/Eigentümer prüfen)."
    if not head.lstrip().startswith(PRIVATE_KEY_MARKERS):
        return False, f"Datei {key} ist kein gültiger privater SSH-Schlüssel."
    return True, "Schlüssel vorhanden und lesbar."
