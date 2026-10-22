import logging
import time

from langchain_core.language_models import BaseChatModel

from eduvision.db.models import Analysis
from eduvision.db.repositories import AnalysisRepository, UploadRepository
from eduvision.llm.errors import InvalidLLMOutputError, LLMUnavailableError
from eduvision.storage.local_storage import LocalStorage
from eduvision.workflow.errors import StepLimitExceededError
from eduvision.workflow.graph import run_workflow
from eduvision.workflow.progress import WorkflowProgress
from eduvision.workflow.state import AnalysisState

logger = logging.getLogger(__name__)

INTERNAL_ERROR = "internal_error"


class UploadNotFoundError(Exception):
    """No upload exists with the requested id."""


class AnalysisNotFoundError(Exception):
    """No analysis exists with the requested id."""


class AnalysisFailedError(Exception):
    """The analysis ran and failed; it has been saved as `failed` with `failure_reason`."""

    def __init__(self, analysis_id: str, failure_reason: str, message: str) -> None:
        super().__init__(message)
        self.analysis_id = analysis_id
        self.failure_reason = failure_reason
        self.message = message


_FAILURE_MESSAGES = {
    "no_text_found": "No meaningful text could be found in the image.",
    "invalid_llm_output": "The model returned invalid output, even after one retry.",
    "step_limit_exceeded": "The analysis workflow exceeded its step limit.",
    "llm_unavailable": "The LLM provider is unavailable or timed out.",
    INTERNAL_ERROR: "The analysis failed unexpectedly.",
}


class AnalysisService:
    def __init__(
        self,
        uploads: UploadRepository,
        analyses: AnalysisRepository,
        storage: LocalStorage,
        recursion_limit: int,
    ) -> None:
        self._uploads = uploads
        self._analyses = analyses
        self._storage = storage
        self._recursion_limit = recursion_limit

    def create_analysis(self, upload_id: str, model: BaseChatModel) -> Analysis:
        """Run the workflow on an upload and save the outcome.

        A failed run is saved as `failed` before AnalysisFailedError is raised.
        """
        upload = self._uploads.get(upload_id)
        if upload is None:
            raise UploadNotFoundError(f"Upload {upload_id} was not found.")

        analysis = self._analyses.create(Analysis(upload_id=upload.id))
        started = time.perf_counter()
        progress = WorkflowProgress()
        state: AnalysisState = {}
        failure_reason: str | None = None
        try:
            state = run_workflow(
                model,
                image_bytes=self._storage.read(upload.stored_filename),
                image_media_type=upload.content_type,
                recursion_limit=self._recursion_limit,
                analysis_id=analysis.id,
                progress=progress,
            )
            failure_reason = state.get("failure_reason")
        except StepLimitExceededError:
            failure_reason = "step_limit_exceeded"
        except InvalidLLMOutputError:
            failure_reason = "invalid_llm_output"
        except LLMUnavailableError:
            failure_reason = "llm_unavailable"
        except Exception:
            logger.exception("Analysis failed unexpectedly", extra={"analysis_id": analysis.id})
            failure_reason = INTERNAL_ERROR

        analysis.duration_ms = int((time.perf_counter() - started) * 1000)
        # The progress tracker survives a failed run, so partial work is saved either way.
        analysis.input_tokens = progress.input_tokens
        analysis.output_tokens = progress.output_tokens
        analysis.extracted_text = progress.extracted_text
        analysis.layout = progress.layout

        if failure_reason is None:
            analysis.status = "completed"
            analysis.classification_json = state["classification"].model_dump_json()
            analysis.explanation_json = state["explanation"].model_dump_json()
            return self._analyses.update(analysis)

        analysis.status = "failed"
        analysis.failure_reason = failure_reason
        self._analyses.update(analysis)
        raise AnalysisFailedError(analysis.id, failure_reason, _FAILURE_MESSAGES[failure_reason])

    def get_analysis(self, analysis_id: str) -> Analysis:
        analysis = self._analyses.get(analysis_id)
        if analysis is None:
            raise AnalysisNotFoundError(f"Analysis {analysis_id} was not found.")
        return analysis

    def list_analyses(self, limit: int, offset: int) -> tuple[list[Analysis], int]:
        return self._analyses.list(limit=limit, offset=offset)
