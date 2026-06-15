from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.auth import get_current_user, hash_password
from app.csrf import validate_csrf
from app.database import get_db
from app.jinja import templates
from app.models import User

router = APIRouter(prefix="/admin")

ROLES = {
    "editor":   "Редактор",
    "approver": "Согласующий",
    "admin":    "Администратор",
}


def _require_admin(request: Request, db: Session):
    user = get_current_user(request, db)
    if not user:
        return None, RedirectResponse(url="/login", status_code=302)
    if user.role != "admin":
        return None, RedirectResponse(url="/dashboard", status_code=302)
    return user, None


# ─── Список пользователей ───────────────────────────────────────────────────

@router.get("/users", response_class=HTMLResponse)
def users_list(request: Request, db: Session = Depends(get_db)):
    user, redir = _require_admin(request, db)
    if redir:
        return redir
    users = db.query(User).order_by(User.id).all()
    flash = request.session.pop("flash", None)
    return templates.TemplateResponse(request, "admin_users.html", {
        "user": user, "users": users, "roles": ROLES, "flash": flash,
    })


# ─── Создание пользователя ──────────────────────────────────────────────────

@router.get("/users/new", response_class=HTMLResponse)
def user_new_page(request: Request, db: Session = Depends(get_db)):
    user, redir = _require_admin(request, db)
    if redir:
        return redir
    return templates.TemplateResponse(request, "admin_user_form.html", {
        "user": user, "roles": ROLES, "target": None, "error": None,
    })


@router.post("/users/new")
async def user_new_submit(
    request: Request,
    db: Session = Depends(get_db),
    name: str = Form(...),
    email: str = Form(...),
    role: str = Form(...),
    password: str = Form(...),
    csrf_token: str = Form(default=""),
):
    user, redir = _require_admin(request, db)
    if redir:
        return redir
    validate_csrf(request, csrf_token)

    if role not in ROLES:
        return templates.TemplateResponse(request, "admin_user_form.html", {
            "user": user, "roles": ROLES, "target": None,
            "error": "Недопустимая роль",
        })
    if len(password) < 6:
        return templates.TemplateResponse(request, "admin_user_form.html", {
            "user": user, "roles": ROLES, "target": None,
            "error": "Пароль должен быть не менее 6 символов",
        })
    if db.query(User).filter(User.email == email.lower()).first():
        return templates.TemplateResponse(request, "admin_user_form.html", {
            "user": user, "roles": ROLES, "target": None,
            "error": "Пользователь с таким email уже существует",
        })

    new_user = User(
        name=name.strip(),
        email=email.lower().strip(),
        password_hash=hash_password(password),
        role=role,
        active=True,
    )
    db.add(new_user)
    db.commit()
    request.session["flash"] = f"Пользователь {new_user.name} создан."
    return RedirectResponse(url="/admin/users", status_code=302)


# ─── Редактирование пользователя ────────────────────────────────────────────

@router.get("/users/{user_id}/edit", response_class=HTMLResponse)
def user_edit_page(user_id: int, request: Request, db: Session = Depends(get_db)):
    user, redir = _require_admin(request, db)
    if redir:
        return redir
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        return RedirectResponse(url="/admin/users", status_code=302)
    return templates.TemplateResponse(request, "admin_user_form.html", {
        "user": user, "roles": ROLES, "target": target, "error": None,
    })


@router.post("/users/{user_id}/edit")
async def user_edit_submit(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    name: str = Form(...),
    email: str = Form(...),
    role: str = Form(...),
    password: str = Form(""),
    csrf_token: str = Form(default=""),
):
    user, redir = _require_admin(request, db)
    if redir:
        return redir
    validate_csrf(request, csrf_token)

    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        return RedirectResponse(url="/admin/users", status_code=302)

    if role not in ROLES:
        return templates.TemplateResponse(request, "admin_user_form.html", {
            "user": user, "roles": ROLES, "target": target,
            "error": "Недопустимая роль",
        })
    # Защита: нельзя убрать роль admin у самого себя
    if target.id == user.id and role != "admin":
        return templates.TemplateResponse(request, "admin_user_form.html", {
            "user": user, "roles": ROLES, "target": target,
            "error": "Нельзя убрать роль администратора у самого себя",
        })

    existing = db.query(User).filter(User.email == email.lower(), User.id != user_id).first()
    if existing:
        return templates.TemplateResponse(request, "admin_user_form.html", {
            "user": user, "roles": ROLES, "target": target,
            "error": "Email уже занят другим пользователем",
        })

    target.name = name.strip()
    target.email = email.lower().strip()
    target.role = role

    if password:
        if len(password) < 6:
            return templates.TemplateResponse(request, "admin_user_form.html", {
                "user": user, "roles": ROLES, "target": target,
                "error": "Пароль должен быть не менее 6 символов",
            })
        target.password_hash = hash_password(password)

    db.commit()
    request.session["flash"] = f"Данные пользователя {target.name} обновлены."
    return RedirectResponse(url="/admin/users", status_code=302)


# ─── Деактивация / активация ────────────────────────────────────────────────

@router.post("/users/{user_id}/toggle")
async def user_toggle(user_id: int, request: Request, db: Session = Depends(get_db)):
    user, redir = _require_admin(request, db)
    if redir:
        return redir
    form = await request.form()
    validate_csrf(request, form.get("csrf_token", ""))
    if user_id == user.id:
        request.session["flash"] = "Нельзя деактивировать самого себя."
        return RedirectResponse(url="/admin/users", status_code=302)
    target = db.query(User).filter(User.id == user_id).first()
    if target:
        target.active = not target.active
        db.commit()
        state = "активирован" if target.active else "деактивирован"
        request.session["flash"] = f"Пользователь {target.name} {state}."
    return RedirectResponse(url="/admin/users", status_code=302)


# ─── Профиль: смена своего пароля ───────────────────────────────────────────

@router.get("/profile", response_class=HTMLResponse)
def profile_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    flash = request.session.pop("flash", None)
    return templates.TemplateResponse(request, "profile.html", {
        "user": user, "flash": flash, "error": None,
    })


@router.post("/profile")
async def profile_submit(
    request: Request,
    db: Session = Depends(get_db),
    password_old: str = Form(...),
    password_new: str = Form(...),
    password_new2: str = Form(...),
    csrf_token: str = Form(default=""),
):
    from app.auth import verify_password
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    validate_csrf(request, csrf_token)

    def err(msg):
        return templates.TemplateResponse(request, "profile.html", {
            "user": user, "flash": None, "error": msg,
        })

    if not verify_password(password_old, user.password_hash):
        return err("Текущий пароль неверен")
    if len(password_new) < 6:
        return err("Новый пароль должен быть не менее 6 символов")
    if password_new != password_new2:
        return err("Пароли не совпадают")

    user.password_hash = hash_password(password_new)
    db.commit()
    request.session["flash"] = "Пароль успешно изменён."
    return RedirectResponse(url="/admin/profile", status_code=302)
