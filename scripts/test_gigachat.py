"""
Проверка подключения к GigaChat API.
Запустить: py -3.13 scripts/test_gigachat.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import uuid
import urllib3
urllib3.disable_warnings()

from app.config import settings

if not settings.GIGACHAT_CLIENT_ID or not settings.GIGACHAT_CLIENT_SECRET:
    print("❌ GIGACHAT_CLIENT_ID или GIGACHAT_CLIENT_SECRET не заполнены в .env")
    sys.exit(1)

print(f"CLIENT_ID: {settings.GIGACHAT_CLIENT_ID[:8]}...")
print(f"SCOPE: {settings.GIGACHAT_SCOPE}")
print()

import requests

print("1. Получаем OAuth-токен...")
try:
    resp = requests.post(
        "https://ngw.devices.sberbank.ru:9443/api/v2/oauth",
        headers={
            "Authorization": f"Basic {settings.GIGACHAT_CLIENT_SECRET}",
            "RqUID": str(uuid.uuid4()),
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={"scope": settings.GIGACHAT_SCOPE},
        verify=False,
        timeout=15,
    )
    print(f"   HTTP {resp.status_code}")
    data = resp.json()
    if "access_token" in data:
        token = data["access_token"]
        print(f"   Токен: {token[:30]}...")
    else:
        print(f"   ❌ Ответ: {data}")
        sys.exit(1)
except requests.exceptions.ConnectTimeout:
    print("   ❌ Таймаут подключения — сервер недоступен с этой машины")
    sys.exit(1)
except requests.exceptions.ConnectionError as e:
    print(f"   ❌ Ошибка соединения: {e}")
    sys.exit(1)
except Exception as e:
    print(f"   ❌ {e}")
    sys.exit(1)

print()
print("2. Отправляем тестовый запрос к GigaChat...")
try:
    resp = requests.post(
        "https://gigachat.devices.sberbank.ru/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json={
            "model": "GigaChat",
            "messages": [
                {"role": "user", "content": "Напиши одно предложение про детский сад."},
            ],
            "max_tokens": 100,
        },
        verify=False,
        timeout=30,
    )
    print(f"   HTTP {resp.status_code}")
    result = resp.json()
    if "choices" in result:
        text = result["choices"][0]["message"]["content"]
        print(f"   ✅ Ответ: {text}")
    else:
        print(f"   ❌ {result}")
except requests.exceptions.ConnectTimeout:
    print("   ❌ Таймаут — API недоступен")
except Exception as e:
    print(f"   ❌ {e}")
