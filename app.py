import os
from pathlib import Path
import shlex
import subprocess

from flask import Flask, render_template, request

app = Flask(__name__)

BASE_DIR = Path(os.environ.get("APP_DIR", Path(__file__).resolve().parent))
INVENTORY_DIR = BASE_DIR / "inventory"
FILE_EXTENSIONS = {".ini", ".yml", ".yaml"}


def list_inventories():
    if not INVENTORY_DIR.is_dir():
        return []

    return sorted(
        file.name
        for file in INVENTORY_DIR.iterdir()
        if file.is_file()
        and not file.is_symlink()
        and file.suffix.lower() in FILE_EXTENSIONS
    )


def is_likely_playbook(file):
    try:
        beginning = file.read_text(encoding="utf-8")[:2000]
        return "hosts:" in beginning or "import_playbook:" in beginning
    except (OSError, UnicodeError):
        return False


def list_playbooks():
    if not BASE_DIR.is_dir():
        return []

    return sorted(
        file.name
        for file in BASE_DIR.iterdir()
        if file.is_file()
        and not file.is_symlink()
        and file.suffix.lower() in {".yml", ".yaml"}
        and file.name != "requirements.yml"
        and is_likely_playbook(file)
    )


@app.route("/", methods=["GET", "POST"])
def index():
    inventories = list_inventories()
    playbooks = list_playbooks()

    selected_inventory = inventories[0] if inventories else ""
    selected_playbook = playbooks[0] if playbooks else ""
    output = ""
    command = ""
    status = ""

    if request.method == "POST":
        selected_inventory = request.form.get("inventory", "")
        selected_playbook = request.form.get("playbook", "")

        # Nur aktuell angebotene Dateinamen akzeptieren, keine beliebigen Pfade.
        if selected_inventory not in inventories or selected_playbook not in playbooks:
            status = "error"
            output = "Ungültige Auswahl."
        else:
            cmd = [
                "ansible-playbook",
                "-i",
                str(INVENTORY_DIR / selected_inventory),
                str(BASE_DIR / selected_playbook),
            ]
            command = shlex.join(cmd)

            try:
                result = subprocess.run(
                    cmd,
                    cwd=BASE_DIR,
                    capture_output=True,
                    text=True,
                    errors="replace",
                    timeout=1800,
                )
                output = "\n".join(
                    part for part in (result.stdout, result.stderr) if part
                )
                status = "success" if result.returncode == 0 else "error"
            except subprocess.TimeoutExpired:
                status = "error"
                output = "Zeitlimit überschritten (30 Minuten)."
            except OSError as exc:
                status = "error"
                output = f"Playbook konnte nicht gestartet werden: {exc}"

    return render_template(
        "index.html",
        inventories=inventories,
        playbooks=playbooks,
        selected_inventory=selected_inventory,
        selected_playbook=selected_playbook,
        output=output,
        command=command,
        status=status,
    )


@app.get("/inventories")
def inventories_page():
    return render_template("inventories.html", inventories=list_inventories())


@app.get("/playbooks")
def playbooks_page():
    return render_template("playbooks.html", playbooks=list_playbooks())


if __name__ == "__main__":
    # Reload bei Änderungen an app.py; kein Debugger auf dem Netzwerkport.
    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=True)