from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class PublishResult:
    success: bool
    platform_post_id: Optional[str] = None
    post_url: Optional[str] = None
    error_message: Optional[str] = None


class BasePublisher(ABC):
    platform_id: str    # уникальный ключ: "telegram_channel", "vk", "ok", ...
    platform_name: str  # отображаемое название: "Telegram канал", "ВКонтакте", ...
    icon: str = ""      # эмодзи для UI

    @abstractmethod
    def is_configured(self) -> bool:
        """Возвращает True если все нужные env-переменные заполнены."""
        pass

    @abstractmethod
    def publish(self, text: str, image_path: Optional[str] = None, **kwargs) -> PublishResult:
        pass
