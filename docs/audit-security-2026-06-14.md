# Security Audit — Домик Постинг
**Дата:** 14 июня 2026  
**Стандарты:** OWASP Top 10 (2021), CIS Benchmarks  
**Стек:** FastAPI + SQLAlchemy + PostgreSQL + nginx + Docker / Ubuntu 22.04.5 LTS  
**Домен:** post.domik-l.spb.ru

---

## СВОДКА

| Приоритет | Кол-во |
|-----------|--------|
| 🔴 Критично | 5 |
| 🟠 Высокий | 6 |
| 🟡 Средний | 5 |
| 🟢 Низкий | 4 |

---

## 🔴 КРИТИЧНЫЕ УЯЗВИМОСТИ

### КРИТ-1: SSRF — `process_url()` без валидации входящего URL
**OWASP A10:2021 — Server-Side Request Forgery**  
**Файл:** `app/services/content_processor.py`

```python
def process_url(url: str) -> NormalizedContent:
    resp = requests.get(url, ...)  # URL от пользователя без проверки
```

**Риск:** Авторизованный пользователь может передать:
- `http://169.254.169.254/latest/meta-data/` — облачный metadata service
- `http://db:5432/` — PostgreSQL во внутренней docker-сети
- `http://app:8000/` — сам сервис изнутри
- Любые внутренние IP/хосты сети хостера

**Решение:**
```python
from urllib.parse import urlparse
import ipaddress

ALLOWED_SCHEMES = {"http", "https"}
BLOCKED_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0",
                 "169.254.169.254", "metadata.google.internal",
                 "app", "db"}

def _validate_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in ALLOWED_SCHEMES:
        raise ValueError(f"Недопустимая схема: {parsed.scheme}")
    host = parsed.hostname or ""
    if host.lower() in BLOCKED_HOSTS:
        raise ValueError(f"Недопустимый хост: {host}")
    try:
        ip = ipaddress.ip_address(host)
        if ip.is_private or ip.is_loopback or ip.is_link_local:
            raise ValueError(f"Приватный IP недопустим: {ip}")
    except ValueError as e:
        if "Недопустимый" in str(e) or "Приватный" in str(e):
            raise

def process_url(url: str) -> NormalizedContent:
    _validate_url(url)
    # ... остальной код
```

---

### КРИТ-2: Загрузка файлов без валидации типа
**OWASP A03:2021 — Injection / A04 — Insecure Design**  
**Файл:** `app/routers/content.py`

```python
ext = os.path.splitext(file.filename)[1].lower()  # доверяем расширению от клиента
filename = f"{uuid.uuid4()}{ext}"
```

**Риски:**
1. Можно загрузить `.py`, `.sh`, `.html` — нет белого списка расширений
2. Нет проверки MIME по magic bytes
3. `/uploads` смонтирован публично без аутентификации — любой файл доступен по прямому URL

**Решение:**
```python
ALLOWED_MIME_TYPES = {
    "image/jpeg", "image/png", "image/gif", "image/webp",
    "video/mp4", "audio/mpeg", "application/pdf"
}
MIME_TO_EXT = {
    "image/jpeg": ".jpg", "image/png": ".png", "image/gif": ".gif",
    "image/webp": ".webp", "video/mp4": ".mp4",
    "audio/mpeg": ".mp3", "application/pdf": ".pdf"
}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

import magic  # python-magic

def save_upload(file: UploadFile) -> str:
    content = file.file.read()
    if len(content) > MAX_FILE_SIZE:
        raise ValueError("Файл слишком большой (макс. 50MB)")
    mime = magic.from_buffer(content, mime=True)
    if mime not in ALLOWED_MIME_TYPES:
        raise ValueError(f"Недопустимый тип файла: {mime}")
    ext = MIME_TO_EXT[mime]
    filename = f"{uuid.uuid4()}{ext}"
    safe_path = os.path.realpath(os.path.join(UPLOAD_DIR, filename))
    if not safe_path.startswith(os.path.realpath(UPLOAD_DIR)):
        raise ValueError("Path traversal detected")
    with open(safe_path, "wb") as f:
        f.write(content)
    return safe_path
```

В `main.py` убрать публичный маунт `/uploads`, заменить защищённым роутом:
```python
@app.get("/uploads/{filename}")
def serve_upload(filename: str, user=Depends(require_user)):
    return FileResponse(os.path.join(UPLOAD_DIR, filename))
```

---

### КРИТ-3: SSL-верификация отключена в GigaChat-клиенте
**OWASP A02:2021 — Cryptographic Failures**  
**Файл:** `app/services/gigachat.py`

```python
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
resp = requests.post(OAUTH_URL, ..., verify=False, ...)
resp = requests.post(API_URL,  ..., verify=False, ...)
```

**Риск:** MitM-атака позволяет перехватить `GIGACHAT_CLIENT_SECRET`, токены и весь контент, отправляемый на генерацию.

**Решение:** Добавить CA-сертификат Сбербанка в образ:
```dockerfile
# Dockerfile
COPY certs/russian_trusted_root_ca.pem /usr/local/share/ca-certificates/sber.crt
RUN update-ca-certificates
```
```python
SBER_CA = "/etc/ssl/certs/ca-certificates.crt"
resp = requests.post(OAUTH_URL, verify=SBER_CA, ...)
```

Скачать сертификат: https://www.sberbank.ru/common/img/uploaded/redirected/rebrending-2020/certificates/russian_trusted_root_ca.cer

---

### КРИТ-4: Firewall выключен — порт Zabbix открыт в интернет
**CIS Benchmark: Network Access Controls**

```
ufw status: inactive
LISTEN 0.0.0.0:10050  # Zabbix Agent — открыт всему интернету
LISTEN 0.0.0.0:22     # SSH без rate-limit
```

**Решение:**
```bash
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow from <ZABBIX_SERVER_IP> to any port 10050
ufw enable

# Внимание: Docker обходит ufw через iptables — добавить в /etc/docker/daemon.json:
# { "iptables": false }
# И управлять правилами вручную или через ufw-docker
```

---

### КРИТ-5: Docker-контейнер app работает от root
**CIS Docker Benchmark 4.1**

```
User в контейнере: root
ReadonlyRootfs: false
SecurityOpt: null
```

**Риск:** RCE внутри контейнера = root-доступ к файловой системе контейнера.

**Решение — Dockerfile:**
```dockerfile
RUN groupadd -r appuser && useradd -r -g appuser appuser
RUN mkdir -p uploads && chown -R appuser:appuser /app
COPY --chown=appuser:appuser . .
USER appuser
```

**Решение — docker-compose.yml:**
```yaml
app:
  security_opt:
    - no-new-privileges:true
  read_only: true
  tmpfs:
    - /tmp
```

---

## 🟠 ВЫСОКИЕ УЯЗВИМОСТИ

### ВЫСОК-1: SSH root-логин по паролю + нет fail2ban
**OWASP A07:2021 | CIS 5.2.9**

```
PermitRootLogin yes
PasswordAuthentication yes (по умолчанию)
MaxAuthTries 6 (по умолчанию)
fail2ban: не установлен
```

**Решение:**
```bash
apt install fail2ban -y
systemctl enable fail2ban --now

# /etc/fail2ban/jail.local
[sshd]
enabled = true
maxretry = 3
bantime = 3600
findtime = 600
```

```
# /etc/ssh/sshd_config
PermitRootLogin prohibit-password
PasswordAuthentication no
MaxAuthTries 3
```

⚠️ Перед отключением паролей — обязательно добавить SSH-ключ в `~/.ssh/authorized_keys`

---

### ВЫСОК-2: Нет rate-limit на `/login`
**OWASP A07:2021 — Authentication Failures**

Неограниченный перебор паролей.

**Решение — nginx:**
```nginx
limit_req_zone $binary_remote_addr zone=login_limit:10m rate=5r/m;

location /login {
    limit_req zone=login_limit burst=3 nodelay;
    limit_req_status 429;
    proxy_pass http://app:8000;
}
```

---

### ВЫСОК-3: Редактор может публиковать посты (broken access control)
**OWASP A01:2021 — Broken Access Control**  
**Файл:** `app/routers/content.py`

```python
@router.post("/posts/approve/{item_id}")
async def approve_submit(...):
    user = get_current_user(request, db)  # только проверка логина, не роли
```

**Решение:**
```python
if user.role != "approver":
    return RedirectResponse(url="/dashboard", status_code=302)
```

---

### ВЫСОК-4: Нет CSRF-защиты
**OWASP A01:2021 — Broken Access Control**

Все POST-формы (login, content/new, posts/approve) без CSRF-токенов.

**Решение:**
```bash
pip install starlette-csrf
```
```python
# app/main.py
from starlette_csrf import CSRFMiddleware
app.add_middleware(CSRFMiddleware, secret=settings.SECRET_KEY)
```

---

### ВЫСОК-5: `SECRET_KEY` с небезопасным значением по умолчанию
**OWASP A02:2021**  
**Файл:** `app/config.py`

```python
SECRET_KEY: str = "dev-secret-key-change-in-production"
```

Знание ключа позволяет подделать любую сессию.

**Решение:**
```python
SECRET_KEY: str  # убрать default — приложение не запустится без него

@validator("SECRET_KEY")
def secret_key_strong(cls, v):
    if len(v) < 32 or v in ("dev-secret-key-change-in-production",):
        raise ValueError("Небезопасный SECRET_KEY")
    return v
```

---

### ВЫСОК-6: Внутренние пути и исключения видны пользователю
**OWASP A04:2021 — Insecure Design**  
**Файл:** `app/routers/content.py`

```python
except Exception as e:
    {"error": f"Ошибка обработки материала: {e}"}  # stack trace в ответе
```

**Решение:**
```python
import logging
logger = logging.getLogger(__name__)

except Exception as e:
    logger.error("Content processing error: %s", e, exc_info=True)
    {"error": "Ошибка обработки материала. Попробуйте снова."}
```

---

## 🟡 СРЕДНИЕ УЯЗВИМОСТИ

### СРЕДН-1: Отсутствуют security-заголовки HTTP
**OWASP A05:2021**

Nginx не выдаёт ни одного защитного заголовка.

**Решение — nginx:**
```nginx
add_header X-Frame-Options "SAMEORIGIN" always;
add_header X-Content-Type-Options "nosniff" always;
add_header X-XSS-Protection "1; mode=block" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline' cdn.jsdelivr.net; style-src 'self' 'unsafe-inline' cdn.jsdelivr.net;" always;
server_tokens off;
```

---

### СРЕДН-2: Session cookie без флагов `Secure` и `SameSite`
**OWASP A07:2021**

**Решение:**
```python
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SECRET_KEY,
    max_age=86400,
    https_only=True,  # Secure flag
    same_site="lax",
)
```

---

### СРЕДН-3: Нет логирования событий безопасности
**OWASP A09:2021**

Не логируются: неудачные входы, успешные входы, публикации, ошибки авторизации, загрузки файлов.

**Решение:**
```python
security_logger = logging.getLogger("security")

# В auth.py:
security_logger.warning("LOGIN_FAILED email=%s ip=%s", email, request.client.host)
security_logger.info("LOGIN_SUCCESS user_id=%s ip=%s", user.id, request.client.host)
```

---

### СРЕДН-4: `server_tokens on` (версия nginx раскрыта)

**Решение:** `server_tokens off;` в nginx.conf

---

### СРЕДН-5: `ReadonlyRootfs: false` + нет `no-new-privileges`

Решение указано в КРИТ-5 (docker-compose.yml).

---

## 🟢 НИЗКИЕ УЯЗВИМОСТИ

### НИЗ-1: Зависимости без pinning версий
**Файл:** `requirements.txt`

Использует `>=` — при пересборке могут подтянуться уязвимые версии.

**Решение:**
```bash
pip install pip-tools
pip-compile requirements.in --generate-hashes -o requirements.lock
# В Dockerfile:
RUN pip install --require-hashes -r requirements.lock
```

---

### НИЗ-2: `DATABASE_URL` с SQLite по умолчанию

```python
DATABASE_URL: str = "sqlite:///./domik.db"
```

При отсутствии `.env` — молчаливое переключение на SQLite без многопоточности.

**Решение:** Убрать default-значение, сделать обязательным.

---

### НИЗ-3: Zabbix-агент (порт 10050) без ограничений

Решение в КРИТ-4 — ограничить ufw-правилом на IP Zabbix-сервера.

---

### НИЗ-4: HSTS без `preload`

После включения HSTS (СРЕДН-1) добавить `preload` и зарегистрировать на hstspreload.org.

---

## АРХИТЕКТУРНЫЕ ЗАМЕЧАНИЯ

**Планировщик задач отсутствует.** Поле `scheduled_at` заполняется, но нет celery/APScheduler для его исполнения. Публикация по расписанию не работает — только «сразу».

**Файлы без ограничения размера до записи.** nginx допускает `client_max_body_size 100M`, но код не проверяет размер перед сохранением на диск. DoS через загрузку огромных файлов.

**`file_paths` как JSON-строка в Text-колонке.** Нет нормализации, нет каскадного удаления. При удалении `ContentItem` файлы остаются на диске.

---

## ИТОГОВЫЙ ПЛАН ДЕЙСТВИЙ

### Немедленно (критично):
1. Включить `ufw`, закрыть порт 10050
2. Добавить валидацию URL в `process_url()` против SSRF
3. Белый список MIME при загрузке файлов + закрыть публичный `/uploads`
4. `USER appuser` в Dockerfile + `no-new-privileges` в compose
5. Исправить `verify=False` в GigaChat

### Следующий спринт (высокий):
6. SSH-ключи вместо пароля + fail2ban
7. `limit_req_zone` в nginx для `/login`
8. Проверка роли `approver` в POST `/posts/approve/{item_id}`
9. CSRF-защита (`starlette-csrf`)
10. Убрать default `SECRET_KEY`, добавить валидатор
11. Generic сообщения об ошибках + логирование

### В течение месяца (средний):
12. Security-заголовки в nginx
13. `https_only=True`, `same_site="lax"` в SessionMiddleware
14. Логирование событий безопасности
15. `server_tokens off`

### Улучшения:
16. `pip-compile --generate-hashes` для pinning зависимостей
17. HSTS preload
18. Celery/APScheduler для отложенных публикаций
19. Ограничение размера файла до записи

---

## СОСТОЯНИЕ СЕРВЕРА

| Параметр | Статус |
|----------|--------|
| OS | Ubuntu 22.04.5 LTS (поддерживается до 2027) ✅ |
| TLS | TLSv1.2 + TLSv1.3, Let's Encrypt (до Sep 2026) ✅ |
| HTTP→HTTPS редирект | Настроен ✅ |
| Firewall (ufw) | **Выключен** 🔴 |
| fail2ban | **Не установлен** 🔴 |
| SSH root по паролю | **Включён** 🟠 |
| Docker от root | **Да** 🔴 |
| DB порт наружу | Нет (только внутренняя сеть) ✅ |
| .env права | 600 root:root ✅ |
| unattended-upgrades | Установлен ✅ |
| Security Headers | **Отсутствуют** 🟡 |
| CSRF Protection | **Отсутствует** 🟠 |
| Rate Limiting | **Отсутствует** 🟠 |
