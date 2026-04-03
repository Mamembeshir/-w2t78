"""
config/logging_filters.py
Masks sensitive values in log records before they are written anywhere.
Patterns: Authorization headers, tokens, passwords, API keys, secrets.
"""
import logging
import re

# Patterns that match sensitive key=value pairs in log strings.
# Each tuple is (compiled_regex, replacement_string).
_MASK_PATTERNS = [
    # 1. Authorization: Bearer / Token <value>
    (re.compile(r"(Authorization:\s*(?:Bearer|Token)\s+)\S+", re.IGNORECASE), r"\1[REDACTED]"),
    # 2. JSON double-quoted values: "password": "value" — run before general pattern
    (re.compile(
        r'("(?:token|access_token|refresh_token|api_key|apikey|secret|password|passwd|credential)"\s*:\s*")[^"]*(")',
        re.IGNORECASE,
    ), r"\1[REDACTED]\2"),
    # 3. Query-string / env: token=<value> (stops at & whitespace quotes braces)
    (re.compile(
        r"((?:token|access_token|refresh_token|api_key|apikey|secret|password|passwd|credential|FIELD_ENCRYPTION_KEY)\s*[=:]\s*)[^\s,&\"\'}{]+",
        re.IGNORECASE,
    ), r"\1[REDACTED]"),
]


class MaskSecretsFilter(logging.Filter):
    """
    Logging filter that applies all _MASK_PATTERNS to every log message.
    Applied to the console handler so no secret ever reaches stdout/stderr.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = _mask(record.getMessage())
        record.args = ()  # already interpolated into msg above
        return True


def _mask(text: str) -> str:
    """Apply all masking patterns to a string."""
    if not isinstance(text, str):
        try:
            text = str(text)
        except Exception:
            return "[unformattable log message]"
    for pattern, replacement in _MASK_PATTERNS:
        text = pattern.sub(replacement, text)
    return text
