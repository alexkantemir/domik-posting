import requests
from typing import Optional
from urllib.parse import urlparse

from app.config import settings
from app.services.publishers.base import BasePublisher, PublishResult

MAX_API_BASE = "https://platform-api2.max.ru"
_TRUSTED_UPLOAD_SUFFIXES = (".oneme.ru", ".max.ru")


class MAXPublisher(BasePublisher):
    platform_id = "max"
    platform_name = "MAX"
    icon = "🟣"

    def is_configured(self) -> bool:
        return bool(settings.MAX_BOT_TOKEN and settings.MAX_CHAT_ID)

    def publish(self, text: str, image_path: Optional[str] = None, **kwargs) -> PublishResult:
        token = settings.MAX_BOT_TOKEN
        chat_id = int(settings.MAX_CHAT_ID)
        headers = {"Authorization": token, "Content-Type": "application/json"}

        try:
            body: dict = {"text": text}

            if image_path:
                attachment_token = self._upload_image(token, image_path)
                if attachment_token:
                    body["attachments"] = [
                        {"type": "image", "payload": {"token": attachment_token}}
                    ]

            resp = requests.post(
                f"{MAX_API_BASE}/messages",
                headers=headers,
                params={"chat_id": chat_id},
                json=body,
                timeout=30,
            )
            data = resp.json()

            # Реальная структура ответа: {"message": {"body": {"mid": "..."}, ...}}
            if resp.status_code == 200 and "message" in data:
                mid = data["message"].get("body", {}).get("mid", "")
                return PublishResult(success=True, platform_post_id=mid)

            error_msg = data.get("message") or data.get("code") or "Неизвестная ошибка MAX"
            return PublishResult(success=False, error_message=str(error_msg))

        except Exception as e:
            return PublishResult(success=False, error_message=str(e))

    def _upload_image(self, token: str, image_path: str) -> Optional[str]:
        try:
            # Шаг 1: получаем URL для загрузки
            resp = requests.post(
                f"{MAX_API_BASE}/uploads",
                headers={"Authorization": token},
                params={"type": "image"},
                timeout=15,
            )
            upload_data = resp.json()
            upload_url = upload_data.get("url")
            if not upload_url:
                return None

            # SSRF-защита: проверяем домен
            parsed = urlparse(upload_url)
            hostname = parsed.hostname or ""
            if parsed.scheme != "https" or not any(
                hostname.endswith(s) for s in _TRUSTED_UPLOAD_SUFFIXES
            ):
                raise ValueError(f"Недоверенный upload URL: {upload_url}")

            # Шаг 2: загружаем файл — токен приходит в ответе на upload, не на /uploads
            with open(image_path, "rb") as f:
                upload_resp = requests.post(upload_url, files={"data": f}, timeout=30)

            if upload_resp.status_code not in (200, 204):
                return None

            # Структура ответа: {"photos": {"<photo_id>": {"token": "..."}}}
            photos = upload_resp.json().get("photos", {})
            if not photos:
                return None

            first_photo = next(iter(photos.values()))
            return first_photo.get("token")

        except Exception:
            return None
