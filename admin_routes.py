"""Admin-only session, booking, and waiting-list management."""

from datetime import date, datetime

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, logout_user
from flask_wtf import FlaskForm
from wtforms.fields.choices import SelectChoice
from wtforms import (
    DateField,
    PasswordField,
    StringField,
    SubmitField,
    TextAreaField,
    TimeField,
)
from wtforms.validators import DataRequired, Email, Length, Optional

from app import generate_slot_times
from booking import (
    BOOKING_DURATIONS,
    BookingForm,
    available_booking_slots,
    booking_slot_options,
    delete_booking_and_release_slots,
    is_extension_slot,
    save_booking,
)
from models import Admin, Booking, Session, Slot, WaitingList, db

admin_bp = Blueprint("admin", __name__)


class SessionForm(FlaskForm):
    datum = DateField("Datum", validators=[DataRequired()], format="%Y-%m-%d")
    startzeit = TimeField("Startzeit", validators=[DataRequired()], format="%H:%M")
    endzeit = TimeField("Endzeit", validators=[DataRequired()], format="%H:%M")
    ort = StringField("Ort", validators=[DataRequired(), Length(max=200)])
    beschreibung = TextAreaField("Beschreibung", validators=[Optional(), Length(max=5000)])
    submit = SubmitField("Sitzung anlegen")


class AdminForm(FlaskForm):
    username = StringField(
        "Benutzername", validators=[DataRequired(), Length(min=3, max=80)]
    )
    email = StringField(
        "E-Mail-Adresse", validators=[DataRequired(), Email(), Length(max=254)]
    )
    password = PasswordField(
        "Startpasswort", validators=[DataRequired(), Length(min=12, max=128)]
    )
    submit = SubmitField("Administrator anlegen")


class AdminEditForm(FlaskForm):
    username = StringField(
        "Benutzername", validators=[DataRequired(), Length(min=3, max=80)]
    )
    email = StringField(
        "E-Mail-Adresse", validators=[DataRequired(), Email(), Length(max=254)]
    )
    password = PasswordField(
        "Neues Passwort",
        validators=[Optional(), Length(min=12, max=128)],
    )
    submit = SubmitField("Änderungen speichern")


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


@admin_bp.route("/administratoren", methods=["GET", "POST"])
@login_required
def administrators():
    form = AdminForm()
    if form.validate_on_submit():
        username = form.username.data.strip()
        email = form.email.data.strip().lower()

        username_exists = Admin.query.filter(
            db.func.lower(Admin.username) == username.lower()
        ).first()
        email_exists = Admin.query.filter(
            db.func.lower(Admin.email) == email
        ).first()

        if username_exists:
            flash("Dieser Benutzername wird bereits verwendet.", "danger")
        elif email_exists:
            flash("Diese E-Mail-Adresse wird bereits verwendet.", "danger")
        else:
            admin = Admin(username=username, email=email, role="admin")
            admin.set_password(form.password.data)
            db.session.add(admin)
            db.session.commit()
            flash(f"Administrator „{username}“ wurde angelegt.", "success")
            return redirect(url_for("admin.administrators"))

    admins = Admin.query.order_by(Admin.username).all()
    return render_template("admins.html", form=form, admins=admins)


@admin_bp.route("/administratoren/<int:admin_id>/bearbeiten", methods=["GET", "POST"])
@login_required
def edit_administrator(admin_id):
    admin = db.get_or_404(Admin, admin_id)
    form = AdminEditForm(obj=admin)

    if form.validate_on_submit():
        username = form.username.data.strip()
        email = form.email.data.strip().lower()
        username_exists = Admin.query.filter(
            db.func.lower(Admin.username) == username.lower(),
            Admin.id != admin.id,
        ).first()
        email_exists = Admin.query.filter(
            db.func.lower(Admin.email) == email,
            Admin.id != admin.id,
        ).first()

        if username_exists:
            flash("Dieser Benutzername wird bereits verwendet.", "danger")
        elif email_exists:
            flash("Diese E-Mail-Adresse wird bereits verwendet.", "danger")
        else:
            admin.username = username
            admin.email = email
            if form.password.data:
                admin.set_password(form.password.data)
            db.session.commit()
            flash(f"Administrator „{username}“ wurde aktualisiert.", "success")
            return redirect(url_for("admin.administrators"))

    return render_template(
        "edit_admin.html",
        form=form,
        admin=admin,
        is_current_admin=admin.id == current_user.id,
    )


@admin_bp.post("/administratoren/<int:admin_id>/loeschen")
@login_required
def delete_administrator(admin_id):
    admin = db.get_or_404(Admin, admin_id)

    if Admin.query.count() <= 1:
        flash("Der letzte Administrator kann nicht gelöscht werden.", "warning")
    else:
        is_current_admin = admin.id == current_user.id
        username = admin.username
        db.session.delete(admin)
        if is_current_admin:
            logout_user()
        db.session.commit()
        flash(f"Administrator „{username}“ wurde gelöscht.", "success")
        if is_current_admin:
            return redirect(url_for("auth.login"))

    return redirect(url_for("admin.administrators"))


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
    duration = booking_form.dauer.data
    if duration not in BOOKING_DURATIONS:
        duration = 15
    available_slots = available_booking_slots(session, duration)
    booking_form.slot_id.choices = [
        SelectChoice(str(slot.id), slot.zeitpunkt.strftime("%H:%M"))
        for slot in available_slots
    ]
    return render_template(
        "session_detail.html",
        session=session,
        booking_form=booking_form,
        slot_options=booking_slot_options(session),
        extended_slot_ids={
            slot.id for slot in session.slots if is_extension_slot(slot)
        },
    )


@admin_bp.post("/sitzungen/<int:session_id>/buchungen")
@login_required
def create_booking(session_id):
    session = db.get_or_404(Session, session_id)
    form = BookingForm()
    duration = form.dauer.data
    if duration not in BOOKING_DURATIONS:
        duration = 15
    available_slots = available_booking_slots(session, duration)
    form.slot_id.choices = [
        SelectChoice(str(slot.id), slot.zeitpunkt.strftime("%H:%M"))
        for slot in available_slots
    ]
    if form.validate_on_submit():
        if not available_slots:
            flash("Für diese Dauer ist kein passender freier Termin verfügbar.", "warning")
        elif form.slot_id.data is None:
            flash("Bitte wählen Sie einen freien Termin aus.", "danger")
        elif save_booking(
            session,
            form.slot_id.data,
            form.name.data.strip(),
            form.email.data.strip().lower(),
            (form.telefon.data or "").strip(),
            duration,
        ):
            flash("Buchung gespeichert.", "success")
        else:
            flash("Dieses Zeitfenster ist nicht mehr frei.", "danger")
    else:
        flash("Bitte prüfen Sie die Buchungsangaben.", "danger")
    return redirect(url_for("admin.session_detail", session_id=session.id))


@admin_bp.post("/buchungen/<int:booking_id>/loeschen")
@login_required
def delete_booking(booking_id):
    booking = db.get_or_404(Booking, booking_id)
    session_id = booking.slot.session_id
    delete_booking_and_release_slots(booking)
    flash("Buchung gelöscht; die belegten Zeitfenster sind wieder frei.", "success")
    return redirect(url_for("admin.session_detail", session_id=session_id))


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
    if is_extension_slot(slot):
        flash("Dieser Slot gehört zu einer 30-Minuten-Buchung und kann nicht einzeln geändert werden.", "warning")
    elif slot.status == "belegt":
        flash("Belegte Zeitfenster können nicht reserviert werden.", "warning")
    else:
        slot.status = "reserviert" if slot.status == "frei" else "frei"
        db.session.commit()
        flash("Zeitfensterstatus aktualisiert.", "success")
    return redirect(url_for("admin.session_detail", session_id=slot.session_id))
