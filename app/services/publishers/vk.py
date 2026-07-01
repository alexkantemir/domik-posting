import requests
from typing import Optional
from urllib.parse import urlparse

from app.config import settings
from app.services.publishers.base import BasePublisher, PublishResult

VK_API_VERSION = "5.199"


class VKPublisher(BasePublisher):
    platform_id = "vk"
    platform_name = "ВКонтакте"
    icon = "🔵"

    def is_configured(self) -> bool:
        return bool(settings.VK_COMMUNITY_TOKEN and settings.VK_GROUP_ID)

    def publish(self, text: str, image_path: Optional[str] = None, **kwargs) -> PublishResult:
        community_token = settings.VK_COMMUNITY_TOKEN
        user_token = settings.VK_USER_TOKEN or community_token
        group_id = self._clean_group_id(settings.VK_GROUP_ID)

        try:
            attachment = None
            if image_path:
                attachment = self._upload_photo(user_token, group_id, image_path)
                # If photo upload fails — post text only, don't abort

            params = {
                "access_token": community_token,
                "owner_id": f"-{group_id}",
                "from_group": 1,
                "message": text,
                "v": VK_API_VERSION,
            }
            if attachment:
                params["attachments"] = attachment

            resp = requests.post("https://api.vk.com/method/wall.post", params=params, timeout=30)
            data = resp.json()

            if "response" in data:
                post_id = data["response"]["post_id"]
                post_url = f"https://vk.com/wall-{group_id}_{post_id}"
                return PublishResult(success=True, platform_post_id=str(post_id), post_url=post_url)

            error = data.get("error", {})
            return PublishResult(success=False, error_message=error.get("error_msg", "Неизвестная ошибка VK"))

        except Exception as e:
            return PublishResult(success=False, error_message=str(e))

    def _clean_group_id(self, raw: str) -> str:
        raw = raw.lstrip("-")
        if raw.isdigit():
            return raw
        for prefix in ("club", "public"):
            if raw.startswith(prefix):
                return raw[len(prefix):]
        return raw

    def _upload_photo(self, token: str, group_id: str, image_path: str) -> Optional[str]:
        try:
            # Получаем адрес сервера загрузки
            resp = requests.get(
                "https://api.vk.com/method/photos.getWallUploadServer",
                params={"access_token": token, "group_id": group_id, "v": VK_API_VERSION},
                timeout=15,
            )
            upload_url = resp.json()["response"]["upload_url"]

            # Проверяем что upload_url ведёт на доверенный домен VK (защита от SSRF)
            _parsed = urlparse(upload_url)
            if _parsed.scheme != "https" or not (_parsed.hostname or "").endswith((".vk.com", ".userapi.com")):
                raise ValueError(f"Недоверенный upload URL: {upload_url}")

            # Загружаем файл
            with open(image_path, "rb") as f:
                resp = requests.post(upload_url, files={"photo": f}, timeout=30)
            upload_data = resp.json()

            # Сохраняем на сервере VK
            resp = requests.post(
                "https://api.vk.com/method/photos.saveWallPhoto",
                params={
                    "access_token": token,
                    "group_id": group_id,
                    "photo": upload_data["photo"],
                    "server": upload_data["server"],
                    "hash": upload_data["hash"],
                    "v": VK_API_VERSION,
                },
                timeout=15,
            )
            saved = resp.json()["response"][0]
            return f"photo{saved['owner_id']}_{saved['id']}"

        except Exception:
            return None
