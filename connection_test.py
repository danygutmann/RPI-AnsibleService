"""Schreibgeschützter Verbindungstest (ansible -m ping) für Inventory-Hosts."""
import json
import re
import subprocess

from ssh_keys import check_key_file

SAFE_HOST = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,99}\Z")

ERROR_HINTS = (
    ("Permission denied", "Anmeldung verweigert: Benutzer oder Schlüssel falsch."),
    ("Host key verification failed", "Host-Key-Prüfung fehlgeschlagen (known_hosts prüfen)."),
    ("Connection timed out", "Zeitüberschreitung: IP-Adresse/Port oder Firewall prüfen."),
    ("No route to host", "Kein Weg zum Host: IP-Adresse prüfen."),
    ("Connection refused", "Verbindung abgelehnt: SSH-Dienst/Port prüfen."),
    ("Could not resolve hostname", "Hostname nicht auflösbar."),
    ("Failed to connect to the host via ssh", "SSH-Verbindung fehlgeschlagen."),
    ("/usr/bin/python", "Python fehlt auf dem Zielsystem (für ping nötig)."),
    ("interpreter", "Python-Interpreter auf dem Zielsystem nicht gefunden."),
)


def explain(output):
    for needle, hint in ERROR_HINTS:
        if needle.lower() in output.lower():
            return hint
    return "Verbindung fehlgeschlagen."


def sanitize(text):
    return re.sub(
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?(-----END [A-Z ]*PRIVATE KEY-----|\Z)",
        "[Schlüssel entfernt]",
        text or "",
        flags=re.S,
    )


def load_hosts(inventory_path, run=subprocess.run):
    """Liefert {host: key_file_or_None} per ansible-inventory (kein Shell)."""
    result = run(
        ["ansible-inventory", "-i", str(inventory_path), "--list"],
        capture_output=True, text=True, errors="replace", timeout=60,
    )
    if result.returncode != 0:
        raise ValueError("Inventory konnte nicht gelesen werden.")
    meta = json.loads(result.stdout).get("_meta", {}).get("hostvars", {})
    return {h: v.get("ansible_ssh_private_key_file") for h, v in meta.items()}


def run_ping(inventory_path, host=None, run=subprocess.run):
    """Gibt (status, command, output) zurück; host=None testet alle Hosts."""
    try:
        hosts = load_hosts(inventory_path, run)
    except (ValueError, OSError, subprocess.TimeoutExpired) as exc:
        return "error", "", str(exc) or "Inventory konnte nicht gelesen werden."
    if host is not None and (host not in hosts or not SAFE_HOST.fullmatch(host)):
        return "error", "", "Unbekannter Host im Inventory."
    selected = [host] if host else list(hosts)
    if not selected:
        return "error", "", "Keine Hosts im Inventory."
    for name in selected:
        key = hosts[name]
        if key:
            ok, msg = check_key_file(key)
            if not ok:
                return "error", "", f"{name}: {msg}"
    cmd = ["ansible", host or "all", "-i", str(inventory_path), "-m", "ping"]
    try:
        result = run(cmd, capture_output=True, text=True, errors="replace", timeout=120)
    except subprocess.TimeoutExpired:
        return "error", " ".join(cmd), "Zeitlimit überschritten (2 Minuten)."
    except OSError as exc:
        return "error", " ".join(cmd), f"ansible konnte nicht gestartet werden: {exc}"
    output = sanitize("\n".join(p for p in (result.stdout, result.stderr) if p))
    if result.returncode == 0:
        return "success", " ".join(cmd), output
    return "error", " ".join(cmd), f"{explain(output)}\n\n{output}"
