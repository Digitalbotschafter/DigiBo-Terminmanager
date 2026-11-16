"""Set an administrator password without exposing it in shell history."""

import getpass
import os
import secrets

os.environ.setdefault("SECRET_KEY", secrets.token_hex(32))

from app import create_app
from models import Admin, db


def main():
    username = input("Benutzername des Administrators: ").strip()
    password = getpass.getpass("Neues Passwort (mindestens 12 Zeichen): ")
    confirmation = getpass.getpass("Neues Passwort wiederholen: ")

    if len(password) < 12:
        raise SystemExit("Das Passwort muss mindestens 12 Zeichen lang sein.")
    if password != confirmation:
        raise SystemExit("Die Passwörter stimmen nicht überein.")

    app = create_app()
    with app.app_context():
        admin = Admin.query.filter_by(username=username).first()
        if admin is None:
            raise SystemExit(f"Administrator „{username}“ wurde nicht gefunden.")
        admin.set_password(password)
        db.session.commit()
        print(f"Das Passwort für „{username}“ wurde geändert.")


if __name__ == "__main__":
    main()
