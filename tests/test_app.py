import sqlite3
from datetime import date, time
from datetime import timedelta

import pytest

from app import create_app, generate_slot_times
from models import Admin, Booking, Session, Slot, WaitingList, db


@pytest.fixture
def app():
    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test-key-not-for-production",
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "WTF_CSRF_ENABLED": False,
        }
    )
    yield app
    with app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def add_session(app, start=time(9, 0), end=time(10, 0), statuses=None):
    session_date = date.today() + timedelta(days=14)
    with app.app_context():
        session = Session(
            datum=session_date,
            startzeit=start,
            endzeit=end,
            ort="Bürgerhaus",
            beschreibung="Digitale Unterstützung",
        )
        db.session.add(session)
        db.session.flush()
        slot_ids = {}
        for moment in generate_slot_times(session_date, start, end):
            slot_status = (statuses or {}).get(moment.strftime("%H:%M"), "frei")
            slot = Slot(
                session_id=session.id,
                zeitpunkt=moment,
                status=slot_status,
            )
            db.session.add(slot)
            db.session.flush()
            slot_ids[moment.strftime("%H:%M")] = slot.id
        db.session.commit()
        return session.id, slot_ids


def test_slot_generation_includes_end_time():
    slots = generate_slot_times(date(2026, 12, 1), time(9, 0), time(10, 0))
    assert [slot.strftime("%H:%M") for slot in slots] == [
        "09:00", "09:15", "09:30", "09:45", "10:00"
    ]


@pytest.mark.parametrize(
    ("start", "end"),
    [(time(10, 0), time(9, 0)), (time(9, 5), time(10, 0)), (time(9, 0), time(10, 5))],
)
def test_slot_generation_rejects_invalid_times(start, end):
    with pytest.raises(ValueError):
        generate_slot_times(date(2026, 12, 1), start, end)


def test_admin_pages_require_authentication(client):
    response = client.get("/admin/")
    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]
    response = client.get("/admin/sitzungen")
    assert response.status_code == 302
    response = client.get("/admin/administratoren")
    assert response.status_code == 302


def test_public_home_and_session_list_are_available_without_login(app, client):
    add_session(app)

    home = client.get("/")
    sessions = client.get("/sitzungen")

    assert home.status_code == 200
    assert "Termin buchen".encode() in home.data
    assert sessions.status_code == 200
    assert "Bürgerhaus".encode() in sessions.data


def test_existing_database_gets_waitlist_duration_column(tmp_path):
    database_path = tmp_path / "legacy.sqlite"
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "CREATE TABLE waiting_list ("
            "id INTEGER PRIMARY KEY, session_id INTEGER NOT NULL, "
            "name VARCHAR(160) NOT NULL, email VARCHAR(254) NOT NULL, "
            "telefon VARCHAR(50) NOT NULL, created_at DATETIME NOT NULL)"
        )

    create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "migration-test-key",
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{database_path.as_posix()}",
            "WTF_CSRF_ENABLED": False,
        }
    )

    with sqlite3.connect(database_path) as connection:
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(waiting_list)")
        }
    assert "dauer" in columns


def test_login_post_requires_csrf_token():
    csrf_app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "csrf-test-key",
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
        }
    )
    response = csrf_app.test_client().post(
        "/auth/login", data={"username": "admin", "password": "admin123"}
    )
    assert response.status_code == 400


def test_admin_password_is_hashed_and_login_protects_dashboard(app, client):
    with app.app_context():
        admin = Admin(username="admin", email="admin@example.com")
        admin.set_password("admin123")
        db.session.add(admin)
        db.session.commit()
        assert admin.password_hash != "admin123"
        assert admin.check_password("admin123")
    response = client.post(
        "/auth/login",
        data={"username": "admin", "password": "admin123"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Ubersicht" in response.data or "Übersicht".encode() in response.data


def test_admin_can_create_session_with_end_time_slot(app, client):
    with app.app_context():
        admin = Admin(username="admin", email="admin@example.com")
        admin.set_password("admin123")
        db.session.add(admin)
        db.session.commit()
        session_date = (date.today() + timedelta(days=14)).isoformat()

    client.post("/auth/login", data={"username": "admin", "password": "admin123"})
    response = client.post(
        "/admin/sitzungen/neu",
        data={
            "datum": session_date,
            "startzeit": "09:00",
            "endzeit": "10:00",
            "ort": "Bürgerhaus",
            "beschreibung": "",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "5 Zeitfenster".encode() in response.data
    assert b"10:00" in response.data


def test_participant_can_book_30_minutes_and_reserves_following_slot(app, client):
    session_id, slot_ids = add_session(app)
    response = client.post(
        f"/sitzungen/{session_id}",
        data={
            "slot_id": str(slot_ids["09:15"]),
            "name": "Teilnehmer Beispiel",
            "email": "teilnehmer@example.com",
            "telefon": "0123456789",
            "dauer": "30",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "wurde gebucht".encode() in response.data
    with app.app_context():
        start = db.session.get(Slot, slot_ids["09:15"])
        following = db.session.get(Slot, slot_ids["09:30"])
        booking = Booking.query.filter_by(slot_id=start.id).one()
        assert booking.dauer == 30
        assert start.status == "belegt"
        assert following.status == "reserviert"


def test_30_minute_booking_without_two_free_slots_is_added_to_waitlist(app, client):
    session_id, slot_ids = add_session(
        app,
        statuses={
            "09:15": "reserviert",
            "09:30": "reserviert",
            "09:45": "reserviert",
            "10:00": "reserviert",
        },
    )
    response = client.post(
        f"/sitzungen/{session_id}",
        data={
            "slot_id": "",
            "name": "Teilnehmer Beispiel",
            "email": "warteliste@example.com",
            "telefon": "",
            "dauer": "30",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "automatisch auf die Warteliste gesetzt".encode() in response.data
    with app.app_context():
        assert Booking.query.count() == 0
        entry = WaitingList.query.one()
        assert entry.email == "warteliste@example.com"
        assert entry.dauer == 30
        assert db.session.get(Slot, slot_ids["09:00"]).status == "frei"


def test_participant_booking_form_has_no_separate_waitlist_form(app, client):
    session_id, _ = add_session(app)
    response = client.get(f"/sitzungen/{session_id}")

    assert response.status_code == 200
    assert "Auf Warteliste setzen".encode() not in response.data
    assert "booking-duration".encode() in response.data


def test_30_minute_booking_must_fit_before_session_end(app, client):
    session_id, slot_ids = add_session(app)
    response = client.post(
        f"/sitzungen/{session_id}",
        data={
            "slot_id": str(slot_ids["09:45"]),
            "name": "Teilnehmer Beispiel",
            "email": "teilnehmer@example.com",
            "telefon": "",
            "dauer": "30",
        },
    )

    assert response.status_code == 200
    with app.app_context():
        assert Booking.query.count() == 0
        assert WaitingList.query.count() == 0


def test_booking_duration_over_30_minutes_is_rejected(app, client):
    session_id, slot_ids = add_session(app)
    response = client.post(
        f"/sitzungen/{session_id}",
        data={
            "slot_id": str(slot_ids["09:00"]),
            "name": "Teilnehmer Beispiel",
            "email": "teilnehmer@example.com",
            "telefon": "",
            "dauer": "45",
        },
    )

    assert response.status_code == 200
    with app.app_context():
        assert Booking.query.count() == 0
        assert WaitingList.query.count() == 0


def test_admin_30_minute_booking_reserves_and_deletion_releases_both_slots(app, client):
    session_id, slot_ids = add_session(app)
    with app.app_context():
        admin = Admin(username="admin", email="admin@example.com")
        admin.set_password("admin123")
        db.session.add(admin)
        db.session.commit()

    client.post("/auth/login", data={"username": "admin", "password": "admin123"})
    client.post(
        f"/admin/sitzungen/{session_id}/buchungen",
        data={
            "slot_id": str(slot_ids["09:15"]),
            "name": "Interne Buchung",
            "email": "intern@example.com",
            "telefon": "",
            "dauer": "30",
        },
    )
    with app.app_context():
        booking = Booking.query.one()
        booking_id = booking.id
        assert db.session.get(Slot, slot_ids["09:30"]).status == "reserviert"

    client.post(f"/admin/slots/{slot_ids['09:30']}/reservierung")
    with app.app_context():
        assert db.session.get(Slot, slot_ids["09:30"]).status == "reserviert"

    client.post(f"/admin/buchungen/{booking_id}/loeschen")
    with app.app_context():
        assert db.session.get(Slot, slot_ids["09:15"]).status == "frei"
        assert db.session.get(Slot, slot_ids["09:30"]).status == "frei"


def test_admin_can_create_another_admin_with_hashed_password(app, client):
    with app.app_context():
        admin = Admin(username="admin", email="admin@example.com")
        admin.set_password("admin123")
        db.session.add(admin)
        db.session.commit()

    client.post("/auth/login", data={"username": "admin", "password": "admin123"})
    response = client.post(
        "/admin/administratoren",
        data={
            "username": "zweiter-admin",
            "email": "zweiter@example.com",
            "password": "Ein-Sicheres-Passwort-2026",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "zweiter-admin".encode() in response.data
    with app.app_context():
        created_admin = Admin.query.filter_by(username="zweiter-admin").one()
        assert created_admin.check_password("Ein-Sicheres-Passwort-2026")
        assert created_admin.password_hash != "Ein-Sicheres-Passwort-2026"


def test_admin_can_edit_email_and_password(app, client):
    with app.app_context():
        admin = Admin(username="admin", email="admin@example.com")
        admin.set_password("admin123")
        other_admin = Admin(username="other", email="other@example.com")
        other_admin.set_password("Another-Secure-Password-2026")
        db.session.add_all([admin, other_admin])
        db.session.commit()
        other_admin_id = other_admin.id

    client.post("/auth/login", data={"username": "admin", "password": "admin123"})
    response = client.post(
        f"/admin/administratoren/{other_admin_id}/bearbeiten",
        data={
            "username": "other",
            "email": "updated@example.com",
            "password": "Updated-Secure-Password-2026",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200

    with app.app_context():
        updated_admin = db.session.get(Admin, other_admin_id)
        assert updated_admin.email == "updated@example.com"
        assert updated_admin.check_password("Updated-Secure-Password-2026")


def test_admin_can_delete_another_admin_and_cannot_delete_last_admin(app, client):
    with app.app_context():
        admin = Admin(username="admin", email="admin@example.com")
        admin.set_password("admin123")
        other_admin = Admin(username="other", email="other@example.com")
        other_admin.set_password("Another-Secure-Password-2026")
        db.session.add_all([admin, other_admin])
        db.session.commit()
        admin_id = admin.id
        other_admin_id = other_admin.id

    client.post("/auth/login", data={"username": "admin", "password": "admin123"})
    client.post(
        f"/admin/administratoren/{other_admin_id}/loeschen", follow_redirects=True
    )
    with app.app_context():
        assert db.session.get(Admin, other_admin_id) is None

    last_admin_delete = client.post(
        f"/admin/administratoren/{admin_id}/loeschen", follow_redirects=True
    )
    assert last_admin_delete.status_code == 200
    with app.app_context():
        assert db.session.get(Admin, admin_id) is not None


def test_admin_can_delete_own_account_if_another_admin_remains(app, client):
    with app.app_context():
        admin = Admin(username="admin", email="admin@example.com")
        admin.set_password("admin123")
        other_admin = Admin(username="other", email="other@example.com")
        other_admin.set_password("Another-Secure-Password-2026")
        db.session.add_all([admin, other_admin])
        db.session.commit()
        admin_id = admin.id
        other_admin_id = other_admin.id

    client.post("/auth/login", data={"username": "admin", "password": "admin123"})
    response = client.post(
        f"/admin/administratoren/{admin_id}/loeschen", follow_redirects=True
    )
    assert response.status_code == 200
    assert "Anmelden".encode() in response.data
    with app.app_context():
        assert db.session.get(Admin, admin_id) is None
        assert db.session.get(Admin, other_admin_id) is not None
