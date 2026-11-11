"""
Tests for the Data Manager's repositories. run_tests.py gives each test
its own empty DATA_DIR, so the real data/ folder is never touched.
"""

import json

from django.conf import settings

from ..managers.data_manager import JsonRepository
from .fakes import InMemoryRepository


def data_file(name):
    return settings.DATA_DIR / name


# ---------- JsonRepository: loading ----------

def test_missing_file_loads_as_empty():
    assert JsonRepository().load("resumes") == []


def test_empty_file_loads_as_empty():
    data_file("resumes.json").write_text("")
    assert JsonRepository().load("resumes") == []


def test_broken_file_loads_as_empty_instead_of_crashing():
    data_file("resumes.json").write_text("{not json")
    assert JsonRepository().load("resumes") == []


def test_file_without_a_list_is_ignored():
    data_file("resumes.json").write_text('{"id": "R001"}')
    assert JsonRepository().load("resumes") == []


# ---------- JsonRepository: saving ----------

def test_save_gives_each_record_the_next_id():
    repository = JsonRepository()
    first = repository.save("resumes", {"filename": "a.pdf"})
    second = repository.save("resumes", {"filename": "b.pdf"})
    assert (first["id"], second["id"]) == ("R001", "R002")
    assert repository.load("resumes") == [first, second]


def test_saved_records_are_plain_json_on_disk():
    JsonRepository().save("job_matches", {"resume_id": "R001"})
    assert json.loads(data_file("job_matches.json").read_text()) == [{"id": "J001", "resume_id": "R001"}]


def test_save_keeps_a_broken_file_as_a_backup():
    data_file("resumes.json").write_text("{not json")
    repository = JsonRepository()
    repository.save("resumes", {"filename": "a.pdf"})
    assert len(repository.load("resumes")) == 1
    assert data_file("resumes.broken.json").read_text() == "{not json"


def test_save_leaves_no_temp_file_behind():
    JsonRepository().save("resumes", {"filename": "a.pdf"})
    assert not data_file("resumes.tmp").exists()


def test_save_creates_the_data_folder():
    folder = settings.DATA_DIR / "new" / "folder"
    JsonRepository(folder).save("resumes", {"filename": "a.pdf"})
    assert (folder / "resumes.json").exists()


# ---------- JsonRepository: collections and queries ----------

def test_collection_names_skip_broken_backups():
    repository = JsonRepository()
    assert repository.collection_names() == []
    repository.save("resumes", {"filename": "a.pdf"})
    repository.save("job_matches", {"resume_id": "R001"})
    data_file("old.broken.json").write_text("{not json")
    assert repository.collection_names() == ["job_matches", "resumes"]


def test_missing_data_folder_has_no_collections():
    assert JsonRepository(settings.DATA_DIR / "missing").collection_names() == []


def test_queries_from_the_base_class_work_on_json_files():
    repository = JsonRepository()
    repository.save("job_matches", {"resume_id": "R001"})
    repository.save("job_matches", {"resume_id": "R002"})
    newest = repository.save("job_matches", {"resume_id": "R001"})
    assert repository.find("job_matches", "J002")["resume_id"] == "R002"
    assert [r["id"] for r in repository.filter("job_matches", resume_id="R001")] == ["J001", "J003"]
    assert repository.newest("job_matches", resume_id="R001") == newest
    assert sorted(repository.load_everything()) == ["job_matches"]


def test_two_repositories_on_different_folders_stay_separate():
    a, b = JsonRepository(settings.DATA_DIR / "a"), JsonRepository(settings.DATA_DIR / "b")
    a.save("resumes", {"filename": "a.pdf"})
    assert b.load("resumes") == []


# ---------- Every repository keeps the RecordRepository contract ----------

def check_keeps_the_contract(repository):
    """What every RecordRepository must do, whatever it stores records in."""
    assert repository.load("resumes") == []
    assert repository.collection_names() == []

    first = repository.save("resumes", {"filename": "a.pdf", "file_hash": "x"})
    repository.save("resumes", {"filename": "b.pdf", "file_hash": "y"})
    assert first == {"id": "R001", "filename": "a.pdf", "file_hash": "x"}
    assert [r["id"] for r in repository.load("resumes")] == ["R001", "R002"]

    repository.load("resumes")[0]["filename"] = "changed.pdf"
    assert repository.find("resumes", "R001")["filename"] == "a.pdf"

    assert repository.filter("resumes", file_hash="y")[0]["filename"] == "b.pdf"
    assert repository.newest("resumes")["id"] == "R002"
    assert repository.find("resumes", "R999") is None
    assert repository.collection_names() == ["resumes"]


def test_json_and_in_memory_repositories_can_replace_each_other():
    check_keeps_the_contract(JsonRepository())
    check_keeps_the_contract(InMemoryRepository())


def test_in_memory_repository_never_touches_the_data_folder():
    InMemoryRepository().save("resumes", {"filename": "a.pdf"})
    assert not data_file("resumes.json").exists()
