import secrets

from fastapi import HTTPException, Request


def get_csrf_token(request: Request) -> str:
    if "csrf_token" not in request.session:
        request.session["csrf_token"] = secrets.token_hex(32)
    return request.session["csrf_token"]


def validate_csrf(request: Request, token: str) -> None:
    session_token = request.session.get("csrf_token", "")
    if not session_token or not token or not secrets.compare_digest(session_token, token):
        raise HTTPException(status_code=403, detail="Недействительный CSRF-токен. Обновите страницу.")
