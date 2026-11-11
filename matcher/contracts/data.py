"""
Data contract - what the rest of the app needs from storage.

Records are dicts kept in named collections, e.g. the "resumes"
collection. JsonRepository will keep each collection in data/<name>.json,
and InMemoryRepository will keep them in a dict for the tests.

A subclass only has to load and save. Finding and filtering records work
the same for every kind of storage, so they are written once here.
"""

from abc import ABC, abstractmethod


class RecordRepository(ABC):
    """Abstract base for saving, loading and querying records."""

    @abstractmethod
    def load(self, collection):
        """Return every record in a collection, oldest first.

        Returns [] if the collection is missing, empty or unreadable -
        never raises because of bad stored data.
        """

    @abstractmethod
    def save(self, collection, record):
        """Add a record and return it with its new id, e.g. "R001"."""

    @abstractmethod
    def collection_names(self):
        """The names of every stored collection, e.g. ["job_matches", "resumes"]."""

    def find(self, collection, record_id):
        """Return the record with this id, or None."""
        if not record_id:
            return None
        matches = self.filter(collection, id=record_id)
        return matches[0] if matches else None

    def filter(self, collection, **fields):
        """Return the records whose fields all equal the given values.

        e.g. repository.filter("job_matches", resume_id="R001")
        """
        return [
            record for record in self.load(collection)
            if all(record.get(name) == value for name, value in fields.items())
        ]

    def newest(self, collection, **fields):
        """The most recently saved record with these field values, or None."""
        matches = self.filter(collection, **fields)
        return matches[-1] if matches else None

    def load_everything(self):
        """Every collection's records, e.g. {"resumes": [...], ...} (run at startup)."""
        return {name: self.load(name) for name in self.collection_names()}
