"""
Реестр паблишеров.

Чтобы добавить новую платформу (например OK.ru):
  1. Создать app/services/publishers/ok.py с классом OKPublisher(BasePublisher)
  2. Импортировать здесь и добавить в список PUBLISHERS
  3. Добавить нужные переменные в .env
  — больше никаких изменений в коде не требуется.
"""
from app.services.publishers.telegram import (
    TelegramChannelPublisher,
    TelegramGroupPublisher,
    TelegramStoriesPublisher,
)
from app.services.publishers.vk import VKPublisher
from app.services.publishers.max_publisher import MAXPublisher

PUBLISHERS = [
    TelegramChannelPublisher(),
    TelegramGroupPublisher(),
    TelegramStoriesPublisher(),
    VKPublisher(),
    MAXPublisher(),
    # OKPublisher(),          # подключить в Sprint 5
    # YandexMapsPublisher(),  # подключить в Sprint 5
    # YandexZenPublisher(),   # подключить в Sprint 5
    # InstagramPublisher(),   # подключить в Sprint 7
]


def get_all_publishers():
    return PUBLISHERS


def get_active_publishers():
    """Только те, у которых заполнены все env-переменные."""
    return [p for p in PUBLISHERS if p.is_configured()]


def get_publisher(platform_id: str):
    return next((p for p in PUBLISHERS if p.platform_id == platform_id), None)
