"""Flask application factory and server-side slot generation."""

from datetime import datetime, timedelta
from pathlib import Path

from flask import Flask, jsonify
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import inspect, text

from config import Config
from models import Admin, db

login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message = "Bitte melden Sie sich an, um fortzufahren."
login_manager.login_message_category = "warning"
csrf = CSRFProtect()


def generate_slot_times(session_date, start_time, end_time):
    """Return slot start datetimes every 15 minutes, including the end time."""
    start = datetime.combine(session_date, start_time)
    end = datetime.combine(session_date, end_time)
    if end <= start:
        raise ValueError("Die Endzeit muss nach der Startzeit liegen.")
    if any(value.minute % 15 != 0 or value.second or value.microsecond for value in (start, end)):
        raise ValueError("Start- und Endzeit müssen auf einem Viertelstundenraster liegen.")
    result = []
    current = start
    while current <= end:
        result.append(current)
        current += timedelta(minutes=15)
    return result


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)
    if not app.config.get("SECRET_KEY"):
        raise RuntimeError(
            "SECRET_KEY ist nicht gesetzt. Legen Sie vor dem Start einen zufälligen "
            "SECRET_KEY als Umgebungsvariable fest."
        )

    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    @login_manager.user_loader
    def load_admin(admin_id):
        return db.session.get(Admin, int(admin_id))

    from auth.routes import auth_bp
    from admin_routes import admin_bp
    from public_routes import public_bp

    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(public_bp)

    @app.get("/")
    def index():
        from flask import render_template

        return render_template("home.html")

    @app.get("/health")
    def health():
        return jsonify(status="ok")

    with app.app_context():
        db.create_all()
        waiting_list_columns = {
            column["name"] for column in inspect(db.engine).get_columns("waiting_list")
        }
        if "dauer" not in waiting_list_columns:
            with db.engine.begin() as connection:
                connection.execute(
                    text(
                        "ALTER TABLE waiting_list "
                        "ADD COLUMN dauer INTEGER NOT NULL DEFAULT 15"
                    )
                )

    return app


if __name__ == "__main__":
    create_app().run(debug=False)
