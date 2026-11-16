"""Administrator authentication routes."""

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from flask_wtf import FlaskForm
from wtforms import PasswordField, StringField, SubmitField
from wtforms.validators import DataRequired
from urllib.parse import urlsplit

from models import Admin

auth_bp = Blueprint("auth", __name__)


class LoginForm(FlaskForm):
    username = StringField("Benutzername", validators=[DataRequired()])
    password = PasswordField("Passwort", validators=[DataRequired()])
    submit = SubmitField("Anmelden")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("admin.dashboard"))
    form = LoginForm()
    if form.validate_on_submit():
        admin = Admin.query.filter_by(username=form.username.data.strip()).first()
        if admin and admin.check_password(form.password.data):
            login_user(admin)
            flash("Sie sind angemeldet.", "success")
            next_url = request.args.get("next", "")
            parsed_next = urlsplit(next_url)
            if next_url.startswith("/") and not next_url.startswith("//") and not parsed_next.netloc:
                return redirect(next_url)
            return redirect(url_for("admin.dashboard"))
        flash("Benutzername oder Passwort ist nicht korrekt.", "danger")
    return render_template("login.html", form=form)


@auth_bp.post("/logout")
@login_required
def logout():
    logout_user()
    flash("Sie wurden abgemeldet.", "info")
    return redirect(url_for("auth.login"))
