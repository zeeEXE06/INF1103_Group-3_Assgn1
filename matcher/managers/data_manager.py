"""
Data Manager - saves and loads records as JSON files in the data/ folder.

Each collection is one file holding a list of records, e.g.
load_records("resumes") reads data/resumes.json. Missing, empty or broken
files never crash the app.
"""

import json
import logging

from django.conf import settings

logger = logging.getLogger(__name__)


def get_path(collection):
    return settings.DATA_DIR / f"{collection}.json"


def load_records(collection):
    """Return the list of records in a collection ([] if missing, empty or broken)."""
    path = get_path(collection)
    if not path.exists():
        return []

    try:
        records = json.loads(path.read_text(encoding="utf-8") or "[]")
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Could not read %s: %s", path, exc)
        return []

    if not isinstance(records, list):
        logger.warning("%s does not contain a list, ignoring it", path)
        return []
    return records


def save_record(collection, record):
    """Add a record to a collection and return it with its new id, e.g. "R001"."""
    path = get_path(collection)
    path.parent.mkdir(parents=True, exist_ok=True)

    records = load_records(collection)
    if not records and path.exists() and path.stat().st_size > 0:
        # The file is unreadable - keep a copy instead of overwriting it
        backup = path.with_suffix(".broken.json")
        path.replace(backup)
        logger.warning("Moved unreadable %s to %s", path, backup)

    record = {"id": f"{collection[0].upper()}{len(records) + 1:03d}", **record}
    records.append(record)

    # Write to a temp file first so a crash mid-write cannot corrupt the data
    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(records, indent=2), encoding="utf-8")
    tmp_path.replace(path)
    return record
