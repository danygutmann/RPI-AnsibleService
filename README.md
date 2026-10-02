# RPI-AnsibleService

Kleine Flask-Weboberfläche zum Ausführen von Ansible-Playbooks auf Raspberry Pis (oder anderen Hosts). Im Browser wird ein Inventory und ein Playbook gewählt; die App startet `ansible-playbook` und zeigt die Ausgabe an.

## Inhalt

- [Funktionen](#funktionen)
- [Projektstruktur](#projektstruktur)
- [Voraussetzungen](#voraussetzungen)
- [Schnellstart mit Docker Compose](#schnellstart-mit-docker-compose)
- [Alternative: Image selbst bauen](#alternative-image-selbst-bauen)
- [Initialisierung in Docker](#initialisierung-in-docker)
- [Inventories](#inventories)
- [Playbooks](#playbooks)
- [Sicherheitshinweise](#sicherheitshinweise)
- [Fehlersuche](#fehlersuche)

## Funktionen

- Weboberfläche (Port `5000`) mit Seiten für Start (`/`), Inventories (`/inventories`) und Playbooks (`/playbooks`)
- Erkennt automatisch alle `*.yml`/`*.yaml`-Playbooks im Projektverzeichnis (Dateien mit `hosts:` oder `import_playbook:`)
- Erkennt Inventories im Ordner `inventory/` (`.ini`, `.yml`, `.yaml`)
- Es werden nur aktuell angebotene Dateinamen akzeptiert (keine beliebigen Pfade); Timeout 30 Minuten

## Projektstruktur

| Pfad | Beschreibung |
|------|--------------|
| `app.py` | Flask-Anwendung (erwartet das Projekt unter `/work`) |
| `Dockerfile` | Image mit Python 3.12, Ansible, Flask, ssh, sshpass, git |
| `Docker_compose.yml` | Compose-Datei (Start ohne eigenes Image, Installation beim Start) |
| `ansible.cfg` | Ansible-Konfiguration (`host_key_checking = False`, Log `ansible.log`) |
| `inventory/` | Inventories, z. B. `RPI_A.ini`, `RPI_B.ini`, `Team_X.ini` |
| `inventory.ini` | Standard-Inventory für die CLI-Nutzung |
| `Job_*.yml`, `Setup_*.yml`, `Config_wlan.yml`, `Check_IsOnline.yml`, `site.yml` | Playbooks |
| `tasks/` | Wiederverwendbare Task-Dateien (Docker, Portainer, Python, Git, Cockpit, USB, VLAN …) |
| `templates/`, `static/` | HTML-Templates, CSS und JS der Weboberfläche |
| `collections/` | Ansible-Collections (wird beim Start erzeugt, nicht im Git) |

## Voraussetzungen

- Docker und Docker Compose v2 (`docker compose`)
- Netzwerkzugriff vom Container zu den Zielhosts (SSH, Port 22)
- SSH-Zugang (Passwort oder Schlüssel) zu den Zielhosts

## Schnellstart mit Docker Compose

Die mitgelieferte `Docker_compose.yml` nutzt das Standard-Image `python:3.12-slim`, installiert beim Start alle Abhängigkeiten und die Collections `community.docker` und `community.general` und startet die App. Das Projekt wird als `/work` eingebunden.

1. Repository klonen:

   ```bash
   git clone https://github.com/danygutmann/RPI-AnsibleService.git
   cd RPI-AnsibleService
   ```

2. Pfad des Volumes anpassen. In `Docker_compose.yml` ist ein Synology-Pfad hinterlegt (`/volume1/docker/Ansible`). Für ein lokales Verzeichnis ersetzen durch `.:/work`:

   ```yaml
   volumes:
     - .:/work
   ```

3. Starten:

   ```bash
   docker compose -f Docker_compose.yml up -d
   docker compose -f Docker_compose.yml logs -f
   ```

4. Im Browser öffnen: <http://localhost:5000> (bzw. `http://<Server-IP>:5000`).

Stoppen: `docker compose -f Docker_compose.yml down`

> Der erste Start dauert etwas, da Pakete und Collections installiert werden.

## Alternative: Image selbst bauen

Das `Dockerfile` enthält bereits alle Abhängigkeiten, benötigt aber weiterhin das Projekt unter `/work` sowie die Collections. Beispiel `compose.yml`:

```yaml
services:
  ansible-web:
    build: .
    image: rpi-ansible-service
    container_name: rpi-ansible-service
    restart: unless-stopped
    ports:
      - "5000:5000"
    volumes:
      - .:/work
    working_dir: /work
    environment:
      ANSIBLE_COLLECTIONS_PATH: /work/collections
    command: >
      bash -lc "
      ansible-galaxy collection install -p /work/collections community.docker community.general &&
      python /work/app.py
      "
```

```bash
docker compose up -d --build
```

> Hinweis: Das `Dockerfile` kopiert `app.py` nach `/app/app.py`, die App liest Inventories/Playbooks jedoch aus `/work`. Daher muss das Projekt immer als Volume nach `/work` gemountet werden (wie oben).

## Initialisierung in Docker

### Collections vorab installieren

```bash
docker compose -f Docker_compose.yml exec ansible-web \
  ansible-galaxy collection install -p /work/collections community.docker community.general
```

### Verbindung testen

```bash
docker compose -f Docker_compose.yml exec ansible-web \
  ansible all -i /work/inventory/RPI_A.ini -m ping
```

### Playbook per CLI im Container ausführen

```bash
docker compose -f Docker_compose.yml exec ansible-web \
  ansible-playbook -i /work/inventory/RPI_A.ini /work/Job_Ping.yml
```

### SSH-Schlüssel statt Passwort nutzen

Schlüssel read-only einbinden:

```yaml
    volumes:
      - .:/work
      - ~/.ssh/id_ed25519:/root/.ssh/id_ed25519:ro
```

Inventory-Eintrag ohne Passwort:

```ini
[rpi]
192.168.178.110 ansible_user=pi ansible_ssh_private_key_file=/root/.ssh/id_ed25519
```

### Neue Raspberry Pis hinzufügen

1. Neue Datei in `inventory/` anlegen (siehe unten).
2. Seite neu laden – das Inventory erscheint automatisch in der Auswahl.

### Konfiguration über Umgebungsvariablen

| Variable | Beschreibung |
|----------|--------------|
| `ANSIBLE_COLLECTIONS_PATH` | Speicherort der Collections (`/work/collections`) |
| `FLASK_DEBUG` | In der Compose-Datei gesetzt (`"1"`); in Produktion entfernen |

## Inventories

Beispiel `inventory/RPI_A.ini`:

```ini
[rpi]
192.168.178.110 ansible_user=pi ansible_become_password=CHANGE_ME
```

Passwörter besser mit [Ansible Vault](https://docs.ansible.com/ansible/latest/vault_guide/index.html) oder SSH-Schlüsseln verwalten.

## Playbooks

| Playbook | Zweck |
|----------|-------|
| `Check_IsOnline.yml`, `Job_Ping.yml` | Erreichbarkeit prüfen / MAC-Adresse anzeigen |
| `Job_Update.yml` | Systemupdates |
| `Job_Restart.yml`, `Job_Shutdown.yml` | Neustart / Herunterfahren |
| `Job_gitClone.yml`, `Job_Artifactory.yml` | Git-Clone / Artifactory |
| `Config_wlan.yml`, `Setup_VLan.yml` | Netzwerk (WLAN, VLAN) |
| `Setup_general.yml`, `Setup_cockpit.yml`, `Setup_usb.yml` | Einrichtung (Basis, Cockpit, USB) |
| `site.yml` | Sammel-Playbook (Tasks aus `tasks/`) |

Neue Playbooks einfach als `*.yml` mit `hosts:` im Projektverzeichnis ablegen.

## Sicherheitshinweise

- Die Weboberfläche hat **keine Authentifizierung** und kann Befehle als `root` auf Zielhosts ausführen. Nur im vertrauenswürdigen Netz betreiben, z. B. Port nur lokal binden: `"127.0.0.1:5000:5000"`.
- Keine echten Passwörter ins Repository committen; Standardpasswörter (`pi`) ändern.
- `host_key_checking = False` in `ansible.cfg` ist bequem, aber unsicher.

## Fehlersuche

| Problem | Lösung |
|---------|--------|
| Keine Playbooks/Inventories sichtbar | Volume prüfen: Projekt muss nach `/work` gemountet sein |
| `community.docker` nicht gefunden | Collections installieren (siehe oben) |
| SSH-Timeout / unreachable | Netzwerk, IP, Benutzer und Passwort prüfen; Container braucht Zugriff auf das LAN |
| Logs ansehen | `docker compose logs -f` bzw. `ansible.log` im Projektordner |
