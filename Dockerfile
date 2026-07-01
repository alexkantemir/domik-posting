FROM python:3.13-slim@sha256:2b7445fb71ca9cb15e9aab053fe8cb3162796f8e1d92ada12a49c766a811bc1e

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    ffmpeg \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt psycopg2-binary

# Непривилегированный пользователь
RUN groupadd -r appuser && useradd -r -g appuser -d /app appuser
RUN mkdir -p uploads static && chown -R appuser:appuser /app

COPY --chown=appuser:appuser . .

# Российские доверенные сертификаты (Sub CA + Root CA Минцифры) для GigaChat / Сбербанк.
# Bundle извлечён из реальной TLS-цепочки ngw.devices.sberbank.ru:9443, проверен ssl.create_default_context.
# Патчим certifi ПОСЛЕ всех COPY, под root — гарантирует что патч не откатится.
RUN python -c "\
import certifi; \
bundle = open('/app/russian_trusted_ca_bundle.crt', 'rb').read(); \
f = open(certifi.where(), 'ab'); \
f.write(b'\n'); \
f.write(bundle); \
f.close(); \
print('Patched certifi, bundle size:', len(bundle)); \
import ssl; ctx = ssl.create_default_context(cafile=certifi.where()); \
print('certifi verify OK, total certs:', len(ctx.get_ca_certs()))"

USER appuser

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
