"""
Скрипт для нахождения chat_id группы MAX.

Запуск:
    py -3 scripts/get_max_chat_id.py --token YOUR_BOT_TOKEN

Что делает:
  1. Проверяет токен (GET /me)
  2. Регистрирует временный webhook через MAX API
  3. Ждёт первого сообщения из группы (отправь любое в группу вручную)
  4. Выводит chat_id найденного чата

Зависимости: requests, fastapi, uvicorn
"""

import argparse
import threading
import time
import requests
import uvicorn
from fastapi import FastAPI, Request

MAX_API = "https://platform-api.max.ru"
found_chat_ids: list[dict] = []

app = FastAPI()


@app.post("/max-webhook")
async def webhook(request: Request):
    body = await request.json()
    for update in body.get("updates", [body]):
        chat = (
            update.get("message", {}).get("recipient")
            or update.get("chat_title_changed", {}).get("chat")
            or {}
        )
        if not chat:
            # Try direct chat_id
            chat_id = (
                update.get("message", {}).get("recipient", {}).get("chat_id")
                or update.get("chat_id")
            )
            title = update.get("title", "")
        else:
            chat_id = chat.get("chat_id")
            title = chat.get("title", "")
        if chat_id and {"chat_id": chat_id, "title": title} not in found_chat_ids:
            found_chat_ids.append({"chat_id": chat_id, "title": title})
            print(f"\n✅  НАЙДЕНО: chat_id={chat_id}  title='{title}'")
            print(f"    Добавь в .env:  MAX_CHAT_ID={chat_id}\n")
    return {"ok": True}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--token", required=True, help="MAX bot token")
    parser.add_argument("--webhook-url", default="",
                        help="Публичный URL где запущен этот скрипт (например ngrok). "
                             "Если не указан — только проверяем токен.")
    args = parser.parse_args()

    token = args.token
    headers = {"Authorization": token, "Content-Type": "application/json"}

    # 1. Проверяем токен
    resp = requests.get(f"{MAX_API}/me", headers=headers, timeout=10)
    me = resp.json()
    if resp.status_code != 200:
        print(f"❌  Ошибка токена: {me}")
        return
    print(f"✅  Бот: {me.get('name')} (id={me.get('user_id')})")

    if not args.webhook_url:
        print("\nТокен валиден!")
        print("Для поиска chat_id используй --webhook-url с публичным URL (ngrok и т.п.),")
        print("или найди chat_id вручную — он есть в URL группы на max.ru.")
        return

    webhook_url = args.webhook_url.rstrip("/") + "/max-webhook"

    # 2. Регистрируем webhook
    resp = requests.post(
        f"{MAX_API}/subscriptions",
        headers=headers,
        json={"url": webhook_url, "update_types": ["message_created", "bot_added"]},
        timeout=10,
    )
    print(f"\nРегистрация webhook: {resp.status_code} {resp.text}")

    # 3. Запускаем сервер
    print(f"\nСервер запущен на 0.0.0.0:8765")
    print("Отправь любое сообщение в своей группе MAX — я поймаю chat_id.")
    print("Нажми Ctrl+C чтобы остановить.\n")

    def run():
        uvicorn.run(app, host="0.0.0.0", port=8765, log_level="warning")

    t = threading.Thread(target=run, daemon=True)
    t.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass

    # 4. Удаляем webhook
    try:
        resp = requests.delete(f"{MAX_API}/subscriptions", headers=headers, timeout=10)
        print(f"\nWebhook удалён: {resp.status_code}")
    except Exception:
        pass

    if found_chat_ids:
        print("\nНайденные чаты:")
        for c in found_chat_ids:
            print(f"  chat_id={c['chat_id']}  title='{c['title']}'")
    else:
        print("\nСообщений не получено.")


if __name__ == "__main__":
    main()
