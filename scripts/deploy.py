"""
Деплой проекта на VPS через SSH (paramiko).
Запуск: py -3.13 scripts/deploy.py --host IP --user root --password PASS
"""
import argparse
import os
import secrets
import sys
import time

try:
    import paramiko
except ImportError:
    print("Установи paramiko: py -3.13 -m pip install paramiko")
    sys.exit(1)

PROJECT_DIR = "/opt/domik-posting"
DOMAIN = "post.domik-l.spb.ru"
EMAIL = "admin@domik-l.spb.ru"

LOCAL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

UPLOAD_FILES = [
    "Dockerfile",
    "docker-compose.yml",
    "requirements.txt",
    "nginx/default.conf",
    "nginx/default-ssl.conf",
    "app/__init__.py",
    "app/main.py",
    "app/config.py",
    "app/database.py",
    "app/models.py",
    "app/auth.py",
    "app/routers/__init__.py",
    "app/routers/auth.py",
    "app/routers/dashboard.py",
    "app/routers/content.py",
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
    "app/templates/base.html",
    "app/templates/login.html",
    "app/templates/dashboard.html",
    "app/templates/content_new.html",
    "app/templates/content_preview.html",
    "scripts/init_db.py",
]


def run(ssh, cmd, check=True):
    print(f"  $ {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, get_pty=True)
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


def upload(sftp, local_rel, remote_path):
    local_path = os.path.join(LOCAL_ROOT, local_rel.replace("/", os.sep))
    if not os.path.exists(local_path):
        print(f"  ⚠️  Пропускаем (нет локально): {local_rel}")
        return
    remote_dir = os.path.dirname(remote_path)
    try:
        sftp.makedirs(remote_dir)
    except Exception:
        pass
    sftp.put(local_path, remote_path)
    print(f"  ↑ {local_rel}")


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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", required=True)
    parser.add_argument("--user", default="root")
    parser.add_argument("--password", required=True)
    parser.add_argument("--db-password", default=None)
    parser.add_argument("--docker-user", default=None, help="Docker Hub username")
    parser.add_argument("--docker-password", default=None, help="Docker Hub password/token")
    parser.add_argument("--skip-docker-install", action="store_true", help="Skip Docker installation (if already installed)")
    args = parser.parse_args()

    db_password = args.db_password or secrets.token_urlsafe(16)

    print(f"\n🚀 Деплой на {args.host}")
    print(f"   Директория: {PROJECT_DIR}")
    print(f"   Домен: {DOMAIN}\n")

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(args.host, username=args.user, password=args.password, timeout=30)
    print("✅ SSH подключение установлено\n")

    # 1. Установка Docker
    if args.skip_docker_install:
        print("1. Docker уже установлен, пропускаем...\n")
    else:
        print("1. Устанавливаем Docker...")
        run(ssh, "apt-get update -qq")
        run(ssh, "apt-get install -y -qq ca-certificates curl gnupg")
        run(ssh, "install -m 0755 -d /etc/apt/keyrings")
        run(ssh, "curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg --yes")
        run(ssh, 'echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" > /etc/apt/sources.list.d/docker.list')
        run(ssh, "apt-get update -qq")
        run(ssh, "apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-compose-plugin")
        run(ssh, "systemctl enable docker --now")
        print("✅ Docker установлен\n")

    # 2. Создаём директории
    print("2. Создаём директории...")
    for d in [PROJECT_DIR, f"{PROJECT_DIR}/nginx", f"{PROJECT_DIR}/app/routers",
              f"{PROJECT_DIR}/app/services/publishers", f"{PROJECT_DIR}/app/templates",
              f"{PROJECT_DIR}/scripts", f"{PROJECT_DIR}/uploads"]:
        run(ssh, f"mkdir -p {d}")
    print("✅ Директории созданы\n")

    # 3. Загружаем файлы
    print("3. Загружаем файлы...")
    sftp = ssh.open_sftp()
    sftp.makedirs = lambda p: makedirs_recursive(sftp, p)

    for rel_path in UPLOAD_FILES:
        remote = f"{PROJECT_DIR}/{rel_path}"
        upload(sftp, rel_path, remote)

    sftp.close()
    print("✅ Файлы загружены\n")

    # 4. Читаем локальный .env и создаём production .env
    print("4. Создаём .env на сервере...")
    local_env_path = os.path.join(LOCAL_ROOT, ".env")
    env_vars = {}
    if os.path.exists(local_env_path):
        with open(local_env_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    env_vars[k.strip()] = v.strip()

    env_vars["DATABASE_URL"] = f"postgresql://domik:{db_password}@db:5432/domik"
    env_vars["DB_PASSWORD"] = db_password
    env_vars["SECRET_KEY"] = env_vars.get("SECRET_KEY") or secrets.token_urlsafe(32)

    env_content = "\n".join(f"{k}={v}" for k, v in env_vars.items())
    run(ssh, f"cat > {PROJECT_DIR}/.env << 'ENVEOF'\n{env_content}\nENVEOF")
    run(ssh, f"chmod 600 {PROJECT_DIR}/.env")
    print(f"   DB_PASSWORD: {db_password}")
    print("✅ .env создан\n")

    # 5. Запускаем контейнеры
    print("5. Запускаем Docker Compose...")
    if args.docker_user and args.docker_password:
        print(f"   Логинимся в Docker Hub как {args.docker_user}...")
        run(ssh, f"echo '{args.docker_password}' | docker login -u '{args.docker_user}' --password-stdin")
    run(ssh, f"cd {PROJECT_DIR} && docker compose up -d --build")
    print("   Ждём старта БД...")
    time.sleep(10)
    print("✅ Контейнеры запущены\n")

    # 6. Инициализируем БД
    print("6. Инициализируем БД...")
    run(ssh, f"cd {PROJECT_DIR} && docker compose exec -T app python scripts/init_db.py")
    print("✅ БД инициализирована\n")

    # 7. SSL-сертификат
    print("7. Получаем SSL-сертификат...")
    run(ssh, f"cd {PROJECT_DIR} && docker compose run --rm certbot certonly --webroot "
             f"--webroot-path /var/www/certbot --email {EMAIL} --agree-tos --no-eff-email "
             f"-d {DOMAIN}", check=False)

    # Проверяем что сертификат есть
    code_check = run(ssh, f"test -f /var/lib/docker/volumes/domik-posting_certbot_certs/_data/live/{DOMAIN}/fullchain.pem && echo OK || echo FAIL", check=False)
    if "OK" in code_check:
        print("   Переключаем на HTTPS конфиг...")
        run(ssh, f"cp {PROJECT_DIR}/nginx/default-ssl.conf {PROJECT_DIR}/nginx/default.conf")
        run(ssh, f"cd {PROJECT_DIR} && docker compose restart nginx")
        print("✅ SSL настроен\n")
    else:
        print("⚠️  SSL не получен (DNS ещё не применился?), работаем по HTTP пока\n")

    print("=" * 50)
    print(f"🎉 Деплой завершён!")
    print(f"   URL: http://{DOMAIN}")
    print(f"   Логин: admin@domik-l.spb.ru")
    print(f"   Пароль: domik2024  (смените!)")
    print(f"   DB пароль: {db_password}  (сохраните!)")
    print("=" * 50)

    ssh.close()


if __name__ == "__main__":
    main()
