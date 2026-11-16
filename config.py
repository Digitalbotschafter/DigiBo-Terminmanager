"""Application configuration for DigiBo Sprechstunde."""

import os
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = PROJECT_DIR / "instance"


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
            "DATABASE_URL", f"sqlite:///{(INSTANCE_DIR / 'digibo.db').as_posix()}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "0").lower() in {
        "1",
        "true",
        "yes",
    }
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SECURE = SESSION_COOKIE_SECURE
    WTF_CSRF_TIME_LIMIT = 3600
