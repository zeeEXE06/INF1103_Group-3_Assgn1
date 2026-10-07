"""
Extra values available in every template.
"""

from django.conf import settings


def static_version(request):
    """Version number for the CSS/JS links, e.g. style.css?v=1759373202.

    It changes whenever style.css or main.js is edited, so browsers load
    the new file instead of an old cached copy.
    """
    static_dir = settings.BASE_DIR / "matcher" / "static"
    files = [static_dir / "css" / "style.css", static_dir / "js" / "main.js"]
    latest_edit = max((f.stat().st_mtime for f in files if f.exists()), default=0)
    return {"static_version": int(latest_edit)}
