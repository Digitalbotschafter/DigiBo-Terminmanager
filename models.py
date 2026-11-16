"""Database models for the admin-only appointment manager."""

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import CheckConstraint, UniqueConstraint
from werkzeug.security import check_password_hash, generate_password_hash

db = SQLAlchemy()


class Admin(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(254), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(30), nullable=False, default="admin")

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class Session(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    datum = db.Column(db.Date, nullable=False, index=True)
    startzeit = db.Column(db.Time, nullable=False)
    endzeit = db.Column(db.Time, nullable=False)
    ort = db.Column(db.String(200), nullable=False)
    beschreibung = db.Column(db.Text, nullable=False, default="")

    slots = db.relationship(
        "Slot", back_populates="session", cascade="all, delete-orphan", order_by="Slot.zeitpunkt"
    )
    waiting_list = db.relationship(
        "WaitingList", back_populates="session", cascade="all, delete-orphan"
    )


class Slot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(
        db.Integer, db.ForeignKey("session.id", ondelete="CASCADE"), nullable=False, index=True
    )
    zeitpunkt = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="frei")

    session = db.relationship("Session", back_populates="slots")
    booking = db.relationship(
        "Booking", back_populates="slot", cascade="all, delete-orphan", uselist=False
    )
    __table_args__ = (
        CheckConstraint("status IN ('frei', 'reserviert', 'belegt')", name="ck_slot_status"),
        UniqueConstraint("session_id", "zeitpunkt", name="uq_slot_session_time"),
    )


class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    slot_id = db.Column(
        db.Integer, db.ForeignKey("slot.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    name = db.Column(db.String(160), nullable=False)
    email = db.Column(db.String(254), nullable=False)
    telefon = db.Column(db.String(50), nullable=False, default="")
    dauer = db.Column(db.Integer, nullable=False)
    token = db.Column(db.String(64), nullable=False, unique=True)

    slot = db.relationship("Slot", back_populates="booking")
    __table_args__ = (CheckConstraint("dauer > 0", name="ck_booking_duration_positive"),)


class WaitingList(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(
        db.Integer, db.ForeignKey("session.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name = db.Column(db.String(160), nullable=False)
    email = db.Column(db.String(254), nullable=False)
    telefon = db.Column(db.String(50), nullable=False, default="")
    created_at = db.Column(db.DateTime, nullable=False, server_default=db.func.current_timestamp())

    session = db.relationship("Session", back_populates="waiting_list")
