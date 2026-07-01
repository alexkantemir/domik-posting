# Логирование — Домик Постинг

## Что внедрено

Структурированный JSONL-лог в `logs/app.jsonl`. Каждое событие — одна строка JSON.

Хранение: файл на сервере в `/opt/domik-posting/logs/app.jsonl`, примонтирован как Docker volume (`./logs:/app/logs`). Файл не попадает в git.

## Где лежат логи

На сервере: `/opt/domik-posting/logs/app.jsonl`

Смотреть через скрипт:
```bash
# Последние 50 событий
docker exec domik-posting-app-1 python scripts/view_logs.py

# Фильтр по типу событий
docker exec domik-posting-app-1 python scripts/view_logs.py --event publish

# С даты
docker exec domik-posting-app-1 python scripts/view_logs.py --since 2026-07-01

# Экспорт в CSV
docker exec domik-posting-app-1 python scripts/view_logs.py --export /app/logs/export.csv
```

Или читать напрямую с сервера (SSH):
```bash
tail -f /opt/domik-posting/logs/app.jsonl
```

## Какие события логируются

| Событие | Когда | Ключевые поля |
|---|---|---|
| `login_ok` | Успешный вход | user_id, email (маск.), role |
| `login_fail` | Неверный логин/пароль | email (маск.) |
| `logout` | Выход из системы | user_id |
| `content_create` | Создан новый материал | user_id, content_type, has_file, text_len |
| `gigachat_call` | Вызов GigaChat API | platform, attempt, status, duration_ms, error |
| `approve` | Согласование материала | user_id, item_id, approved, schedule_mode |
| `reject_all` | Отклонение материала | user_id, item_id |
| `publish` | Публикация в соцсеть | trigger, post_id, item_id, platform, status, duration_ms, post_url, error |
| `prompt_update` | Изменён системный промпт | user_id, platform_id |
| `prompt_reset` | Сброс промпта к умолчанию | user_id, platform_id |
| `user_create` | Создан пользователь | admin_id, target_email (маск.), role |
| `user_update` | Изменён пользователь | admin_id, target_id, fields_changed |
| `user_toggle` | Активация/деактивация | admin_id, target_id, active |

Поле `trigger` в событии `publish`: `manual` — из интерфейса согласования, `scheduled` — автоматически планировщиком.

## Что НЕ попадает в логи

- Пароли и токены
- Текст постов и исходных материалов
- Cookie и заголовки авторизации
- Email в полном виде (всегда маскируется: `al***@example.com`)
- Сообщения об ошибках урезаются до 300 символов

## Формат записи

```json
{"ts":"2026-07-01T10:23:45Z","event":"publish","trigger":"manual","post_id":42,"item_id":15,"platform":"telegram_channel","status":"success","duration_ms":1234,"post_url":"https://t.me/..."}
```

## Как проверить что логирование работает

1. Войди в систему → появится `login_ok`
2. Создай материал → появятся `content_create` + несколько `gigachat_call`
3. Согласуй и опубликуй → появятся `approve` + `publish`

Проверка:
```bash
# На сервере через SSH
tail -20 /opt/domik-posting/logs/app.jsonl | python3 -m json.tool
```

## Чтение с локального компьютера

```powershell
# Скачать лог с сервера
scp -i $env:USERPROFILE\.ssh\id_ed25519_domik root@201.51.6.88:/opt/domik-posting/logs/app.jsonl logs/

# Просмотреть
py -3 scripts/view_logs.py --tail 100

# Экспорт в CSV для Excel
py -3 scripts/view_logs.py --all --export export.csv
```
