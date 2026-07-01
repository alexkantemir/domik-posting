import requests
from typing import Optional

from app.config import settings
from app.services.publishers.base import BasePublisher, PublishResult

CAPTION_LIMIT = 1024


def _escape_html(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _send_to_chat(base_url: str, chat_id: str, text: str, image_path: Optional[str]) -> dict:
    """Send photo+text or text-only, respecting Telegram's 1024-char caption limit."""
    safe_text = _escape_html(text)
    if image_path:
        if len(safe_text) <= CAPTION_LIMIT:
            with open(image_path, "rb") as photo:
                resp = requests.post(
                    f"{base_url}/sendPhoto",
                    data={"chat_id": chat_id, "caption": safe_text, "parse_mode": "HTML"},
                    files={"photo": photo},
                    timeout=30,
                )
            return resp.json()
        else:
            # Send photo first, then text as a separate message
            with open(image_path, "rb") as photo:
                r1 = requests.post(
                    f"{base_url}/sendPhoto",
                    data={"chat_id": chat_id},
                    files={"photo": photo},
                    timeout=30,
                )
            if not r1.json().get("ok"):
                return r1.json()
            r2 = requests.post(
                f"{base_url}/sendMessage",
                json={"chat_id": chat_id, "text": safe_text, "parse_mode": "HTML"},
                timeout=30,
            )
            return r2.json()
    else:
        resp = requests.post(
            f"{base_url}/sendMessage",
            json={"chat_id": chat_id, "text": safe_text, "parse_mode": "HTML"},
            timeout=30,
        )
        return resp.json()


class TelegramChannelPublisher(BasePublisher):
    platform_id = "telegram_channel"
    platform_name = "Telegram канал"
    icon = "✈️"

    def is_configured(self) -> bool:
        return bool(settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHANNEL_ID)

    def publish(self, text: str, image_path: Optional[str] = None, **kwargs) -> PublishResult:
        token = settings.TELEGRAM_BOT_TOKEN
        chat_id = settings.TELEGRAM_CHANNEL_ID
        base_url = f"https://api.telegram.org/bot{token}"
        try:
            data = _send_to_chat(base_url, chat_id, text, image_path)
            if data.get("ok"):
                msg = data["result"]
                post_url = f"https://t.me/c/{str(chat_id).lstrip('-100')}/{msg['message_id']}"
                return PublishResult(success=True, platform_post_id=str(msg["message_id"]), post_url=post_url)
            return PublishResult(success=False, error_message=data.get("description", "Неизвестная ошибка"))
        except Exception as e:
            return PublishResult(success=False, error_message=str(e))


class TelegramGroupPublisher(BasePublisher):
    platform_id = "telegram_group"
    platform_name = "Telegram группа"
    icon = "👥"

    def is_configured(self) -> bool:
        return bool(settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_GROUP_ID)

    def publish(self, text: str, image_path: Optional[str] = None, **kwargs) -> PublishResult:
        token = settings.TELEGRAM_BOT_TOKEN
        chat_id = settings.TELEGRAM_GROUP_ID
        base_url = f"https://api.telegram.org/bot{token}"
        try:
            data = _send_to_chat(base_url, chat_id, text, image_path)
            if data.get("ok"):
                msg = data["result"]
                return PublishResult(success=True, platform_post_id=str(msg["message_id"]))
            return PublishResult(success=False, error_message=data.get("description", "Неизвестная ошибка"))
        except Exception as e:
            return PublishResult(success=False, error_message=str(e))


class TelegramStoriesPublisher(BasePublisher):
    platform_id = "telegram_stories"
    platform_name = "Telegram Stories"
    icon = "🎬"

    def is_configured(self) -> bool:
        return False

    def publish(self, text: str, image_path: Optional[str] = None, **kwargs) -> PublishResult:
        return PublishResult(success=False, error_message="Telegram Stories будет подключён позже")
