"""
Data Manager - saves, loads and queries records kept as JSON files in data/.

Each collection is one file holding a list of records, e.g. the "resumes"
collection is data/resumes.json. Missing, empty or broken files never crash
the app.

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
        # Every record must be a JSON object; anything else can't be queried
        kept = [record for record in records if isinstance(record, dict)]
        if len(kept) < len(records):
            logger.warning("Ignoring %s records in %s that are not objects", len(records) - len(kept), path)
        return kept

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

    def check_on_startup(self):
        """Load every collection and log how many records each has (run once at startup).

        Missing or broken files show up in the log straight away instead of
        on the first upload. Returns {"resumes": [...], ...}.
        """
        if not self.data_dir.exists():
            logger.info("No saved records yet (%s does not exist)", self.data_dir)
            return {}

        everything = self.load_everything()
        for name, records in everything.items():
            logger.info("Loaded %s %s", len(records), name)
        return everything

