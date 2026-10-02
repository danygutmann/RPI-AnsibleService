import os
from pathlib import Path
import re
import shlex
import subprocess

from flask import Flask, abort, redirect, render_template, request, url_for

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 1_048_576

BASE_DIR = Path(os.environ.get("APP_DIR", Path(__file__).resolve().parent))
INVENTORY_DIR = BASE_DIR / "inventory"
JOB_DIR = BASE_DIR / "jobs"
TASK_DIR = BASE_DIR / "tasks"
FILE_EXTENSIONS = {".ini", ".yml", ".yaml"}
EDITOR_CATEGORIES = {
    "jobs": (JOB_DIR, {".yml", ".yaml"}, "Playbook"),
    "tasks": (TASK_DIR, {".yml", ".yaml"}, "Task"),
    "inventories": (INVENTORY_DIR, FILE_EXTENSIONS, "Inventory"),
}
SAFE_FILENAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,99}\Z")


def list_files(directory, extensions):
    if not directory.is_dir():
        return []

    return sorted(
        file.name
        for file in directory.iterdir()
        if file.is_file()
        and not file.is_symlink()
        and file.suffix.lower() in extensions
    )


def list_inventories():
    return list_files(INVENTORY_DIR, FILE_EXTENSIONS)


def is_likely_playbook(file):
    try:
        beginning = file.read_text(encoding="utf-8")[:2000]
        return "hosts:" in beginning or "import_playbook:" in beginning
    except (OSError, UnicodeError):
        return False


def list_playbooks():
    if not JOB_DIR.is_dir():
        return []

    return sorted(
        file.name
        for file in JOB_DIR.iterdir()
        if file.is_file()
        and not file.is_symlink()
        and file.suffix.lower() in {".yml", ".yaml"}
        and file.name != "requirements.yml"
        and is_likely_playbook(file)
    )


def list_tasks():
    return list_files(TASK_DIR, {".yml", ".yaml"})


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
        if (
            not SAFE_FILENAME.fullmatch(selected_inventory)
            or not SAFE_FILENAME.fullmatch(selected_playbook)
            or selected_inventory not in inventories
            or selected_playbook not in playbooks
        ):
            status = "error"
            output = "Ungültige Auswahl."
        else:
            cmd = [
                "ansible-playbook",
                "-i",
                str(INVENTORY_DIR / selected_inventory),
                str(JOB_DIR / selected_playbook),
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


@app.get("/tasks")
def tasks_page():
    return render_template("tasks.html", tasks=list_tasks())


@app.route("/edit/<category>", defaults={"filename": None}, methods=["GET", "POST"])
@app.route("/edit/<category>/<filename>", methods=["GET", "POST"])
def editor_page(category, filename):
    if category not in EDITOR_CATEGORIES:
        abort(404)

    directory, extensions, label = EDITOR_CATEGORIES[category]
    if directory.is_symlink() or not directory.is_dir():
        abort(404)

    is_new = filename is None
    error = ""
    saved = request.args.get("saved") == "1"
    content = ""

    if request.method == "POST":
        filename = filename or request.form.get("filename", "").strip()
        if not SAFE_FILENAME.fullmatch(filename or ""):
            error = "Bitte einen gültigen Dateinamen ohne Verzeichnispfad angeben."
        elif Path(filename).suffix.lower() not in extensions:
            error = "Diese Dateiendung wird für diesen Dateityp nicht unterstützt."
        else:
            path = directory / filename
            content = request.form.get("content", "")
            if len(content.encode("utf-8")) > app.config["MAX_CONTENT_LENGTH"]:
                error = "Die Datei darf höchstens 1 MiB groß sein."
            elif is_new and (path.exists() or path.is_symlink()):
                error = "Eine Datei mit diesem Namen existiert bereits."
            elif not is_new and (path.is_symlink() or not path.is_file()):
                error = "Die Datei wurde nicht gefunden."
            else:
                flags = os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0)
                if is_new:
                    flags |= os.O_CREAT | os.O_EXCL
                else:
                    flags |= os.O_TRUNC
                try:
                    descriptor = os.open(path, flags, 0o644)
                    with os.fdopen(descriptor, "w", encoding="utf-8") as file:
                        file.write(content)
                except FileExistsError:
                    error = "Eine Datei mit diesem Namen existiert bereits."
                except OSError:
                    error = "Die Datei konnte nicht gespeichert werden."
                else:
                    return redirect(
                        url_for("editor_page", category=category, filename=filename, saved=1)
                    )
    elif filename:
        if (
            not SAFE_FILENAME.fullmatch(filename)
            or Path(filename).suffix.lower() not in extensions
        ):
            abort(404)
        path = directory / filename
        if path.is_symlink() or not path.is_file():
            abort(404)
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            abort(404)

    return render_template(
        "editor.html",
        category=category,
        filename=filename or "",
        content=content,
        error=error,
        saved=saved,
        is_new=is_new,
        label=label,
    )


if __name__ == "__main__":
    # Reload bei Änderungen an app.py; kein Debugger auf dem Netzwerkport.
    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=True)