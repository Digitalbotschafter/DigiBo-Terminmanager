"""Shared participant booking form and 15-minute slot allocation helpers."""

import secrets
from datetime import datetime, timedelta

from flask_wtf import FlaskForm
from sqlalchemy import update
from wtforms.fields.choices import SelectChoice
from wtforms import SelectField, StringField, SubmitField
from wtforms.validators import DataRequired, Email, Length, Optional

from models import Booking, Session, Slot, db

BOOKING_DURATIONS = (15, 30)


class BookingForm(FlaskForm):
    slot_id = SelectField("Beginn", coerce=int, validators=[Optional()])
    name = StringField("Name", validators=[DataRequired(), Length(max=160)])
    email = StringField("E-Mail", validators=[DataRequired(), Email(), Length(max=254)])
    telefon = StringField("Telefon", validators=[Optional(), Length(max=50)])
    dauer = SelectField(
        "Dauer",
        coerce=int,
        choices=[
            SelectChoice("15", "15 Minuten"),
            SelectChoice("30", "30 Minuten"),
        ],
        default=15,
        validators=[DataRequired()],
    )
    submit = SubmitField("Termin buchen")


def available_booking_slots(session, duration, now=None):
    """Return free starts that have enough consecutive 15-minute slots."""
    if duration not in BOOKING_DURATIONS:
        return []

    now = now or datetime.now()
    session_end = datetime.combine(session.datum, session.endzeit)
    slots_by_time = {slot.zeitpunkt: slot for slot in session.slots}
    available = []

    for slot in session.slots:
        if slot.status != "frei" or slot.zeitpunkt <= now:
            continue
        if slot.zeitpunkt + timedelta(minutes=duration) > session_end:
            continue

        required_times = (
            slot.zeitpunkt + timedelta(minutes=offset)
            for offset in range(0, duration, 15)
        )
        if all(
            (required_slot := slots_by_time.get(moment)) is not None
            and required_slot.status == "frei"
            for moment in required_times
        ):
            available.append(slot)

    return available


def booking_slot_options(session, now=None):
    """Return start slots paired with the durations available at each start."""
    durations_by_slot = {}
    slots_by_id = {}
    for duration in BOOKING_DURATIONS:
        for slot in available_booking_slots(session, duration, now=now):
            durations_by_slot.setdefault(slot.id, []).append(duration)
            slots_by_id[slot.id] = slot
    return [
        (slots_by_id[slot_id], durations)
        for slot_id, durations in sorted(
            durations_by_slot.items(), key=lambda item: slots_by_id[item[0]].zeitpunkt
        )
    ]


def save_booking(session, slot_id, name, email, telefon, duration):
    """Atomically occupy the requested slot(s) and create the booking."""
    if duration not in BOOKING_DURATIONS:
        return False

    available = {
        slot.id: slot for slot in available_booking_slots(session, duration)
    }
    if slot_id not in available:
        return False

    start_slot = available[slot_id]
    required_slots = [start_slot]
    if duration == 30:
        following_slot = next(
            (
                slot for slot in session.slots
                if slot.zeitpunkt == start_slot.zeitpunkt + timedelta(minutes=15)
            ),
            None,
        )
        if following_slot is None:
            return False
        required_slots.append(following_slot)

    for index, slot in enumerate(required_slots):
        result = db.session.execute(
            update(Slot)
            .where(Slot.id == slot.id, Slot.status == "frei")
            .values(status="belegt" if index == 0 else "reserviert")
        )
        if result.rowcount != 1:
            db.session.rollback()
            return False

    db.session.add(
        Booking(
            slot_id=start_slot.id,
            name=name,
            email=email,
            telefon=telefon,
            dauer=duration,
            token=secrets.token_urlsafe(24),
        )
    )
    db.session.commit()
    return True


def is_extension_slot(slot):
    """Whether a reserved slot is the second half of a 30-minute booking."""
    previous_time = slot.zeitpunkt - timedelta(minutes=15)
    return any(
        previous.zeitpunkt == previous_time
        and previous.booking is not None
        and previous.booking.dauer == 30
        for previous in slot.session.slots
    )


def delete_booking_and_release_slots(booking):
    """Delete a booking and free all slots occupied by its duration."""
    start_slot = booking.slot
    if booking.dauer == 30:
        following_slot = next(
            (
                slot for slot in start_slot.session.slots
                if slot.zeitpunkt == start_slot.zeitpunkt + timedelta(minutes=15)
            ),
            None,
        )
        if following_slot is not None and following_slot.status == "reserviert":
            following_slot.status = "frei"
    start_slot.status = "frei"
    db.session.delete(booking)
    db.session.commit()
