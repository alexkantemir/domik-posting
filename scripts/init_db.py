"""
Создаёт таблицы БД и двух тестовых пользователей.
Запустить один раз: python scripts/init_db.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import Base, engine, SessionLocal
from app.models import User
from app.auth import hash_password

Base.metadata.create_all(bind=engine)

db = SessionLocal()

users = [
    {
        "name": "Администратор",
        "email": "admin@domik-l.spb.ru",
        "password": "domik2024",
        "role": "admin",
    },
    {
        "name": "Редактор",
        "email": "editor@domik-l.spb.ru",
        "password": "domik2024",
        "role": "editor",
    },
]

for u in users:
    exists = db.query(User).filter(User.email == u["email"]).first()
    if not exists:
        db.add(User(
            name=u["name"],
            email=u["email"],
            password_hash=hash_password(u["password"]),
            role=u["role"],
        ))
        print(f"  Создан: {u['email']}  пароль: {u['password']}  роль: {u['role']}")
    else:
        print(f"  Уже существует: {u['email']}")

db.commit()
db.close()

print("\n✅ БД готова.")
print("⚠️  Смените пароли после первого входа!")
