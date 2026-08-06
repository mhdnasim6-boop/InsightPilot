"""Tests for in-memory repositories."""

from backend.models.file_metadata import FileMetadata
from backend.models.session import Session
from backend.repositories.file_repository import InMemoryFileRepository
from backend.repositories.session_repository import InMemorySessionRepository
from backend.utils.time import utc_now


def test_session_repository_crud() -> None:
    repo = InMemorySessionRepository()
    now = utc_now()
    session = Session(session_id="s1", created_at=now, last_activity=now)

    repo.add(session)
    assert repo.get("s1") == session
    assert repo.list() == [session]

    session.uploaded_files.append("f1")
    repo.update(session)
    assert repo.get("s1").uploaded_files == ["f1"]

    assert repo.delete("s1") is True
    assert repo.get("s1") is None


def test_file_repository_list_by_session() -> None:
    repo = InMemoryFileRepository()
    now = utc_now()
    file_a = FileMetadata(
        file_id="f1",
        session_id="s1",
        original_filename="a.csv",
        stored_filename="f1_a.csv",
        storage_path="/data/uploads/s1/f1_a.csv",
        uploaded_at=now,
    )
    file_b = FileMetadata(
        file_id="f2",
        session_id="s2",
        original_filename="b.csv",
        stored_filename="f2_b.csv",
        storage_path="/data/uploads/s2/f2_b.csv",
        uploaded_at=now,
    )
    repo.add(file_a)
    repo.add(file_b)

    assert repo.list_by_session("s1") == [file_a]
    assert len(repo.list()) == 2
