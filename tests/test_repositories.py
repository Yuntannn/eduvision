from datetime import timedelta

from sqlmodel import Session

from eduvision.db.models import Analysis, Upload, utcnow
from eduvision.db.repositories import AnalysisRepository, UploadRepository


def make_upload(session: Session) -> Upload:
    return UploadRepository(session).create(
        Upload(
            original_filename="notes.jpg",
            stored_filename="abc.jpg",
            content_type="image/jpeg",
            size_bytes=123,
        )
    )


def test_create_and_get_upload(session: Session) -> None:
    created = make_upload(session)

    fetched = UploadRepository(session).get(created.id)

    assert fetched is not None
    assert fetched.original_filename == "notes.jpg"
    assert fetched.size_bytes == 123


def test_get_missing_upload_returns_none(session: Session) -> None:
    assert UploadRepository(session).get("missing") is None


def test_create_analysis_applies_defaults(session: Session) -> None:
    upload = make_upload(session)

    analysis = AnalysisRepository(session).create(Analysis(upload_id=upload.id))

    assert analysis.status == "pending"
    assert analysis.input_tokens == 0
    assert analysis.output_tokens == 0
    assert analysis.duration_ms == 0
    assert analysis.failure_reason is None


def test_get_analysis(session: Session) -> None:
    upload = make_upload(session)
    repo = AnalysisRepository(session)
    created = repo.create(Analysis(upload_id=upload.id))

    assert repo.get(created.id) is not None
    assert repo.get("missing") is None


def test_update_analysis_persists_changes_and_bumps_updated_at(session: Session) -> None:
    upload = make_upload(session)
    repo = AnalysisRepository(session)
    analysis = repo.create(Analysis(upload_id=upload.id))
    first_updated_at = analysis.updated_at

    analysis.status = "completed"
    analysis.extracted_text = "Photosynthesis is..."
    analysis.input_tokens = 10
    repo.update(analysis)

    fetched = repo.get(analysis.id)
    assert fetched is not None
    assert fetched.status == "completed"
    assert fetched.extracted_text == "Photosynthesis is..."
    assert fetched.input_tokens == 10
    assert fetched.updated_at > first_updated_at


def test_list_is_newest_first_and_paginated(session: Session) -> None:
    upload = make_upload(session)
    repo = AnalysisRepository(session)
    now = utcnow()
    ids = [
        repo.create(Analysis(upload_id=upload.id, created_at=now + timedelta(seconds=i))).id
        for i in range(5)
    ]
    newest_first = list(reversed(ids))

    page1, total = repo.list(limit=2, offset=0)
    page2, _ = repo.list(limit=2, offset=2)
    page3, _ = repo.list(limit=2, offset=4)
    beyond, _ = repo.list(limit=2, offset=10)

    assert total == 5
    assert [a.id for a in page1] == newest_first[0:2]
    assert [a.id for a in page2] == newest_first[2:4]
    assert [a.id for a in page3] == newest_first[4:5]
    assert beyond == []


def test_list_empty(session: Session) -> None:
    assert AnalysisRepository(session).list() == ([], 0)
