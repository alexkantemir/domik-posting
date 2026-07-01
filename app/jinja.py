import secrets
from datetime import datetime, timedelta
from urllib.parse import urlparse

from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="app/templates")


def _moscow(dt: datetime | None) -> str:
    if not dt:
        return "—"
    return (dt + timedelta(hours=3)).strftime("%d.%m.%Y %H:%M")


templates.env.filters["moscow"] = _moscow


def _safe_url(url: str) -> str:
    """Allow only http/https URLs in href attributes."""
    try:
        if url and urlparse(url).scheme in ("http", "https"):
            return url
    except Exception:
        pass
    return "#"


templates.env.filters["safe_url"] = _safe_url

_orig_response = templates.TemplateResponse


def _csrf_response(request, name, context=None, **kwargs):
    context = context or {}
    if hasattr(request, "session"):
        if "csrf_token" not in request.session:
            request.session["csrf_token"] = secrets.token_hex(32)
        context.setdefault("csrf_token", request.session["csrf_token"])
    return _orig_response(request, name, context, **kwargs)


templates.TemplateResponse = _csrf_response
