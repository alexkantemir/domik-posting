from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import distinct, func
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.jinja import templates
from app.models import ContentItem, GeneratedPost, Publication
from app.services.publishers.registry import get_active_publishers, get_all_publishers

router = APIRouter()


PLATFORM_NAMES = {
    "telegram_channel": ("✈️", "Telegram канал"),
    "telegram_group": ("👥", "Telegram группа"),
    "telegram_stories": ("🎬", "Telegram Stories"),
    "vk": ("🔵", "ВКонтакте"),
    "max": ("🟣", "MAX"),
    "ok": ("🟠", "Одноклассники"),
    "yandex_maps": ("📍", "Яндекс Карты"),
    "yandex_zen": ("📰", "Яндекс Дзен"),
    "instagram": ("📸", "Instagram"),
}


def _item_display_status(item: ContentItem) -> str:
    """pending | scheduled | published | rejected"""
    statuses = {p.status for p in item.generated_posts}
    if "draft" in statuses:
        return "pending"
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if any(
        p.status == "approved" and p.scheduled_at and p.scheduled_at > now
        for p in item.generated_posts
    ):
        return "scheduled"
    if "published" in statuses:
        return "published"
    if "approved" in statuses:
        return "scheduled"
    return "rejected"


@router.get("/posts/pending", response_class=HTMLResponse)
def posts_pending(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    query = (
        db.query(ContentItem)
        .join(ContentItem.generated_posts)
        .filter(GeneratedPost.status == "draft")
    )
    if user.role == "editor":
        query = query.filter(ContentItem.created_by == user.id)
    items = query.order_by(ContentItem.created_at.desc()).distinct().all()

    flash = request.session.pop("flash", None)

    return templates.TemplateResponse(
        request, "posts_list.html",
        {
            "user": user,
            "items": items,
            "platform_names": PLATFORM_NAMES,
            "page_title": "На согласовании",
            "page_type": "pending",
            "empty_text": "Нет материалов, ожидающих согласования",
            "flash": flash,
        },
    )


@router.get("/posts/scheduled", response_class=HTMLResponse)
def posts_scheduled(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    query = (
        db.query(ContentItem)
        .join(ContentItem.generated_posts)
        .filter(
            GeneratedPost.status == "approved",
            GeneratedPost.scheduled_at > now,
        )
    )
    if user.role == "editor":
        query = query.filter(ContentItem.created_by == user.id)
    items = query.order_by(ContentItem.created_at.desc()).distinct().all()

    return templates.TemplateResponse(
        request, "posts_list.html",
        {
            "user": user,
            "items": items,
            "platform_names": PLATFORM_NAMES,
            "page_title": "Запланировано",
            "page_type": "scheduled",
            "empty_text": "Нет запланированных публикаций",
        },
    )


@router.get("/posts/history", response_class=HTMLResponse)
def posts_history(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    query = (
        db.query(ContentItem)
        .join(ContentItem.generated_posts)
        .filter(GeneratedPost.status.in_(["published", "rejected"]))
    )
    items = query.order_by(ContentItem.created_at.desc()).distinct().limit(50).all()

    return templates.TemplateResponse(
        request, "posts_list.html",
        {
            "user": user,
            "items": items,
            "platform_names": PLATFORM_NAMES,
            "page_title": "История публикаций",
            "page_type": "history",
            "empty_text": "История публикаций пуста",
        },
    )


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    stats = {
        # Уникальные материалы (ContentItem), у которых есть хотя бы один пост в нужном статусе
        "pending": db.query(func.count(distinct(ContentItem.id)))
            .join(ContentItem.generated_posts)
            .filter(GeneratedPost.status == "draft")
            .scalar() or 0,
        "scheduled": db.query(func.count(distinct(ContentItem.id)))
            .join(ContentItem.generated_posts)
            .filter(GeneratedPost.status == "approved", GeneratedPost.scheduled_at > now)
            .scalar() or 0,
        "published_total": db.query(func.count(distinct(ContentItem.id)))
            .join(ContentItem.generated_posts)
            .filter(GeneratedPost.status == "published")
            .scalar() or 0,
        "content_total": db.query(ContentItem).count(),
    }

    recent = (
        db.query(ContentItem)
        .order_by(ContentItem.created_at.desc())
        .limit(10)
        .all()
    )

    item_statuses = {item.id: _item_display_status(item) for item in recent}

    active_publishers = get_active_publishers()
    all_publishers = get_all_publishers()

    return templates.TemplateResponse(
        request, "dashboard.html",
        {
            "user": user,
            "stats": stats,
            "recent": recent,
            "item_statuses": item_statuses,
            "active_publishers": active_publishers,
            "all_publishers": all_publishers,
        },
    )
