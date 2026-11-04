"""
Domain classes - the things the app works with, e.g. a Resume or a Candidate.

Each class keeps its fields private (self._name) and exposes them as
read-only properties, so a record can't be changed by accident after it
is made. to_dict() and from_dict() convert to and from the dicts saved in
data/*.json, in the same shape the app has always saved.
"""
