"""
Django settings for the Resume & Job Matcher project.

Sprint 1 (UI): only the pieces needed to render pages are wired up.
No database models, no AI Manager, no Data Manager persistence yet —
those arrive in later sprints. Settings for them (env vars, upload
limits) are stubbed in now so later sprints don't have to touch this
file much.
"""

import os
from pathlib import Path

# Load variables from a .env file if python-dotenv is installed and a
# .env file exists. This keeps secrets (AI API keys, later on) out of
# source control. Safe to skip silently in environments without it.
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

BASE_DIR = Path(__file__).resolve().parent.parent

# --- Core security settings -------------------------------------------------

SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "dev-only-insecure-secret-key-change-me",
)

DEBUG = os.environ.get("DJANGO_DEBUG", "True") == "True"

ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost").split(",")

# --- Applications ------------------------------------------------------------

INSTALLED_APPS = [
    "django.contrib.staticfiles",
    "django.contrib.sessions",
    "django.contrib.messages",
    "matcher",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# No database is configured yet on purpose: Sprint 1 (UI) runs entirely
# on in-memory dummy data (see matcher/dummy_data.py). Sprint 2 adds the
# Data Manager, reading/writing CSV or JSON files under DATA_DIR below.
# Django still needs *a* database configured to boot management commands
# such as `runserver`, so a local SQLite file is used only for Django's
# own internal tables (sessions, etc.) — application data does not live here.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Singapore"
USE_I18N = True
USE_TZ = True

# --- Static & media files ----------------------------------------------------

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "matcher" / "static"]

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"
UPLOAD_DIR = MEDIA_ROOT / "uploads"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Application-specific settings ------------------------------------------

# Where the Data Manager will read/write CSV or JSON (Sprint 2).
DATA_DIR = BASE_DIR / "data"

# Upload validation limits (enforced by forms in later sprints; the
# limits live here so they're configured in one place, not scattered
# through views).
MAX_UPLOAD_SIZE_MB = int(os.environ.get("MAX_UPLOAD_SIZE_MB", "10"))
ALLOWED_UPLOAD_EXTENSIONS = [".pdf"]

# AI Manager configuration (Sprint 4). Left as env-driven stubs now so
# no code changes are needed later beyond the AI Manager itself.
AI_MODE = os.environ.get("AI_MODE", "mock")  # "mock" or "live"
AI_API_KEY = os.environ.get("AI_API_KEY", "")
