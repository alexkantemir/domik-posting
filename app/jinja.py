from datetime import datetime, timedelta

from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="app/templates")


def _moscow(dt: datetime | None) -> str:
    """Convert UTC datetime to Moscow time (UTC+3) and format for display."""
    if not dt:
        return "—"
    return (dt + timedelta(hours=3)).strftime("%d.%m.%Y %H:%M")


templates.env.filters["moscow"] = _moscow
