from dataclasses import dataclass


@dataclass
class WorkflowProgress:
    """What a run has produced so far; the caller keeps it to recover work after a failure."""

    input_tokens: int = 0
    output_tokens: int = 0
    raw_text: str | None = None
    layout: str | None = None
    cleaned_text: str | None = None

    def add_tokens(self, input_tokens: int, output_tokens: int) -> None:
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens

    @property
    def extracted_text(self) -> str | None:
        """The cleaned text, or the raw text if the run stopped before cleaning finished."""
        return self.cleaned_text or self.raw_text
