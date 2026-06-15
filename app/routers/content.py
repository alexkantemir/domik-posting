import json
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import filetype
from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.jinja import templates
from app.models import ContentItem, GeneratedPost, Publication
from app.services.content_processor import NormalizedContent, process_url
from app.services.post_generator import generate_posts
from app.services.publishers.registry import get_publisher

logger = logging.getLogger(__name__)

router = APIRouter()
UPLOAD_DIR = "uploads"

MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50 MB
ALLOWED_MIME_TYPES = {
    "image/jpeg", "image/png", "image/gif", "image/webp",
    "video/mp4", "video/quicktime",
    "audio/mpeg", "audio/ogg", "audio/wav",
    "application/pdf",
}
MIME_TO_EXT = {
    "image/jpeg": ".jpg", "image/png": ".png",
    "image/gif": ".gif", "image/webp": ".webp",
    "video/mp4": ".mp4", "video/quicktime": ".mov",
    "audio/mpeg": ".mp3", "audio/ogg": ".ogg", "audio/wav": ".wav",
    "application/pdf": ".pdf",
}


def _save_upload(file: UploadFile) -> str:
    content = file.file.read()
    if len(content) > MAX_UPLOAD_SIZE:
        raise ValueError("Файл слишком большой (максимум 50 МБ)")

    kind = filetype.guess(content)
    mime = kind.mime if kind else None
    if mime not in ALLOWED_MIME_TYPES:
        raise ValueError(f"Недопустимый тип файла. Разрешены: фото, видео, аудио, PDF")

    ext = MIME_TO_EXT.get(mime, ".bin")
    filename = f"{uuid.uuid4()}{ext}"
    safe_path = os.path.realpath(os.path.join(UPLOAD_DIR, filename))
    if not safe_path.startswith(os.path.realpath(UPLOAD_DIR)):
        raise ValueError("Недопустимый путь файла")

    with open(safe_path, "wb") as f:
        f.write(content)
    return safe_path


@router.get("/uploads/{filename}")
def serve_upload(filename: str, request: Request, db: Session = Depends(get_db)):
    """Защищённая раздача загруженных файлов — только для авторизованных."""
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    safe_path = os.path.realpath(os.path.join(UPLOAD_DIR, filename))
    if not safe_path.startswith(os.path.realpath(UPLOAD_DIR)) or not os.path.exists(safe_path):
        return HTMLResponse("Файл не найден", status_code=404)
    return FileResponse(safe_path)


@router.get("/content/new", response_class=HTMLResponse)
def content_new_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    return templates.TemplateResponse(request, "content_new.html", {"user": user, "error": None})


@router.post("/content/new")
def content_new_submit(
    request: Request,
    content_type: str = Form(...),
    text: Optional[str] = Form(None),
    caption: Optional[str] = Form(None),
    url: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    # Сохраняем файл если есть
    file_paths = []
    if file and file.filename:
        try:
            filepath = _save_upload(file)
            file_paths.append(filepath)
        except ValueError as e:
            return templates.TemplateResponse(
                request, "content_new.html",
                {"user": user, "error": str(e)},
            )

    # Нормализуем контент
    try:
        if content_type == "url" and url:
            normalized = process_url(url.strip())
        else:
            if content_type == "photo_text":
                combined_text = caption.strip() if caption else ""
            else:
                combined_text = text.strip() if text else ""
            if file_paths and not combined_text:
                combined_text = f"[Загружен файл]"
            normalized = NormalizedContent(
                text=combined_text,
                images=file_paths,
                content_type=content_type,
            )
    except ValueError as e:
        return templates.TemplateResponse(
            request, "content_new.html",
            {"user": user, "error": str(e)},
        )
    except Exception as e:
        logger.error("Content processing error: %s", e, exc_info=True)
        return templates.TemplateResponse(
            request, "content_new.html",
            {"user": user, "error": "Ошибка обработки материала. Попробуйте снова."},
        )

    if not normalized.text and not normalized.images:
        return templates.TemplateResponse(
            request, "content_new.html",
            {"user": user, "error": "Добавьте текст, ссылку или файл"},
        )

    # Сохраняем ContentItem
    item = ContentItem(
        type=content_type,
        raw_text=normalized.text[:3000] if normalized.text else None,
        file_paths=json.dumps(file_paths, ensure_ascii=False),
        source_url=url if content_type == "url" else None,
        created_by=user.id,
    )
    db.add(item)
    db.commit()
    db.refresh(item)

    # Генерируем посты через GigaChat
    try:
        generated = generate_posts(normalized)
    except Exception as e:
        db.delete(item)
        db.commit()
        return templates.TemplateResponse(
            request, "content_new.html",
            {"user": user, "error": f"Ошибка GigaChat: {e}"},
        )

    # Сохраняем черновики
    for platform, result in generated.items():
        post = GeneratedPost(
            content_item_id=item.id,
            platform=platform,
            text=result["text"],
            status="draft" if result["ok"] else "failed",
        )
        db.add(post)
    db.commit()

    return RedirectResponse(url=f"/content/{item.id}/preview", status_code=302)


@router.get("/content/{item_id}/preview", response_class=HTMLResponse)
def content_preview(request: Request, item_id: int, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    item = db.query(ContentItem).filter(ContentItem.id == item_id).first()
    if not item:
        return RedirectResponse(url="/dashboard", status_code=302)

    if user.role == "editor" and item.created_by != user.id:
        return RedirectResponse(url="/dashboard", status_code=302)

    posts = db.query(GeneratedPost).filter(GeneratedPost.content_item_id == item_id).all()

    platform_names = {
        "telegram_channel": ("✈️", "Telegram канал"),
        "telegram_group": ("👥", "Telegram группа"),
        "telegram_stories": ("🎬", "Telegram Stories"),
        "vk": ("🔵", "ВКонтакте"),
        "ok": ("🟠", "Одноклассники"),
        "yandex_maps": ("📍", "Яндекс Карты"),
        "yandex_zen": ("📰", "Яндекс Дзен"),
        "instagram": ("📸", "Instagram"),
    }

    file_paths = json.loads(item.file_paths or "[]")
    image_filename = os.path.basename(file_paths[0]) if file_paths else None

    return templates.TemplateResponse(
        request, "content_preview.html",
        {
            "user": user,
            "item": item,
            "posts": posts,
            "platform_names": platform_names,
            "image_filename": image_filename,
        },
    )


PLATFORM_NAMES = {
    "telegram_channel": ("✈️", "Telegram канал"),
    "telegram_group": ("👥", "Telegram группа"),
    "telegram_stories": ("🎬", "Telegram Stories"),
    "vk": ("🔵", "ВКонтакте"),
    "ok": ("🟠", "Одноклассники"),
    "yandex_maps": ("📍", "Яндекс Карты"),
    "yandex_zen": ("📰", "Яндекс Дзен"),
    "instagram": ("📸", "Instagram"),
}


@router.get("/posts/approve/{item_id}", response_class=HTMLResponse)
def approve_page(request: Request, item_id: int, approved: int = 0,
                 published: int = 0, failed: int = 0, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    if user.role == "editor":
        return RedirectResponse(url=f"/content/{item_id}/preview", status_code=302)

    item = db.query(ContentItem).filter(ContentItem.id == item_id).first()
    if not item:
        return RedirectResponse(url="/dashboard", status_code=302)

    posts = db.query(GeneratedPost).filter(GeneratedPost.content_item_id == item_id).all()

    if approved and published == 0 and failed == 0:
        flash = f"Запланировано постов: {approved}."
    elif published or failed:
        parts = []
        if published:
            parts.append(f"✅ Опубликовано: {published}")
        if failed:
            parts.append(f"❌ Ошибок: {failed}")
        flash = " · ".join(parts)
    else:
        flash = None

    file_paths = json.loads(item.file_paths or "[]")
    image_filename = os.path.basename(file_paths[0]) if file_paths else None

    return templates.TemplateResponse(
        request, "approve.html",
        {
            "user": user,
            "item": item,
            "posts": posts,
            "platform_names": PLATFORM_NAMES,
            "flash": flash,
            "image_filename": image_filename,
        },
    )


@router.post("/posts/approve/{item_id}")
async def approve_submit(
    request: Request,
    item_id: int,
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    if user.role not in ("approver", "admin"):
        return RedirectResponse(url="/dashboard", status_code=302)

    item = db.query(ContentItem).filter(ContentItem.id == item_id).first()
    if not item:
        return RedirectResponse(url="/dashboard", status_code=302)

    form = await request.form()
    action = form.get("action", "approve")

    posts = db.query(GeneratedPost).filter(GeneratedPost.content_item_id == item_id).all()

    if action == "reject_all":
        for post in posts:
            if post.status not in ("published",):
                post.status = "rejected"
        db.commit()
        request.session["flash"] = "Материал отклонён."
        return RedirectResponse(url="/posts/pending", status_code=302)

    # Парсим scheduled_at
    schedule_mode = form.get("schedule_mode", "now")
    scheduled_at = None
    if schedule_mode == "later":
        raw_dt = form.get("scheduled_at", "")
        if raw_dt:
            try:
                # datetime-local приходит как "2024-01-15T14:30" — трактуем как МСК (UTC+3)
                naive = datetime.strptime(raw_dt, "%Y-%m-%dT%H:%M")
                scheduled_at = naive - timedelta(hours=3)  # конвертируем в UTC
            except ValueError:
                pass
    if scheduled_at is None:
        scheduled_at = datetime.utcnow()

    approved_count = 0
    for post in posts:
        if post.status in ("published", "failed"):
            continue
        include_key = f"include_{post.id}"
        text_key = f"text_{post.id}"
        included = form.get(include_key) == "1"
        new_text = form.get(text_key, post.text or "").strip()

        if included:
            post.text = new_text
            post.status = "approved"
            post.approved_by = user.id
            post.approved_at = datetime.utcnow()
            post.scheduled_at = scheduled_at
            approved_count += 1
        else:
            post.status = "rejected"

    db.commit()

    # Публикуем немедленно если выбран режим "сразу"
    published_count = 0
    failed_count = 0
    if schedule_mode == "now" and approved_count > 0:
        file_paths = json.loads(item.file_paths or "[]")
        image_path = file_paths[0] if file_paths else None

        for post in posts:
            if post.status != "approved":
                continue
            publisher = get_publisher(post.platform)
            if not publisher or not publisher.is_configured():
                continue

            result = publisher.publish(post.text or "", image_path=image_path)

            pub = Publication(
                generated_post_id=post.id,
                platform=post.platform,
                published_at=datetime.utcnow() if result.success else None,
                platform_post_id=result.platform_post_id,
                post_url=result.post_url,
                success=result.success,
                error_message=result.error_message,
            )
            db.add(pub)

            if result.success:
                post.status = "published"
                published_count += 1
            else:
                failed_count += 1

        db.commit()

    if schedule_mode == "later":
        request.session["flash"] = f"Запланировано постов: {approved_count}."
    elif published_count or failed_count:
        parts = []
        if published_count:
            parts.append(f"Опубликовано: {published_count}")
        if failed_count:
            parts.append(f"Ошибок: {failed_count}")
        request.session["flash"] = " · ".join(parts)
    else:
        request.session["flash"] = "Готово."

    return RedirectResponse(url="/posts/pending", status_code=302)


@router.post("/posts/{post_id}/save")
async def save_post_text(request: Request, post_id: int, db: Session = Depends(get_db)):
    """Сохранение текста черновика — для редакторов и согласующих."""
    user = get_current_user(request, db)
    if not user:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    post = db.query(GeneratedPost).filter(GeneratedPost.id == post_id).first()
    if not post:
        return JSONResponse({"error": "not found"}, status_code=404)

    item = db.query(ContentItem).filter(ContentItem.id == post.content_item_id).first()
    if not item:
        return JSONResponse({"error": "not found"}, status_code=404)

    if user.role == "editor" and item.created_by != user.id:
        return JSONResponse({"error": "forbidden"}, status_code=403)

    if post.status in ("published", "rejected"):
        return JSONResponse({"error": "cannot edit"}, status_code=400)

    form = await request.form()
    text = (form.get("text") or "").strip()
    post.text = text
    db.commit()

    return JSONResponse({"ok": True, "chars": len(text)})
