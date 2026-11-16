"""Admin-only appointment, booking, and waiting-list management."""

import secrets
from datetime import date, datetime

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from flask_wtf import FlaskForm
from wtforms import DateField, IntegerField, SelectField, StringField, SubmitField, TextAreaField, TimeField
from wtforms.validators import DataRequired, Email, Length, NumberRange, Optional

from app import generate_slot_times
from models import Admin, Booking, Session, Slot, WaitingList, db

admin_bp = Blueprint("admin", __name__)


class SessionForm(FlaskForm):
    datum = DateField("Datum", validators=[DataRequired()], format="%Y-%m-%d")
    startzeit = TimeField("Startzeit", validators=[DataRequired()], format="%H:%M")
    endzeit = TimeField("Endzeit", validators=[DataRequired()], format="%H:%M")
    ort = StringField("Ort", validators=[DataRequired(), Length(max=200)])
    beschreibung = TextAreaField("Beschreibung", validators=[Optional(), Length(max=5000)])
    submit = SubmitField("Sitzung anlegen")


class BookingForm(FlaskForm):
    slot_id = SelectField("Freier Termin", coerce=int, validators=[DataRequired()])
    name = StringField("Name", validators=[DataRequired(), Length(max=160)])
    email = StringField("E-Mail", validators=[DataRequired(), Email(), Length(max=254)])
    telefon = StringField("Telefon", validators=[Optional(), Length(max=50)])
    dauer = IntegerField("Dauer (Minuten)", validators=[DataRequired(), NumberRange(min=1, max=1440)])
    submit = SubmitField("Buchung speichern")


class WaitingListForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired(), Length(max=160)])
    email = StringField("E-Mail", validators=[DataRequired(), Email(), Length(max=254)])
    telefon = StringField("Telefon", validators=[Optional(), Length(max=50)])
    submit = SubmitField("Auf Warteliste setzen")


@admin_bp.before_request
def require_admin_role():
    # All endpoints in this blueprint are private; role check prevents a non-admin
    # account from gaining access if the user model is extended in the future.
    if not current_user.is_authenticated:
        return redirect(url_for("auth.login", next=request.url))
    if not isinstance(current_user._get_current_object(), Admin) or current_user.role != "admin":
        abort(403)


@admin_bp.get("/")
@login_required
def dashboard():
    now = datetime.now()
    upcoming = Session.query.filter(Session.datum >= now.date()).order_by(
        Session.datum, Session.startzeit
    ).all()
    upcoming = [
        item for item in upcoming
        if datetime.combine(item.datum, item.startzeit) >= now
    ]
    future_ids = [item.id for item in upcoming]
    booking_count = (
        Booking.query.join(Slot)
        .filter(Booking.slot_id == Slot.id, Slot.session_id.in_(future_ids), Slot.zeitpunkt >= now)
        .count()
        if future_ids
        else 0
    )
    waitlist_count = WaitingList.query.filter(WaitingList.session_id.in_(future_ids)).count() if future_ids else 0
    return render_template(
        "dashboard.html",
        sessions=upcoming,
        session_count=len(upcoming),
        booking_count=booking_count,
        waitlist_count=waitlist_count,
        now=now,
    )


@admin_bp.get("/sitzungen")
@login_required
def sessions():
    all_sessions = Session.query.order_by(Session.datum.desc(), Session.startzeit.desc()).all()
    return render_template("sessions.html", sessions=all_sessions, today=date.today())


@admin_bp.route("/sitzungen/neu", methods=["GET", "POST"])
@login_required
def create_session():
    form = SessionForm()
    if form.validate_on_submit():
        try:
            times = generate_slot_times(form.datum.data, form.startzeit.data, form.endzeit.data)
        except ValueError as exc:
            flash(str(exc), "danger")
            return render_template("create_session.html", form=form)
        session = Session(
            datum=form.datum.data,
            startzeit=form.startzeit.data,
            endzeit=form.endzeit.data,
            ort=form.ort.data.strip(),
            beschreibung=(form.beschreibung.data or "").strip(),
        )
        db.session.add(session)
        db.session.flush()
        for moment in times:
            db.session.add(Slot(session_id=session.id, zeitpunkt=moment, status="frei"))
        db.session.commit()
        flash(f"Sitzung angelegt; {len(times)} Zeitfenster wurden erstellt.", "success")
        return redirect(url_for("admin.session_detail", session_id=session.id))
    return render_template("create_session.html", form=form)


@admin_bp.get("/sitzungen/<int:session_id>")
@login_required
def session_detail(session_id):
    session = db.get_or_404(Session, session_id)
    booking_form = BookingForm()
    booking_form.slot_id.choices = [
        (slot.id, slot.zeitpunkt.strftime("%H:%M"))
        for slot in session.slots
        if slot.status == "frei"
    ]
    waitlist_form = WaitingListForm()
    return render_template(
        "session_detail.html",
        session=session,
        booking_form=booking_form,
        waitlist_form=waitlist_form,
    )


@admin_bp.post("/sitzungen/<int:session_id>/buchungen")
@login_required
def create_booking(session_id):
    session = db.get_or_404(Session, session_id)
    form = BookingForm()
    free_slots = [slot for slot in session.slots if slot.status == "frei"]
    form.slot_id.choices = [(slot.id, slot.zeitpunkt.strftime("%H:%M")) for slot in free_slots]
    if form.validate_on_submit():
        slot = db.session.get(Slot, form.slot_id.data)
        if slot is None or slot.session_id != session.id or slot.status != "frei":
            flash("Dieses Zeitfenster ist nicht mehr frei.", "danger")
        else:
            booking = Booking(
                slot_id=slot.id,
                name=form.name.data.strip(),
                email=form.email.data.strip(),
                telefon=(form.telefon.data or "").strip(),
                dauer=form.dauer.data,
                token=secrets.token_urlsafe(24),
            )
            slot.status = "belegt"
            db.session.add(booking)
            db.session.commit()
            flash("Buchung gespeichert.", "success")
    else:
        flash("Bitte prüfen Sie die Buchungsangaben.", "danger")
    return redirect(url_for("admin.session_detail", session_id=session.id))


@admin_bp.post("/buchungen/<int:booking_id>/loeschen")
@login_required
def delete_booking(booking_id):
    booking = db.get_or_404(Booking, booking_id)
    session_id = booking.slot.session_id
    booking.slot.status = "frei"
    db.session.delete(booking)
    db.session.commit()
    flash("Buchung gelöscht; das Zeitfenster ist wieder frei.", "success")
    return redirect(url_for("admin.session_detail", session_id=session_id))


@admin_bp.post("/sitzungen/<int:session_id>/warteliste")
@login_required
def create_waitlist_entry(session_id):
    session = db.get_or_404(Session, session_id)
    form = WaitingListForm()
    if form.validate_on_submit():
        db.session.add(
            WaitingList(
                session_id=session.id,
                name=form.name.data.strip(),
                email=form.email.data.strip(),
                telefon=(form.telefon.data or "").strip(),
            )
        )
        db.session.commit()
        flash("Eintrag auf der Warteliste gespeichert.", "success")
    else:
        flash("Bitte prüfen Sie die Wartelistenangaben.", "danger")
    return redirect(url_for("admin.session_detail", session_id=session.id))


@admin_bp.post("/warteliste/<int:entry_id>/loeschen")
@login_required
def delete_waitlist_entry(entry_id):
    entry = db.get_or_404(WaitingList, entry_id)
    session_id = entry.session_id
    db.session.delete(entry)
    db.session.commit()
    flash("Wartelisteneintrag gelöscht.", "success")
    return redirect(url_for("admin.session_detail", session_id=session_id))


@admin_bp.post("/slots/<int:slot_id>/reservierung")
@login_required
def toggle_slot_reservation(slot_id):
    slot = db.get_or_404(Slot, slot_id)
    if slot.status == "belegt":
        flash("Belegte Zeitfenster können nicht reserviert werden.", "warning")
    else:
        slot.status = "reserviert" if slot.status == "frei" else "frei"
        db.session.commit()
        flash("Zeitfensterstatus aktualisiert.", "success")
    return redirect(url_for("admin.session_detail", session_id=slot.session_id))
