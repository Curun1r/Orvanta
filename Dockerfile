FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/src

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends gettext \
    && rm -rf /var/lib/apt/lists/*

# psycopg-binary не потребує компілятора — build-essential і libpq-dev не потрібні
COPY requirements.txt /app/

RUN pip install --upgrade pip \
    && pip install -r requirements.txt

COPY . /app/

# Збираємо статичні файли під час білду образу.
# SECRET_KEY потрібен Django навіть для collectstatic — використовуємо тимчасове значення.
RUN SECRET_KEY=build-placeholder python src/manage.py compilemessages --ignore=venv --ignore=.venv \
    && SECRET_KEY=build-placeholder DATABASE_URL=sqlite:///tmp/build.db \
    python src/manage.py collectstatic --noinput

EXPOSE 8000

# Production: gunicorn замість dev-сервера
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "120"]
