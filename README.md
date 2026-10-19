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

- Weboberfläche (Port `5000`) mit Runner (`/`), Inventories (`/inventories`), Playbooks (`/playbooks`) und Tasks (`/tasks`)
- Erkennt automatisch alle `*.yml`/`*.yaml`-Playbooks in `jobs/` (Dateien mit `hosts:` oder `import_playbook:`)
- Erkennt Inventories im Ordner `inventory/` (`.ini`, `.yml`, `.yaml`)
- Ermöglicht das Bearbeiten und Anlegen von Playbooks, Tasks und Inventories im Browser
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
| `jobs/` | Ausführbare Playbooks, z. B. Jobs, Setup-Dateien und `site.yml` |
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
  ansible-playbook -i /app/inventory/RPI_A.ini /app/jobs/Job_Ping.yml
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

1. Neue Datei in `inventory/` anlegen oder über die Inventories-Seite im Browser erstellen.
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
| `jobs/site.yml` | Sammel-Playbook (Tasks aus `tasks/`) |

Neue Playbooks einfach als `*.yml` mit `hosts:` in `jobs/` ablegen oder über die Playbook-Übersicht erstellen. Wiederverwendbare Tasks verwaltest du unter `/tasks`.

## SSH-Schlüssel und ZAP-Hosting (externe Linux-Server)

Private Schlüssel werden **nie** ins Image, nach Git oder über die Weboberfläche bereitgestellt, sondern per read-only Mount eingebunden.

1. Schlüssel auf dem NAS ablegen, z. B. `/volume1/docker/secrets/zap_hosting_rsa`, außerhalb des Repositories:
   `chmod 600 zap_hosting_rsa` und Eigentümer = Benutzer, der den Container betreibt (der Container läuft als `root`, dort genügt `600`).
2. Hostpfad konfigurieren (`.env` neben der Compose-Datei oder Portainer-Variable; **ohne** Schlüsselinhalt):
   `SSH_KEY_HOST_PATH=/volume1/docker/secrets/zap_hosting_rsa`
   Optional: `SSH_KEY_CONTAINER_PATH` (Standard `/run/secrets/zap_hosting_rsa`). Ist `SSH_KEY_HOST_PATH` leer/nicht gesetzt, wird `/dev/null` gemountet: der Container startet, der Verbindungstest meldet aber „kein gültiger privater SSH-Schlüssel“. Bestehende Volumes/Daten bleiben unberührt.
3. Inventory anlegen (Seite *Inventories*, Vorlage `inventory/ZAP_Hosting.ini.example`, nur Platzhalter):

```ini
[zap_hosting]
server1 ansible_host=SERVER_IP_1 ansible_user=SERVER_USER_1
server2 ansible_host=SERVER_IP_2 ansible_user=SERVER_USER_2 ansible_port=2222

[zap_hosting:vars]
ansible_ssh_private_key_file=/run/secrets/zap_hosting_rsa
```

Gruppenschlüssel stehen in `[gruppe:vars]`; ein individueller Schlüssel pro Server wird als `ansible_ssh_private_key_file=...` an der Host-Zeile gesetzt. Benutzer und Port: `ansible_user`, `ansible_port`. Bestehende Inventories werden nicht verändert.

### Verbindungstest

Weboberfläche: *Inventories → Verbindungstest* (`/connection-test`), Inventory und optional Host wählen. Es läuft `ansible <host|all> -i inventory/<datei> -m ping` (nur lesend, Argumentliste, nur bekannte Inventory-Dateien und Hosts). Vorab wird der Schlüssel geprüft (fehlt / nicht lesbar / kein privater Schlüssel); Schlüsselinhalte werden nie ausgegeben.
CLI: `docker exec rpi-ansible-service ansible all -i inventory/ZAP_Hosting.ini -m ping`
Hinweis: `ping` benötigt Python auf dem Zielsystem.

### Fehlersuche SSH

| Meldung | Ursache |
|---|---|
| Schlüsseldatei nicht gefunden | Mount/`SSH_KEY_HOST_PATH` prüfen |
| nicht lesbar | Rechte (`600`) und Eigentümer prüfen |
| Anmeldung verweigert | Benutzer falsch oder Schlüssel nicht beim Server hinterlegt |
| Zeitüberschreitung / kein Weg / abgelehnt | IP, Port, Firewall prüfen |
| Python fehlt | Python auf dem Zielsystem installieren |

### Geschützte Schlüssel (Passphrase)

Die Passphrase wird nicht entfernt oder gespeichert. Empfohlen: einen dedizierten, unverschlüsselten Schlüssel nur für diesen Zweck mit eingeschränkten Rechten beim Provider verwenden, oder `ssh-agent` mit `SSH_AUTH_SOCK` in den Container durchreichen.

### Host-Key-Prüfung

`ansible.cfg` setzt weiterhin `host_key_checking = False` (unverändert, unsicher: Man-in-the-Middle möglich). Sicherer: `host_key_checking = True` setzen und eine `known_hosts` read-only nach `/root/.ssh/known_hosts` mounten (Inhalt via `ssh-keyscan -H SERVER_IP_1` nach Prüfung des Fingerprints).

### Sicherheit und Backups

Die Weboberfläche hat keine Authentifizierung und kann Inventories/Playbooks ändern; Zugriff nur im vertrauenswürdigen Netz oder über einen Reverse-Proxy mit Authentifizierung (separat von der Schlüsselverwaltung). Schlüsseldatei separat sichern (nicht ins Repo-Backup). Tests: `pip install flask pytest && python -m pytest tests`.

## Sicherheitshinweise

- Die Weboberfläche hat **keine Authentifizierung**, kann Dateien im Projekt ändern und Befehle als `root` auf Zielhosts ausführen. Nur im vertrauenswürdigen Netz betreiben, z. B. Port nur lokal binden: `"127.0.0.1:5000:5000"`.
- Keine echten Passwörter ins Repository committen; Standardpasswörter (`pi`) ändern.
- `host_key_checking = False` in `ansible.cfg` ist bequem, aber unsicher.

## Fehlersuche

| Problem | Lösung |
|---------|--------|
| Keine Playbooks/Inventories sichtbar | Image neu bauen (`up -d --build`); im Entwicklungsmodus Volume prüfen |
| `community.docker` nicht gefunden | Collections installieren (siehe oben) |
| SSH-Timeout / unreachable | Netzwerk, IP, Benutzer und Passwort prüfen; Container braucht Zugriff auf das LAN |
| Logs ansehen | `docker compose logs -f` |
