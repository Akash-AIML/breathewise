"""Central secret redaction for logs and user-visible error details.

The application never needs to print an API key. Provider libraries can still
put credentials into exception messages or tracebacks, so redaction is applied
at the logging-handler boundary as a last line of defence.
"""

import logging
import re
import traceback

from app.core.config import settings

REDACTED = "[REDACTED]"

# Query strings used by providers (data.gov.in requires `api-key` in the URL).
_QUERY_SECRET = re.compile(
    r"(?i)([?&](?:api[-_]?key|apikey|key|token|access_token|auth_token)=)([^&\s]+)"
)
# Header-style secrets, including the Google Generative AI header name.
_HEADER_SECRET = re.compile(
    r"(?i)\b(x-goog-api-key|x-api-key|api[-_]?key|authorization|proxy-authorization)\s*[:=]\s*([^\s,;]+)"
)
_BEARER = re.compile(r"(?i)\b(bearer\s+)[A-Za-z0-9._~+/=-]+")
_REDIS_CREDENTIALS = re.compile(r"(?i)(redis://)([^:/\s]+):([^@\s]+)@")


def _configured_secrets() -> list[str]:
    """Secrets currently present in settings, read lazily so tests can patch them."""
    candidates = [
        settings.DATA_GOV_IN_API_KEY,
        settings.OPENAQ_API_KEY,
        settings.GROQ_API_KEY,
        settings.GEMINI_API_KEY,
        settings.REDIS_URL,
    ]
    return [value for value in candidates if isinstance(value, str) and len(value) >= 4]


def redact_text(value: object) -> str:
    """Return ``value`` as text with known secrets and credential patterns removed."""
    text = str(value)

    # Exact configured values first: this catches any format we have not named.
    for secret in _configured_secrets():
        text = text.replace(secret, REDACTED)

    text = _QUERY_SECRET.sub(lambda match: match.group(1) + REDACTED, text)
    text = _HEADER_SECRET.sub(lambda match: match.group(1) + ": " + REDACTED, text)
    text = _BEARER.sub(lambda match: match.group(1) + REDACTED, text)
    text = _REDIS_CREDENTIALS.sub(
        lambda match: match.group(1) + REDACTED + ":" + REDACTED + "@", text
    )
    return text


class SecretRedactionFilter(logging.Filter):
    """Logging filter that sanitises messages, arguments and tracebacks."""

    def filter(self, record: logging.LogRecord) -> bool:
        # Resolve the final message first. Redacting ``msg`` and ``args``
        # independently breaks %-formatting (e.g. an argument that is a number
        # becomes a string) and can duplicate matcher output.
        record.msg = redact_text(record.getMessage())
        record.args = ()

        if record.exc_info:
            record.exc_text = redact_text("".join(traceback.format_exception(*record.exc_info)))
            record.exc_info = None
        elif record.exc_text:
            record.exc_text = redact_text(record.exc_text)
        if record.stack_info:
            record.stack_info = redact_text(record.stack_info)

        return True


def install_secret_redaction() -> None:
    """Attach the filter once to every handler that can emit application logs."""
    redactor = SecretRedactionFilter()
    loggers = (
        logging.getLogger(),
        logging.getLogger("uvicorn"),
        logging.getLogger("uvicorn.error"),
        logging.getLogger("uvicorn.access"),
        logging.getLogger("httpx"),
        logging.getLogger("httpcore"),
        logging.getLogger("breathewise"),
    )
    for target in loggers:
        for handler in target.handlers:
            if not any(isinstance(item, SecretRedactionFilter) for item in handler.filters):
                handler.addFilter(redactor)
