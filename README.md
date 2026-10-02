# RPI-AnsibleService

Kleine Flask-Weboberfläche zum Ausführen von Ansible-Playbooks auf Raspberry Pis (oder anderen Hosts). Im Browser wird ein Inventory und ein Playbook gewählt; die App startet `ansible-playbook` und zeigt die Ausgabe an.

## Inhalt

- [Funktionen](#funktionen)
- [Projektstruktur](#projektstruktur)
- [Voraussetzungen](#voraussetzungen)
- [Schnellstart mit Docker Compose](#schnellstart-mit-docker-compose)
- [Entwicklungsmodus](#entwicklungsmodus)
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
| `app.py` | Flask-Anwendung (Projektpfad automatisch, optional `APP_DIR`) |
| `Dockerfile` | Eigenständiges Image: Python 3.12, Ansible, Collections, Projektdateien |
| `Docker_compose.yml` | Compose-Datei (baut das Image) |
| `Docker_compose.dev.yml` | Override für die Entwicklung (Code als Volume) |
| `ansible.cfg` | Ansible-Konfiguration (`host_key_checking = False`, Log `ansible.log`) |
| `inventory/` | Inventories, z. B. `RPI_A.ini`, `RPI_B.ini`, `Team_X.ini` |
| `inventory.ini` | Standard-Inventory für die CLI-Nutzung |
| `Job_*.yml`, `Setup_*.yml`, `Config_wlan.yml`, `Check_IsOnline.yml`, `site.yml` | Playbooks |
| `tasks/` | Wiederverwendbare Task-Dateien (Docker, Portainer, Python, Git, Cockpit, USB, VLAN …) |
| `templates/`, `static/` | HTML-Templates, CSS und JS der Weboberfläche |
| `collections/` | Ansible-Collections (beim Image-Build installiert, nicht im Git) |

## Voraussetzungen

- Docker und Docker Compose v2 (`docker compose`)
- Netzwerkzugriff vom Container zu den Zielhosts (SSH, Port 22)
- SSH-Zugang (Passwort oder Schlüssel) zu den Zielhosts

## Schnellstart mit Docker Compose

Das Image ist eigenständig („to go“): `Dockerfile` installiert Abhängigkeiten und Collections und kopiert das gesamte Projekt nach `/app`. Der Projektpfad wird automatisch ermittelt (Verzeichnis von `app.py`, überschreibbar mit `APP_DIR`). Es ist kein Volume und keine Pfadanpassung nötig.

```bash
git clone https://github.com/danygutmann/RPI-AnsibleService.git
cd RPI-AnsibleService
docker compose -f Docker_compose.yml up -d --build
```

Öffnen: <http://localhost:5000>. Stoppen: `docker compose -f Docker_compose.yml down`.

Inventories und Playbooks sind im Image enthalten; nach Änderungen neu bauen (`up -d --build`).

## Entwicklungsmodus

Für Änderungen ohne Neubau den lokalen Code einbinden:

```bash
docker compose -f Docker_compose.yml -f Docker_compose.dev.yml up -d --build
```

## Initialisierung in Docker

### Collections

Sind bereits im Image enthalten. Bei Bedarf nachinstallieren:

```bash
docker compose -f Docker_compose.yml exec ansible-web \
  ansible-galaxy collection install -p /app/collections community.docker community.general
```

### Verbindung testen

```bash
docker compose -f Docker_compose.yml exec ansible-web \
  ansible all -i /app/inventory/RPI_A.ini -m ping
```

### Playbook per CLI im Container ausführen

```bash
docker compose -f Docker_compose.yml exec ansible-web \
  ansible-playbook -i /app/inventory/RPI_A.ini /app/Job_Ping.yml
```

### SSH-Schlüssel statt Passwort nutzen

Schlüssel read-only einbinden (in der Compose-Datei):

```yaml
    volumes:
      - ~/.ssh/id_ed25519:/root/.ssh/id_ed25519:ro
```

Inventory-Eintrag ohne Passwort:

```ini
[rpi]
192.168.178.110 ansible_user=pi ansible_ssh_private_key_file=/root/.ssh/id_ed25519
```

### Neue Raspberry Pis hinzufügen

1. Neue Datei in `inventory/` anlegen (siehe unten).
2. Image neu bauen (oder Entwicklungsmodus nutzen) – das Inventory erscheint automatisch in der Auswahl.

### Konfiguration über Umgebungsvariablen

| Variable | Beschreibung |
|----------|--------------|
| `APP_DIR` | Projektpfad (Standard: Verzeichnis von `app.py`, im Image `/app`) |
| `ANSIBLE_COLLECTIONS_PATH` | Speicherort der Collections (`/app/collections`) |
| `ANSIBLE_LOG_PATH` | Ansible-Logdatei (`/tmp/ansible.log`) |

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
| Keine Playbooks/Inventories sichtbar | Image neu bauen (`up -d --build`); im Entwicklungsmodus Volume prüfen |
| `community.docker` nicht gefunden | Collections installieren (siehe oben) |
| SSH-Timeout / unreachable | Netzwerk, IP, Benutzer und Passwort prüfen; Container braucht Zugriff auf das LAN |
| Logs ansehen | `docker compose logs -f` |
