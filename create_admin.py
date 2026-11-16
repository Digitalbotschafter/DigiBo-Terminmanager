"""Create the first administrator using a password entered securely at the prompt."""

import getpass
import os
import secrets

os.environ.setdefault("SECRET_KEY", secrets.token_hex(32))

from app import create_app
from models import Admin, db


def main():
    username = input("Benutzername [admin]: ").strip() or "admin"
    email = input("E-Mail-Adresse: ").strip().lower()
    password = getpass.getpass("Initialpasswort (mindestens 12 Zeichen): ")
    confirmation = getpass.getpass("Passwort wiederholen: ")

    if len(password) < 12:
        raise SystemExit("Das Passwort muss mindestens 12 Zeichen lang sein.")
    if password != confirmation:
        raise SystemExit("Die Passwörter stimmen nicht überein.")
    if not email:
        raise SystemExit("Eine E-Mail-Adresse ist erforderlich.")

    app = create_app()
    with app.app_context():
        existing_admin = Admin.query.filter(
            db.func.lower(Admin.username) == username.lower()
        ).first()
        if existing_admin:
            raise SystemExit(f"Administrator „{username}“ existiert bereits.")

        admin = Admin(username=username, email=email, role="admin")
        admin.set_password(password)
        db.session.add(admin)
        db.session.commit()
        print(f"Administrator „{username}“ wurde angelegt.")


if __name__ == "__main__":
    main()
