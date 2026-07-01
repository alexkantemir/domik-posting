@.claude/skills/server/SKILL.md
@.claude/skills/sync-docs/SKILL.md

# Домик Постинг — обзор проекта для Claude

## Что это

Панель автопостинга для детского сада «Домик Монтессори» (Санкт-Петербург, domik-l.spb.ru).
Редакторы загружают материал → GigaChat генерирует посты под каждую соцсеть → согласующий
проверяет и публикует (немедленно или по расписанию).

Production: **https://post.domik-l.spb.ru** (сервер 201.51.6.88)

---

## Стек

| Слой | Технология |
|---|---|
| Backend | FastAPI + Uvicorn (Python 3.13) |
| Шаблоны | Jinja2 + Bootstrap 5.3 |
| БД (prod) | PostgreSQL 16 (TLS, self-signed cert, sslmode=require) |
| БД (dev) | SQLite |
| ORM | SQLAlchemy (sync) |
| Планировщик | APScheduler (BackgroundScheduler, интервал 1 мин) |
| ИИ | GigaChat API (Sberbank) — требует российских CA |
| Прокси | Nginx + Let's Encrypt |
| Деплой | Docker Compose (`docker compose up -d --build --force-recreate app`) |

---

## Архитектура — ключевые файлы

```
app/
├── main.py              # Точка входа: создаёт таблицы, сидирует промпты, запускает scheduler
├── event_log.py         # log_event() + mask_email() — JSONL-лог в logs/app.jsonl
├── config.py            # Все env-переменные (pydantic-settings), читает из .env
├── models.py            # SQLAlchemy модели (см. ниже)
├── auth.py              # get_current_user() из сессии, bcrypt хэши
├── csrf.py              # validate_csrf() — двойная проверка токена
├── jinja.py             # Jinja2-окружение с фильтрами (moscow — UTC→МСК)
├── database.py          # engine, SessionLocal, Base, get_db()
├── scheduler.py         # publish_scheduled_posts() — постит approved-посты с наступившим scheduled_at
│
├── routers/
│   ├── auth.py          # /login, /logout
│   ├── dashboard.py     # /dashboard, /posts/pending, /posts/scheduled, /posts/history
│   ├── content.py       # /content/new, /content/{id}/preview, /posts/approve/{id},
│   │                    # /posts/{id}/save, /uploads/{filename}
│   └── admin.py         # /admin/users/*, /admin/prompts/*, /admin/profile
│
├── services/
│   ├── gigachat.py      # generate_text(system_prompt, user_message) → str
│   ├── prompts.py       # PLATFORM_PROMPTS и PLATFORM_DISPLAY_NAMES (дефолтные значения)
│   ├── post_generator.py# generate_posts(content, db) — вызывает GigaChat для всех платформ
│   ├── content_processor.py  # process_url() + SSRF-защита (_safe_get, _validate_url)
│   └── publishers/
│       ├── base.py      # BasePublisher — интерфейс: platform_id, is_configured(), publish()
│       ├── registry.py  # PUBLISHERS список + get_publisher(platform_id)
│       ├── telegram.py  # TelegramChannelPublisher, TelegramGroupPublisher, TelegramStoriesPublisher
│       ├── vk.py        # VKPublisher — через VK API v5.131
│       └── max_publisher.py  # MAXPublisher — platform-api2.max.ru (мигрировали с api1 в июне 2026)
│
└── templates/           # Jinja2 HTML (base.html + страницы)

logs/                    # JSONL-лог (volume на сервере, не в git — только .gitkeep)
static/                  # JS-файлы (без inline JS для CSP)
│   base.js              # toggleSidebar, closeSidebar, nav listeners
│   approve.js           # логика страницы согласования
│   preview.js           # логика страницы предпросмотра редактора
│   content_new.js       # переключение типов контента
│   prompt_edit.js       # счётчик символов в редакторе промптов
```

---

## Модели БД

### User
`id, name, email, password_hash, role (editor|approver|admin), active, created_at`

### ContentItem
`id, type (text|url|photo|video|audio|photo_text), raw_text, file_paths (JSON), source_url, created_by→User, created_at`

### GeneratedPost
`id, content_item_id→ContentItem, platform (telegram_channel|telegram_group|vk|max|...), text, status (draft|approved|rejected|published|failed), approved_by→User, approved_at, scheduled_at, created_at`

### PromptTemplate
`id, platform_id, platform_name, prompt (Text), updated_at, updated_by→User`
Сидируется из `services/prompts.py` при первом запуске (если таблица пуста). Редактируется через `/admin/prompts`.

### Publication
`id, generated_post_id→GeneratedPost, platform, published_at, platform_post_id, post_url, success, error_message`
Создаётся после каждой попытки публикации (и при ошибке тоже).

---

## Роли и права

| Роль | Что может |
|---|---|
| `editor` | Создаёт материалы, редактирует свои черновики, видит только своё |
| `approver` | Всё что editor + согласование/отклонение/публикация всех материалов |
| `admin` | Всё что approver + управление пользователями + редактирование промптов |

---

## Жизненный цикл материала

1. Редактор создаёт материал (`/content/new`) — загружает текст / ссылку / файл
2. `process_url()` нормализует контент, `generate_posts()` дёргает GigaChat для каждой платформы
3. Создаются `GeneratedPost` со статусом `draft`
4. Редактор видит черновики на `/content/{id}/preview`, может редактировать тексты
5. Согласующий/Админ заходит в `/posts/approve/{id}`, выбирает платформы, редактирует тексты
6. Режим "Сразу" → немедленная публикация через publisher, статус `published`/`failed`
7. Режим "Позже" → `scheduled_at` сохраняется, scheduler публикует через `publish_scheduled_posts()`
8. Каждая публикация создаёт запись `Publication`

---

## Добавление новой платформы

1. Создать `app/services/publishers/platform.py` с классом `PlatformPublisher(BasePublisher)`:
   - Задать `platform_id = "platform_name"` (строка-ключ)
   - Реализовать `is_configured() → bool`
   - Реализовать `publish(text, image_path=None) → PublishResult`
2. Добавить в `app/services/publishers/registry.py` в список `PUBLISHERS`
3. Добавить env-переменные в `app/config.py` (класс `Settings`) и `.env.example`
4. Добавить промпт в `app/services/prompts.py` (в `PLATFORM_PROMPTS` и `PLATFORM_DISPLAY_NAMES`)
5. Добавить иконку и название в `PLATFORM_NAMES` в `app/routers/content.py`
6. Промпт автоматически попадёт в БД при следующем запуске (если он новый)

---

## Безопасность (реализовано)

- **CSRF**: double-submit cookie через `app/csrf.py`, все POST-формы имеют `csrf_token`
- **SSRF**: `_safe_get()` в `content_processor.py` — валидирует каждый редирект, блокирует приватные IP
- **CSP**: `script-src 'self' https://cdn.jsdelivr.net` — нет `unsafe-inline`, весь JS во внешних файлах
- **Uploads**: проверка mime-типа через `filetype`, path traversal защита (`os.path.realpath`), раздача только авторизованным
- **Сессии**: `https_only=True, same_site=lax, max_age=8ч`, инвалидация при смене пароля
- **Пароли**: bcrypt, минимум 12 символов
- **PostgreSQL**: TLS (`sslmode=require`), self-signed cert смонтирован в контейнер
- **Rate limiting**: nginx конфиг на `/login`
- **OpenAPI**: `docs_url=None, openapi_url=None` — закрыт

---

## Деплой

Редеплой (загрузка файлов + rebuild образа):
```powershell
$env:PYTHONIOENCODING="utf-8"
py -3.12 scripts/redeploy.py --host 201.51.6.88 --user root --key "C:\Users\AdmVps\.ssh\id_ed25519_domik"
```

Если `redeploy.py` не знает о новом файле — загрузить вручную через paramiko SFTP,
затем пересобрать образ:
```
docker compose up -d --build --force-recreate app
```

`docker compose restart app` — НЕ пересобирает образ, шаблоны и статика внутри него не обновятся.
`docker compose up -d --force-recreate app` (без `--build`) — НЕ перечитывает `.env`.

---

## GigaChat

Требует российских CA (Минцифры). В Dockerfile:
```dockerfile
COPY russian_trusted_ca_bundle.crt .
RUN python -c "import certifi; ..."   # патчит certifi
```
Токен получается через `GIGACHAT_CLIENT_ID` + `GIGACHAT_CLIENT_SECRET`.
Промпты для генерации читаются из таблицы `prompt_templates` (редактируются в `/admin/prompts`).
Fallback на `PLATFORM_PROMPTS` из `prompts.py` если таблица пуста.
