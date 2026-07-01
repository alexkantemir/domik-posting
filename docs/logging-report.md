# Отчёт: внедрение логирования в Домик Постинг

## 1. Что было сделано

### Новые файлы

| Файл | Назначение |
|---|---|
| `app/event_log.py` | Центральный модуль логирования: `log_event()` и `mask_email()` |
| `scripts/view_logs.py` | CLI-скрипт для просмотра, фильтрации и экспорта логов |
| `logs/.gitkeep` | Директория для логов зафиксирована в git, сами файлы — нет |
| `docs/logging.md` | Справочник: где логи, как смотреть, таблица событий |

### Изменённые файлы

| Файл | Что добавлено |
|---|---|
| `app/routers/auth.py` | `login_ok`, `login_fail`, `logout` |
| `app/routers/content.py` | `content_create`, `approve`, `reject_all`, `publish` (с timing) |
| `app/routers/admin.py` | `prompt_update`, `prompt_reset`, `user_create`, `user_update`, `user_toggle` |
| `app/services/post_generator.py` | `gigachat_call` на каждую платформу с `duration_ms` и статусом |
| `app/scheduler.py` | `publish` (trigger=scheduled) с timing и ошибкой при сбое |
| `docker-compose.yml` | Добавлен volume `./logs:/app/logs` |
| `Dockerfile` | `mkdir -p logs` с правильным владельцем `appuser` |
| `scripts/redeploy.py` | Добавлены все новые файлы в список загрузки; `chown 999:999 logs/` перед деплоем |
| `.gitignore` | `logs/*.jsonl` исключён из git; `docs/` заменён точечными исключениями |

### Выбранный механизм

**JSONL-файл** (`logs/app.jsonl`) — каждое событие одна строка JSON.

Почему не SQLite и не отдельная таблица в PostgreSQL:
- PostgreSQL уже занят основными данными приложения; логи туда — лишняя нагрузка и риск при инцидентах с БД
- SQLite рядом с PostgreSQL в одном контейнере создаёт путаницу
- JSONL — простейший формат: читается `tail -f`, экспортируется в CSV одной командой, не требует схемы, не ломается при падении
- Для этого масштаба (один сервер, один процесс) JSONL полностью достаточен

---

## 2. Что именно логируется

### Полный список событий

| Событие | Когда возникает | Поля |
|---|---|---|
| `login_ok` | Успешный вход | `user_id`, `email` (маск.), `role` |
| `login_fail` | Неверный логин или пароль | `email` (маск.) |
| `logout` | Выход из системы | `user_id` |
| `content_create` | Создан новый материал | `user_id`, `content_type`, `has_file`, `text_len` |
| `gigachat_call` | Вызов GigaChat на одну платформу | `platform`, `attempt`, `status`, `duration_ms`, `error` |
| `approve` | Материал согласован | `user_id`, `item_id`, `approved`, `schedule_mode`, `scheduled_at` |
| `reject_all` | Материал отклонён | `user_id`, `item_id` |
| `publish` | Публикация в соцсеть | `trigger`, `post_id`, `item_id`, `platform`, `status`, `duration_ms`, `post_url`, `error` |
| `prompt_update` | Изменён системный промпт GigaChat | `user_id`, `platform_id` |
| `prompt_reset` | Промпт сброшен к умолчанию | `user_id`, `platform_id` |
| `user_create` | Создан новый пользователь | `admin_id`, `target_email` (маск.), `role` |
| `user_update` | Данные пользователя изменены | `admin_id`, `target_id`, `fields_changed` |
| `user_toggle` | Пользователь активирован / деактивирован | `admin_id`, `target_id`, `active` |

### Поле `trigger` в событии `publish`
- `manual` — публикация из интерфейса согласования (approver нажал кнопку)
- `scheduled` — автоматическая публикация планировщиком по расписанию

### Статусы `gigachat_call`
- `ok` — успешная генерация
- `refusal` — GigaChat отказал (сработал контентный фильтр), будет повторная попытка
- `error` — сетевая или API ошибка

### Обработка ошибок
- Все ошибки публикации логируются с полем `error` (текст обрезается до 300 символов)
- При необработанном исключении в scheduler также пишется запись с `status=fail, error=unhandled_exception`
- Сам модуль `log_event()` перехватывает все исключения и не даёт им сломать приложение

### Защита чувствительных данных
- Email всегда маскируется: `alexander@example.com` → `al***@example.com`
- Пароли, токены, куки, заголовки авторизации — не пишутся нигде
- Текст постов и исходных материалов — не пишется
- Сообщения об ошибках обрезаются до 300 символов

---

## 3. Как это проверить

### Шаг 1 — Войти на сайт
Открыть https://post.domik-l.spb.ru, ввести логин и пароль.

### Шаг 2 — Проверить что событие появилось

**Вариант А — через SSH:**
```bash
ssh -i ~/.ssh/id_ed25519_domik root@201.51.6.88
tail -f /opt/domik-posting/logs/app.jsonl
```

**Вариант Б — через скрипт на сервере:**
```bash
docker exec domik-posting-app-1 python scripts/view_logs.py --tail 20
```

**Вариант В — скачать и посмотреть локально (Windows):**
```powershell
scp -i $env:USERPROFILE\.ssh\id_ed25519_domik root@201.51.6.88:/opt/domik-posting/logs/app.jsonl logs/
py -3 scripts/view_logs.py --tail 20
```

### Шаг 3 — Создать материал и проследить пайплайн

1. Нажать «Новый материал», вставить текст, отправить
2. В логе должны появиться: `content_create` + 4 записи `gigachat_call` (по одной на платформу)
3. Перейти к согласованию, нажать «Опубликовать»
4. Появятся: `approve` + `publish` для каждой настроенной платформы

### Шаг 4 — Проверить сценарий с ошибкой

Если GigaChat отказывает — в логе будет `gigachat_call` со `status=refusal` и следом ещё одна попытка. Это уже видно на реальных данных: платформа `max` дала `refusal` на попытке 1, `ok` на попытке 2.

### Команды для фильтрации

```powershell
# только публикации
py -3 scripts/view_logs.py --event publish

# только вызовы GigaChat
py -3 scripts/view_logs.py --event gigachat_call

# ошибки авторизации
py -3 scripts/view_logs.py --event login_fail

# события за сегодня
py -3 scripts/view_logs.py --since 2026-07-01

# экспорт всего в CSV
py -3 scripts/view_logs.py --all --export export.csv
```

---

## 4. Что получилось в итоге

Логирование внедрено и работает в production. Первые реальные данные, полученные сразу после запуска:

```
2026-07-01T05:48:58Z  logout                 user_id=1
2026-07-01T05:49:03Z  login_ok               user_id=3 email=ap***@domik-l.spb.ru role=approver
2026-07-01T05:49:19Z  content_create         user_id=3 content_type=text has_file=False text_len=37
2026-07-01T05:49:20Z  gigachat_call          platform=telegram_channel attempt=1 status=ok duration_ms=1300
2026-07-01T05:49:21Z  gigachat_call          platform=vk attempt=1 status=ok duration_ms=1205
2026-07-01T05:49:22Z  gigachat_call          platform=max attempt=1 status=refusal duration_ms=828
2026-07-01T05:49:23Z  gigachat_call          platform=max attempt=2 status=ok duration_ms=1078
2026-07-01T05:49:24Z  gigachat_call          platform=telegram_group attempt=1 status=ok duration_ms=459
2026-07-01T05:49:40Z  approve                user_id=3 item_id=40 approved=4 schedule_mode=later
```

**Что уже можно анализировать:**
- Среднее время ответа GigaChat по платформам
- Частота отказов (refusal) и на каких платформах они чаще
- Активность пользователей: кто, когда, сколько материалов
- Успешность публикаций по платформам (success vs fail)
- Несанкционированные попытки входа (`login_fail`)

**Готовность к развитию:** решение минимально инвазивное, не трогает основную логику. `log_event()` — одна функция, добавить новое событие занимает одну строку кода.

---

## 5. Что можно улучшить потом

1. **Ротация логов** — сейчас `app.jsonl` растёт бесконечно. Добавить `logging.handlers.TimedRotatingFileHandler` или cron-задачу `logrotate` на сервере (например, хранить 30 дней).

2. **Веб-интерфейс для логов** — страница `/admin/logs` с фильтрами и пагинацией прямо в панели, чтобы не нужно было заходить на сервер.

3. **Метрики по GigaChat** — отдельный дашборд: среднее время генерации, процент refusal по платформам, динамика по дням. Данные уже есть в логах.

4. **Алерты** — отправка уведомления в Telegram если публикация упала с ошибкой 3 раза подряд, или если `login_fail` больше 5 раз за минуту (возможная атака).

5. **Структурированный вывод в stdout** — сейчас `log_event()` пишет только в файл. Дублирование в stdout в JSON-формате позволит собирать логи стандартными Docker/cloud инструментами (Loki, CloudWatch, etc.) без изменения кода приложения.
