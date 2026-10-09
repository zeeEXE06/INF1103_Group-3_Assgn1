"""
Django settings for the Resume & Job Matcher project.
"""

import os
from pathlib import Path

# Load settings from the .env file (keeps API keys out of the code)
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
                "matcher.context_processors.static_version",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# Only used by Django itself (sessions etc.). Our app data is saved as
# CSV/JSON files in data/ by the Data Manager (Sprint 2).
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# Keep sessions in a signed cookie so no database tables (migrations) are needed.
# The session only holds small values, e.g. which job match the visitor uploaded.
SESSION_ENGINE = "django.contrib.sessions.backends.signed_cookies"

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

# Data mode toggle - set DATA_MODE in .env
#   "debug" = results pages use the fixed sample data in dummy_data.py
#   "live"  = results pages use real saved data (Sprint 2 onwards)
DATA_MODE = os.environ.get("DATA_MODE", "debug")

# Folder where the Data Manager saves CSV/JSON files (Sprint 2)
DATA_DIR = BASE_DIR / "data"

# Upload limits, checked by the I/O Manager
MAX_UPLOAD_SIZE_MB = int(os.environ.get("MAX_UPLOAD_SIZE_MB", "10"))
ALLOWED_UPLOAD_EXTENSIONS = [".pdf"]

# Most Jobstreet jobs the AI job search returns for one resume
MAX_JOBS = int(os.environ.get("MAX_JOBS", "15"))

# AI Manager settings (Sprint 4)
AI_MODE = os.environ.get("AI_MODE", "mock")  # "mock" or "live"
# Free Gemini key from https://aistudio.google.com/apikey. GEMINI_API_KEY also works.
AI_API_KEY = os.environ.get("AI_API_KEY") or os.environ.get("GEMINI_API_KEY", "")
AI_MODEL = os.environ.get("AI_MODEL", "gemini-3.8-flash")
# Models to try, in order, if AI_MODEL is overloaded (503) or rate limited (429)
AI_FALLBACK_MODELS = [
    m.strip() for m in os.environ.get("AI_FALLBACK_MODELS", "gemini-3.5-flash").split(",") if m.strip()
]
