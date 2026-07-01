import os
from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings
from app.database import Base, engine
from app.routers import admin as admin_router
from app.routers import auth as auth_router
from app.routers import content as content_router
from app.routers import dashboard as dashboard_router
from app.scheduler import publish_scheduled_posts

Base.metadata.create_all(bind=engine)


def _seed_prompts() -> None:
    """Заполняет таблицу промптов при первом запуске."""
    from app.database import SessionLocal
    from app.models import PromptTemplate
    from app.services.prompts import PLATFORM_PROMPTS, PLATFORM_DISPLAY_NAMES
    db = SessionLocal()
    try:
        if db.query(PromptTemplate).count() == 0:
            for pid, prompt in PLATFORM_PROMPTS.items():
                db.add(PromptTemplate(
                    platform_id=pid,
                    platform_name=PLATFORM_DISPLAY_NAMES.get(pid, pid),
                    prompt=prompt.strip(),
                ))
            db.commit()
    finally:
        db.close()


_seed_prompts()


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.add_job(publish_scheduled_posts, "interval", minutes=1, id="scheduled_publisher")
    scheduler.start()
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(
    title="Домик — Панель постинга",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
    lifespan=lifespan,
)

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SECRET_KEY,
    max_age=28800,  # 8 часов
    https_only=True,
    same_site="lax",
)

os.makedirs("static", exist_ok=True)
os.makedirs("uploads", exist_ok=True)

app.mount("/static", StaticFiles(directory="static"), name="static")
# /uploads раздаётся через защищённый роут в content router (требует авторизации)

app.include_router(auth_router.router)
app.include_router(content_router.router)
app.include_router(dashboard_router.router)
app.include_router(admin_router.router)


@app.get("/")
def root():
    return RedirectResponse(url="/dashboard", status_code=302)
