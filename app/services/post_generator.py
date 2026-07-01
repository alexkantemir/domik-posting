import time

from sqlalchemy.orm import Session

from app.event_log import log_event
from app.services.content_processor import NormalizedContent
from app.services.gigachat import generate_text
from app.services.prompts import PLATFORM_PROMPTS


_REFUSAL_MARKERS = [
    "временно ограничены",
    "чувствительными темами",
    "некорректные ответы",
    "не могу выполнить",
    "не могу помочь",
]


def _is_refusal(text: str) -> bool:
    return any(m in text for m in _REFUSAL_MARKERS)


def _load_prompts(db: Session) -> dict:
    """Загружает промпты из БД; если таблица пуста — возвращает захардкоженные."""
    from app.models import PromptTemplate
    rows = db.query(PromptTemplate).all()
    if rows:
        return {r.platform_id: r.prompt for r in rows}
    return PLATFORM_PROMPTS


def generate_posts(content: NormalizedContent, db: Session) -> dict:
    """
    Генерирует тексты постов для всех платформ через GigaChat.
    Возвращает: {platform_id: {"text": str, "ok": bool, "error": str|None}}
    """
    prompts = _load_prompts(db)
    user_message = (
        "Подготовь информационный пост для официальной страницы образовательного учреждения "
        f"на основе следующего материала:\n\n{content.text}"
    )

    results = {}
    for platform, system_prompt in prompts.items():
        text = ""
        error = None
        ok = False
        for attempt in range(2):
            t0 = time.monotonic()
            try:
                text = generate_text(system_prompt, user_message)
                duration_ms = int((time.monotonic() - t0) * 1000)
                if _is_refusal(text):
                    log_event("gigachat_call", platform=platform, attempt=attempt + 1,
                              status="refusal", duration_ms=duration_ms)
                    error = "GigaChat отказал (фильтр). Попробуйте переформулировать материал."
                    text = ""
                    continue
                log_event("gigachat_call", platform=platform, attempt=attempt + 1,
                          status="ok", duration_ms=duration_ms)
                ok = True
                error = None
                break
            except Exception as e:
                duration_ms = int((time.monotonic() - t0) * 1000)
                error = str(e)
                log_event("gigachat_call", platform=platform, attempt=attempt + 1,
                          status="error", duration_ms=duration_ms, error=str(e)[:300])
        results[platform] = {"text": text, "ok": ok, "error": error}

    return results
