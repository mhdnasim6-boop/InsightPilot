"""Tests for the service layer."""

import pytest

from backend.core.exceptions import NotFoundError, ValidationError
from backend.repositories.file_repository import InMemoryFileRepository
from backend.repositories.session_repository import InMemorySessionRepository
from backend.services.file_service import FileService
from backend.services.session_service import SessionService


def test_create_and_get_session() -> None:
    service = SessionService(InMemorySessionRepository())
    session = service.create_session()

    fetched = service.get_session(session.session_id)
    assert fetched.session_id == session.session_id
    assert fetched.uploaded_files == []


def test_get_missing_session_raises_not_found() -> None:
    service = SessionService(InMemorySessionRepository())
    with pytest.raises(NotFoundError):
        service.get_session("missing")


def test_touch_session_updates_last_activity() -> None:
    service = SessionService(InMemorySessionRepository())
    session = service.create_session()

    touched = service.touch_session(session.session_id)
    assert touched.last_activity >= session.created_at


def test_register_file_attaches_to_session() -> None:
    session_service = SessionService(InMemorySessionRepository())
    file_service = FileService(InMemoryFileRepository(), session_service)
    session = session_service.create_session()

    metadata = file_service.register_file(session.session_id, "report.csv", "text/csv", 1024)

    assert metadata.session_id == session.session_id
    assert session_service.get_session(session.session_id).uploaded_files == [metadata.file_id]
    assert file_service.list_session_files(session.session_id) == [metadata]


def test_register_file_rejects_unsupported_type() -> None:
    session_service = SessionService(InMemorySessionRepository())
    file_service = FileService(InMemoryFileRepository(), session_service)
    session = session_service.create_session()

    with pytest.raises(ValidationError):
        file_service.register_file(session.session_id, "malware.exe")


def test_register_file_requires_existing_session() -> None:
    file_service = FileService(InMemoryFileRepository(), SessionService(InMemorySessionRepository()))

    with pytest.raises(NotFoundError):
        file_service.register_file("missing-session", "report.csv")
