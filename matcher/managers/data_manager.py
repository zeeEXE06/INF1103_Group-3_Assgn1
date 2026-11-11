"""
Data Manager - saves, loads and queries records kept as JSON files in data/.

Each collection is one file holding a list of records, e.g.
load_records("resumes") reads data/resumes.json. Missing, empty or broken
files never crash the app.

    JsonRepository  a RecordRepository (contracts/data.py) that keeps each
                    collection in its own JSON file
"""

import json
import logging
from pathlib import Path

from django.conf import settings

from ..contracts.data import RecordRepository

logger = logging.getLogger(__name__)


class JsonRepository(RecordRepository):
    """Keeps each collection as a list of records in <data_dir>/<collection>.json.

    Only load(), save() and collection_names() are written here; find(),
    filter(), newest() and load_everything() come from RecordRepository.
    """

    def __init__(self, data_dir=None):
        """data_dir: the folder for the JSON files. Defaults to DATA_DIR in settings."""
        self._data_dir = None if data_dir is None else Path(data_dir)

    @property
    def data_dir(self):
        # Read DATA_DIR each time, so a changed setting (e.g. in the tests) is used
        return settings.DATA_DIR if self._data_dir is None else self._data_dir

    def _path(self, collection):
        return self.data_dir / f"{collection}.json"

    def load(self, collection):
        """Return the list of records in a collection ([] if missing, empty or broken)."""
        path = self._path(collection)
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

    def save(self, collection, record):
        """Add a record to a collection and return it with its new id, e.g. "R001"."""
        path = self._path(collection)
        path.parent.mkdir(parents=True, exist_ok=True)

        records = self.load(collection)
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

    def collection_names(self):
        """Every collection with a file in data_dir, skipping .broken.json backups."""
        if not self.data_dir.exists():
            return []
        return sorted(
            path.stem for path in self.data_dir.glob("*.json")
            if not path.name.endswith(".broken.json")
        )



# ---------- Used by the views and matching service until they become classes (P3) ----------

def load_records(collection):
    """Return the list of records in a collection ([] if missing, empty or broken)."""
    return JsonRepository().load(collection)


def save_record(collection, record):
    """Add a record to a collection and return it with its new id, e.g. "R001"."""
    return JsonRepository().save(collection, record)


def find_record(collection, record_id):
    """Return the record with this id, or None."""
    return JsonRepository().find(collection, record_id)


def filter_records(collection, **fields):
    """Return the records whose fields all equal the given values.

    e.g. filter_records("job_matches", resume_id="R001")
    """
    return JsonRepository().filter(collection, **fields)


def load_all_records():
    """Load every collection in data/ (run once at startup).

    Returns {"resumes": [...], "job_matches": [...], ...} and logs how many
    records each has, so missing or broken files show up straight away.
    """
    repository = JsonRepository()
    if not repository.data_dir.exists():
        logger.info("No saved records yet (%s does not exist)", repository.data_dir)
        return {}

    all_records = repository.load_everything()
    for name, records in all_records.items():
        logger.info("Loaded %s %s", len(records), name)
    return all_records
