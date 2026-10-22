from sqlalchemy import func
from sqlmodel import Session, col, select

from eduvision.db.models import Analysis, Upload, utcnow


class UploadRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, upload: Upload) -> Upload:
        self._session.add(upload)
        self._session.commit()
        self._session.refresh(upload)
        return upload

    def get(self, upload_id: str) -> Upload | None:
        return self._session.get(Upload, upload_id)


class AnalysisRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, analysis: Analysis) -> Analysis:
        self._session.add(analysis)
        self._session.commit()
        self._session.refresh(analysis)
        return analysis

    def update(self, analysis: Analysis) -> Analysis:
        analysis.updated_at = utcnow()
        self._session.add(analysis)
        self._session.commit()
        self._session.refresh(analysis)
        return analysis

    def get(self, analysis_id: str) -> Analysis | None:
        return self._session.get(Analysis, analysis_id)

    def list(self, limit: int = 20, offset: int = 0) -> tuple[list[Analysis], int]:
        """Return one page of analyses (newest first) and the total count."""
        total = self._session.exec(select(func.count()).select_from(Analysis)).one()
        items = self._session.exec(
            select(Analysis)
            .order_by(col(Analysis.created_at).desc(), col(Analysis.id))
            .limit(limit)
            .offset(offset)
        ).all()
        return list(items), total
