# DigiBo Terminmanager

Deutschsprachige Flask-Anwendung für die Verwaltung und öffentliche Buchung von Digitalsprechstunden der Digitalbotschafter Pirmasenser Land.

## Voraussetzungen

- Python 3.12
- PowerShell (Windows) oder eine Shell mit Python und `venv`

## Lokale Installation (PowerShell)

```powershell
cd "C:\Pfad\zum\Workspace\digibo_sprechstunde"
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Erzeugen Sie einen eigenen Sitzungsschlüssel und setzen Sie ihn für das aktuelle Terminal. Der Schlüssel ist absichtlich nicht im Quellcode hinterlegt:

```powershell
$env:SECRET_KEY = python -c "import secrets; print(secrets.token_hex(32))"
```

Optional kann `DATABASE_URL` eine andere SQLAlchemy-Datenbankadresse setzen. Standardmäßig liegt die SQLite-Datei unter `instance/digibo.db` und wird beim Anwendungsstart automatisch initialisiert. Für HTTPS-Produktionsbetrieb setzen Sie zusätzlich `$env:COOKIE_SECURE = "1"` und verwenden Sie einen persistenten, geheimen `SECRET_KEY`.

Für GitHub ist nur `instance/digibo-template.db` vorgesehen. Diese Vorlage enthält das Datenbankschema, aber keine Admin-, Termin- oder Kontaktdaten. Die verwendete Laufzeitdatenbank `instance/digibo.db` bleibt von Git ausgeschlossen. SQLite-Dateien sind lokale Snapshots und keine gemeinsam nutzbare Live-Datenbank.

Initialen Administrator sicher anlegen und Anwendung starten:

```powershell
python create_admin.py
python app.py
```

Das Skript fragt Benutzername, E-Mail und ein mindestens 12 Zeichen langes Passwort ab; das Passwort wird nicht angezeigt. Anschließend `http://127.0.0.1:5000` öffnen. Teilnehmende können über **Termin buchen** kommende Sitzungen auswählen und ohne Anmeldung buchen. Administratoren melden sich über **Admin-Anmeldung** an; gespeichert wird nur ein Werkzeug-Passwort-Hash.

## Funktionen

- Öffentliche Sitzungsübersicht und Buchung ohne Teilnehmerkonto; Teilnehmerdaten bleiben im geschützten Admin-Bereich.
- Buchungen für genau 15 oder 30 Minuten. Eine 30-Minuten-Buchung benötigt zwei aufeinanderfolgende freie Slots; der zweite Slot wird mitreserviert.
- Wenn für die gewählte Dauer kein passender Startzeitpunkt frei ist, wird der Teilnehmer mit einem einzigen Formular automatisch auf die Warteliste gesetzt.
- Geschützter Admin-Bereich, CSRF-geschützte zustandsändernde Formulare und sichere HTTP-only SameSite-Cookies.
- Administratoren können Konten bearbeiten (Benutzername, E-Mail und optional Passwort), weitere Admins anlegen und Konten löschen. Neue und geänderte Passwörter müssen mindestens 12 Zeichen lang sein. Das letzte Admin-Konto kann nicht gelöscht werden; beim Löschen des eigenen Kontos erfolgt die Abmeldung.
- Sitzungen mit 15-Minuten-Zeitfenstern einschließlich der angegebenen Endzeit.
- Serverseitige Prüfung auf Endzeit nach Startzeit und Viertelstundenraster.
- Admin-verwaltete Sitzungen, Buchungen und Wartelisten; die manuelle zweite Wartelisten-Eingabemaske wurde entfernt.
- Das Schema bestehender Datenbanken wird beim Start um die gewünschte Wartelistendauer erweitert.

## Kostenloses Hosting auf PythonAnywhere EU

Die kostenlose Beginner-Stufe stellt eine Web-App unter `https://<benutzername>.eu.pythonanywhere.com` bereit. Sie hat Einschränkungen bei Ressourcen und ausgehendem Netzwerkzugriff; ein eigener Domainname ist im kostenlosen Tarif nicht enthalten. Die App verwendet auf PythonAnywhere die SQLite-Datei unter `instance/digibo.db` im Benutzerverzeichnis.

1. Erstellen Sie ein kostenloses Konto auf [eu.pythonanywhere.com](https://eu.pythonanywhere.com/); wählen Sie beim Anlegen der Web-App die manuelle Konfiguration mit Python 3.12.
2. Klonen Sie das öffentliche Projekt in einer Bash-Konsole und installieren Sie die Abhängigkeiten:

   ```bash
   git clone https://github.com/Digitalbotschafter/DigiBo-Terminmanager.git
   cd DigiBo-Terminmanager
   mkvirtualenv --python=/usr/bin/python3.12 digibo-env
   pip install -r requirements.txt
   ```

3. Übertragen Sie eine freigegebene Kopie der Laufzeitdatenbank direkt über die PythonAnywhere-Dateiverwaltung nach `DigiBo-Terminmanager/instance/digibo.db`. **Laden Sie diese Datei nicht zu GitHub hoch.** Sie kann personenbezogene Teilnehmerdaten enthalten. Die App ergänzt das Wartelisten-Schema beim Start automatisch.
4. Vor dem öffentlichen Start setzen Sie das Passwort eines bestehenden Administrators sicher in der Bash-Konsole zurück:

   ```bash
   cd ~/DigiBo-Terminmanager
   workon digibo-env
   python set_admin_password.py
   ```

5. In der PythonAnywhere-Web-Konfiguration stellen Sie das virtuelle Environment auf `digibo-env` und konfigurieren Sie die WSGI-Datei so, dass vor dem Import von `app` diese Werte gesetzt werden:

   ```python
   import os
   import sys

   project_path = os.path.expanduser("~/DigiBo-Terminmanager")
   if project_path not in sys.path:
       sys.path.insert(0, project_path)

   os.environ["SECRET_KEY"] = "<zufälliger, geheimer Schlüssel>"
   os.environ["COOKIE_SECURE"] = "1"

   from app import create_app
   application = create_app()
   ```

   Erzeugen Sie den Schlüssel in der Bash-Konsole mit `python -c "import secrets; print(secrets.token_hex(32))"` und tragen Sie ihn nur in die private WSGI-Konfiguration ein, niemals in GitHub. Speichern Sie die WSGI-Datei und laden Sie die Web-App anschließend neu.

## Tests

```powershell
python -m pytest -q
```
