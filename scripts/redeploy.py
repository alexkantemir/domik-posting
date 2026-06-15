"""
Быстрый редеплой: загружает изменённые файлы и пересобирает контейнер app.
Запуск: py -3.13 scripts/redeploy.py --host IP --user root --password PASS
"""
import argparse
import os
import sys

try:
    import paramiko
except ImportError:
    print("Установи paramiko: py -3.13 -m pip install paramiko")
    sys.exit(1)

PROJECT_DIR = "/opt/domik-posting"
LOCAL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

UPLOAD_FILES = [
    "app/__init__.py",
    "app/main.py",
    "app/jinja.py",
    "app/csrf.py",
    "app/config.py",
    "app/database.py",
    "app/models.py",
    "app/auth.py",
    "app/routers/__init__.py",
    "app/routers/auth.py",
    "app/routers/dashboard.py",
    "app/routers/content.py",
    "app/routers/admin.py",
    "app/services/__init__.py",
    "app/services/gigachat.py",
    "app/services/prompts.py",
    "app/services/content_processor.py",
    "app/services/post_generator.py",
    "app/services/publishers/__init__.py",
    "app/services/publishers/base.py",
    "app/services/publishers/telegram.py",
    "app/services/publishers/vk.py",
    "app/services/publishers/registry.py",
    "app/scheduler.py",
    "app/templates/base.html",
    "app/templates/login.html",
    "app/templates/dashboard.html",
    "app/templates/content_new.html",
    "app/templates/content_preview.html",
    "app/templates/approve.html",
    "app/templates/posts_list.html",
    "app/templates/admin_users.html",
    "app/templates/admin_user_form.html",
    "app/templates/profile.html",
    "scripts/init_db.py",
    "requirements.txt",
]


def run(ssh, cmd, check=True, timeout=300):
    print(f"  $ {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, get_pty=True, timeout=timeout)
    out = stdout.read().decode(errors="replace").strip()
    err = stderr.read().decode(errors="replace").strip()
    code = stdout.channel.recv_exit_status()
    if out:
        print(f"    {out[-500:]}")
    if err and code != 0:
        print(f"    ERR: {err[-300:]}")
    if check and code != 0:
        raise RuntimeError(f"Команда завершилась с кодом {code}: {cmd}")
    return out


def makedirs_recursive(sftp, path):
    parts = path.split("/")
    current = ""
    for part in parts:
        if not part:
            continue
        current += "/" + part
        try:
            sftp.mkdir(current)
        except IOError:
            pass


def upload(sftp, local_rel, remote_path):
    local_path = os.path.join(LOCAL_ROOT, local_rel.replace("/", os.sep))
    if not os.path.exists(local_path):
        print(f"  ⚠️  Пропускаем (нет локально): {local_rel}")
        return
    makedirs_recursive(sftp, os.path.dirname(remote_path))
    sftp.put(local_path, remote_path)
    print(f"  ↑ {local_rel}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", required=True)
    parser.add_argument("--user", default="root")
    parser.add_argument("--password", required=True)
    args = parser.parse_args()

    print(f"\n🔄 Редеплой на {args.host}\n")

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(args.host, username=args.user, password=args.password, timeout=30)
    print("✅ SSH подключение установлено\n")

    print("1. Загружаем файлы...")
    sftp = ssh.open_sftp()
    for rel_path in UPLOAD_FILES:
        upload(sftp, rel_path, f"{PROJECT_DIR}/{rel_path}")
    sftp.close()
    print("✅ Файлы загружены\n")

    print("2. Пересобираем и перезапускаем app...")
    run(ssh, f"cd {PROJECT_DIR} && docker compose up -d --build --force-recreate app", timeout=300)
    print("✅ Готово\n")

    status = run(ssh, "docker ps --filter name=domik-posting-app-1 --format '{{.Status}}'", check=False)
    print(f"   Статус контейнера: {status}")

    ssh.close()
    print("\n🎉 Редеплой завершён!")


if __name__ == "__main__":
    main()
