import anthropic


class LLMError(Exception):
    """Base class for LLM layer errors."""


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
