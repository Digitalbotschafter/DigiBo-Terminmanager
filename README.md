# DigiBo Terminmanager

Interne, deutschsprachige Flask-Anwendung zur Verwaltung von Beratungssitzungen. Es gibt **keine öffentliche Buchungsseite**: Sitzung, Buchung und Warteliste können ausschließlich angemeldete Administratoren verwalten.

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

Initialen Administrator anlegen und Anwendung starten:

```powershell
python create_admin.py
python app.py
```

Anschließend `http://127.0.0.1:5000` öffnen und mit `admin` / `admin123` anmelden. Dieses Kennwort ist ausschließlich für die lokale Ersteinrichtung gedacht. Ändern Sie es vor jedem Produktiveinsatz; der Admin-Datensatz speichert nur einen Werkzeug-Passwort-Hash. Es gibt in dieser minimalen Oberfläche keine Passwortänderungsfunktion; vor öffentlichem Betrieb sollte eine solche Funktion ergänzt oder der Hash kontrolliert erneuert werden.

## Funktionen

- Geschützter Admin-Bereich, CSRF-geschützte zustandsändernde Formulare und sichere HTTP-only SameSite-Cookies.
- Sitzungen mit 15-Minuten-Zeitfenstern einschließlich der angegebenen Endzeit.
- Serverseitige Prüfung auf Endzeit nach Startzeit und Viertelstundenraster.
- Admin-verwaltete Buchungen, Reservierungen und Wartelisten; Buchungsdaten sind nicht öffentlich abrufbar.

## Tests

```powershell
python -m pytest -q
```
