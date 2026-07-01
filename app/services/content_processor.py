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
_BLOCKED_CIDRS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("100.64.0.0/10"),  # CGNAT
    ipaddress.ip_network("169.254.0.0/16"),  # link-local
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),        # IPv6 ULA
]


def _is_blocked_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return (
        ip.is_private or ip.is_loopback or ip.is_link_local
        or ip.is_reserved or ip.is_multicast
        or any(ip in net for net in _BLOCKED_CIDRS)
    )


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

    # Резолвим все A/AAAA записи и проверяем каждый IP (защита от DNS rebinding)
    try:
        ip = ipaddress.ip_address(host)
        if _is_blocked_ip(ip):
            raise ValueError("Приватный или зарезервированный IP недопустим")
    except ValueError as e:
        if "Приватный" in str(e) or "Недопустимый" in str(e):
            raise
        # host — доменное имя, резолвим все адреса
        try:
            addr_infos = socket.getaddrinfo(host, None)
            for info in addr_infos:
                ip = ipaddress.ip_address(info[4][0])
                if _is_blocked_ip(ip):
                    raise ValueError("URL ведёт на приватный IP")
        except socket.gaierror:
            raise ValueError("Не удалось определить хост")


def _safe_get(url: str) -> requests.Response:
    """Follow redirects only after validating each redirect target against SSRF rules."""
    headers = {"User-Agent": "Mozilla/5.0 (compatible; DomikBot/1.0)"}
    max_redirects = 5
    for _ in range(max_redirects + 1):
        resp = requests.get(url, headers=headers, timeout=15, allow_redirects=False)
        if resp.status_code in (301, 302, 303, 307, 308):
            location = resp.headers.get("Location", "")
            if not location:
                break
            # Resolve relative redirects
            if location.startswith("/"):
                parsed = urlparse(url)
                location = f"{parsed.scheme}://{parsed.netloc}{location}"
            _validate_url(location)
            url = location
            continue
        return resp
    return resp


def process_url(url: str) -> NormalizedContent:
    _validate_url(url)
    resp = _safe_get(url)
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
