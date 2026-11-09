#!/bin/sh
set -e

python src/manage.py compilemessages --ignore=venv --ignore=.venv

echo "=== Step 1: collectstatic ==="
python src/manage.py collectstatic --noinput

echo "=== Step 2: migrate ==="
python src/manage.py migrate --noinput

echo "=== Step 3: starting gunicorn ==="
exec gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers 1 --timeout 120
