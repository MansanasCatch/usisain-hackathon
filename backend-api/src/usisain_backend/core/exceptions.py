class UsisAInError(Exception):
    """Base exception for all UsisAIn backend errors."""


class ExtractionError(UsisAInError):
    """Raised when content extraction fails (bad file, unreachable URL, etc)."""


class PipelineError(UsisAInError):
    """Raised when a pipeline step fails in a way that should stop the run."""
