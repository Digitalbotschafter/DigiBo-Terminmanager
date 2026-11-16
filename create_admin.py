"""Create the initial local administrator (password: admin123)."""

from app import create_app
from models import Admin, db


def main():
    app = create_app()
    with app.app_context():
        admin = Admin.query.filter_by(username="admin").first()
        if admin:
            print("Administrator 'admin' existiert bereits; es wurde nichts geändert.")
            return
        admin = Admin(username="admin", email="admin@localhost")
        admin.set_password("admin123")
        db.session.add(admin)
        db.session.commit()
        print("Administrator 'admin' wurde angelegt. Initialpasswort: admin123")
        print("Bitte das Initialpasswort vor einem Produktiveinsatz ändern.")


if __name__ == "__main__":
    main()
