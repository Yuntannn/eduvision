import anthropic


class LLMError(Exception):
    """Base class for LLM layer errors.

    `input_tokens` / `output_tokens` are what the failed call(s) still consumed, so callers can
    account for the spend.
    """

    def __init__(self, message: str, *, input_tokens: int = 0, output_tokens: int = 0) -> None:
        super().__init__(message)
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens


class InvalidLLMOutputError(LLMError):
    """The model's output did not match the expected schema, even after one retry."""


class LLMUnavailableError(LLMError):
    """The LLM provider timed out, could not be reached, or is overloaded."""


# Provider exceptions that mean "try again later" rather than "our request is wrong".
UNAVAILABLE_EXCEPTIONS: tuple[type[Exception], ...] = (
    anthropic.APIConnectionError,  # includes APITimeoutError
    anthropic.InternalServerError,
    anthropic.RateLimitError,
    TimeoutError,
    ConnectionError,
)
