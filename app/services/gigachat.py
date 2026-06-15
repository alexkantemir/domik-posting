import uuid
import requests

from app.config import settings

OAUTH_URL = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
API_URL = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"
MODEL = "GigaChat"

# GigaChat использует российский УЦ (Минцифры).
# В Dockerfile сертификат скачивается и добавляется в системный bundle через update-ca-certificates.
# Используем системный bundle (verify=True); если GigaChat недоступен — проверить Dockerfile.
_SSL_VERIFY: bool | str = True


def _get_token() -> str:
    # GigaChat выдаёт CLIENT_SECRET уже как готовую base64-строку "client_id:secret"
    resp = requests.post(
        OAUTH_URL,
        headers={
            "Authorization": f"Basic {settings.GIGACHAT_CLIENT_SECRET}",
            "RqUID": str(uuid.uuid4()),
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={"scope": settings.GIGACHAT_SCOPE},
        verify=_SSL_VERIFY,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def generate_text(system_prompt: str, user_message: str) -> str:
    token = _get_token()
    resp = requests.post(
        API_URL,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json={
            "model": MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "temperature": 0.8,
            "max_tokens": 1500,
        },
        verify=_SSL_VERIFY,
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()
