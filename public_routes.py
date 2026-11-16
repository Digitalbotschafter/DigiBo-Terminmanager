"""Public session browsing and participant booking routes."""

from datetime import datetime

from flask import Blueprint, abort, flash, redirect, render_template, url_for
from wtforms.fields.choices import SelectChoice

from booking import (
    BOOKING_DURATIONS,
    BookingForm,
    available_booking_slots,
    booking_slot_options,
    save_booking,
)
from models import Session, WaitingList, db

public_bp = Blueprint("public", __name__)


@public_bp.get("/sitzungen")
def sessions():
    now = datetime.now()
    all_sessions = Session.query.filter(Session.datum >= now.date()).order_by(
        Session.datum, Session.startzeit
    ).all()
    sessions = [
        session for session in all_sessions
        if datetime.combine(session.datum, session.endzeit) > now
    ]
    available_counts = {
        session.id: len(available_booking_slots(session, 15, now=now))
        for session in sessions
    }
    return render_template(
        "public_sessions.html",
        sessions=sessions,
        available_counts=available_counts,
    )


@public_bp.route("/sitzungen/<int:session_id>", methods=["GET", "POST"])
def session_detail(session_id):
    session = db.get_or_404(Session, session_id)
    now = datetime.now()
    if datetime.combine(session.datum, session.endzeit) <= now:
        abort(404)

    form = BookingForm()
    duration = form.dauer.data
    if duration not in BOOKING_DURATIONS:
        duration = 15
    available_slots = available_booking_slots(session, duration, now=now)
    form.slot_id.choices = [
        SelectChoice(str(slot.id), slot.zeitpunkt.strftime("%H:%M"))
        for slot in available_slots
    ]

    if form.validate_on_submit():
        name = form.name.data.strip()
        email = form.email.data.strip().lower()
        telefon = (form.telefon.data or "").strip()

        if not available_slots:
            db.session.add(
                WaitingList(
                    session_id=session.id,
                    name=name,
                    email=email,
                    telefon=telefon,
                    dauer=duration,
                )
            )
            db.session.commit()
            flash(
                "Für die gewünschte Dauer ist kein passender Termin frei. "
                "Sie wurden automatisch auf die Warteliste gesetzt.",
                "info",
            )
            return redirect(url_for("public.session_detail", session_id=session.id))

        if form.slot_id.data is None:
            form.slot_id.errors.append("Bitte wählen Sie einen freien Termin aus.")
        elif save_booking(
            session,
            form.slot_id.data,
            name,
            email,
            telefon,
            duration,
        ):
            flash(
                f"Ihr Termin um {next(slot.zeitpunkt.strftime('%H:%M') for slot in available_slots if slot.id == form.slot_id.data)} "
                f"für {duration} Minuten wurde gebucht.",
                "success",
            )
            return redirect(url_for("public.session_detail", session_id=session.id))
        else:
            flash(
                "Dieser Termin ist inzwischen belegt. Bitte wählen Sie einen anderen.",
                "warning",
            )

    return render_template(
        "public_session_detail.html",
        session=session,
        form=form,
        slot_options=booking_slot_options(session, now=now),
        available_for_duration=bool(available_slots),
    )
