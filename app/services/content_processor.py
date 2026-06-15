import ipaddress
import socket
from dataclasses import dataclass, field
from typing import List, Optional
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup


@dataclass
class NormalizedContent:
    text: str
    images: List[str] = field(default_factory=list)
    source_url: Optional[str] = None
    content_type: str = "text"


_ALLOWED_SCHEMES = {"http", "https"}
_BLOCKED_HOSTS = {
    "localhost", "127.0.0.1", "0.0.0.0", "::1",
    "169.254.169.254",           # AWS/GCP/Azure metadata
    "metadata.google.internal",  # GCP metadata
    "app", "db", "nginx",        # docker service names
}


def _validate_url(url: str) -> None:
    try:
        parsed = urlparse(url)
    except Exception:
        raise ValueError("Некорректный URL")

    if parsed.scheme not in _ALLOWED_SCHEMES:
        raise ValueError(f"Недопустимая схема URL: {parsed.scheme}")

    host = (parsed.hostname or "").lower()
    if not host:
        raise ValueError("URL не содержит хост")

    if host in _BLOCKED_HOSTS:
        raise ValueError("Недопустимый хост")

    # Резолвим DNS и проверяем IP
    try:
        ip = ipaddress.ip_address(host)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            raise ValueError("Приватный или зарезервированный IP недопустим")
    except ValueError as e:
        if any(w in str(e) for w in ("Приватный", "Недопустимый")):
            raise
        # host — доменное имя, резолвим
        try:
            resolved_ip = socket.gethostbyname(host)
            ip = ipaddress.ip_address(resolved_ip)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                raise ValueError("URL ведёт на приватный IP")
        except socket.gaierror:
            raise ValueError("Не удалось определить хост")


def process_url(url: str) -> NormalizedContent:
    _validate_url(url)
    resp = requests.get(
        url,
        headers={"User-Agent": "Mozilla/5.0 (compatible; DomikBot/1.0)"},
        timeout=15,
        allow_redirects=True,
    )
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding

    soup = BeautifulSoup(resp.text, "html.parser")

    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()

    title = soup.find("title")
    title_text = title.get_text(strip=True) if title else ""

    meta = soup.find("meta", attrs={"name": "description"})
    description = meta.get("content", "").strip() if meta else ""

    body_text = soup.get_text(separator="\n", strip=True)
    body_text = "\n".join(line for line in body_text.splitlines() if line.strip())
    body_text = body_text[:3000]

    parts = []
    if title_text:
        parts.append(f"Заголовок: {title_text}")
    if description:
        parts.append(f"Описание: {description}")
    parts.append(f"Текст страницы:\n{body_text}")

    return NormalizedContent(
        text="\n\n".join(parts),
        source_url=url,
        content_type="url",
    )


def process_text(text: str, images: List[str] = None) -> NormalizedContent:
    return NormalizedContent(
        text=text.strip(),
        images=images or [],
        content_type="text",
    )
