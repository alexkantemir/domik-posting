import asyncio

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.auth import get_current_user, verify_password
from app.csrf import validate_csrf
from app.database import get_db
from app.jinja import templates
from app.models import User

router = APIRouter()


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    user = get_current_user(request, next(get_db()))
    if user:
        return RedirectResponse(url="/dashboard", status_code=302)
    return templates.TemplateResponse(request, "login.html", {"error": None, "email": ""})


@router.post("/login")
async def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    csrf_token: str = Form(default=""),
    db: Session = Depends(get_db),
):
    validate_csrf(request, csrf_token)
    user = db.query(User).filter(User.email == email.strip().lower(), User.active == True).first()
    if not user or not verify_password(password, user.password_hash):
        await asyncio.sleep(0.5)
        return templates.TemplateResponse(
            request, "login.html",
            {"error": "Неверный email или пароль", "email": email},
            status_code=401,
        )
    request.session["user_id"] = user.id
    return RedirectResponse(url="/dashboard", status_code=302)


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=302)
