from datetime import date, time
from datetime import timedelta

import pytest

from app import create_app, generate_slot_times
from models import Admin, db


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
        admin = Admin(username="admin", email="admin@example.test")
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
        admin = Admin(username="admin", email="admin@example.test")
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
