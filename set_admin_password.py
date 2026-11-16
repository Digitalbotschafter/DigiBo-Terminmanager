"""Set an administrator password without exposing it in shell history."""

import argparse
import getpass
import os
import secrets
from pathlib import Path

os.environ.setdefault("SECRET_KEY", secrets.token_hex(32))

from app import create_app
from models import Admin, db


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--generate-one-time",
        action="store_true",
        help="Generate a temporary password and save it in the private home directory.",
    )
    args = parser.parse_args()

    username = input("Benutzername des Administrators: ").strip()
    password_file = Path.home() / "digibo-admin-password-onetime.txt"

    if args.generate_one_time:
        if password_file.exists():
            raise SystemExit(
                f"Die Datei {password_file} existiert bereits. "
                "Löschen Sie sie nach Prüfung oder wählen Sie einen anderen Weg."
            )
        password = secrets.token_urlsafe(24)
    else:
        password = getpass.getpass("Neues Passwort (mindestens 12 Zeichen): ")
        confirmation = getpass.getpass("Neues Passwort wiederholen: ")
        if password != confirmation:
            raise SystemExit("Die Passwörter stimmen nicht überein.")

    if len(password) < 12:
        raise SystemExit("Das Passwort muss mindestens 12 Zeichen lang sein.")
    app = create_app()
    with app.app_context():
        admin = Admin.query.filter_by(username=username).first()
        if admin is None:
            raise SystemExit(f"Administrator „{username}“ wurde nicht gefunden.")
        admin.set_password(password)
        db.session.commit()

    if args.generate_one_time:
        password_file.write_text(password, encoding="utf-8")
        password_file.chmod(0o600)
        print(
            "Ein temporäres Passwort wurde gesetzt. Rufen Sie die Datei "
            f"{password_file} nur in Ihrem privaten PythonAnywhere-Konto ab, "
            "ändern Sie das Passwort anschließend im Admin-Bereich und löschen "
            "Sie die Datei."
        )
    else:
        print(f"Das Passwort für „{username}“ wurde geändert.")


if __name__ == "__main__":
    main()
