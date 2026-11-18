from app.core.config import get_settings
from app.core.exceptions import ContentRejectedError


def ensure_content_allowed(content: str) -> None:
    normalized = content.casefold()
    if any(term.casefold() in normalized for term in get_settings().blocked_terms):
        raise ContentRejectedError()
