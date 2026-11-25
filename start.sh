#!/bin/sh
# Production start script (used by Railway, see railway.json).
set -e

python manage.py migrate --noinput
python manage.py collectstatic --noinput
# Fills the database with demo data on first boot; skips itself when data already exists.
python manage.py seed_data

exec gunicorn clinic_project.wsgi:application \
    --bind "0.0.0.0:${PORT:-8000}" \
    --workers "${WEB_CONCURRENCY:-2}" \
    --timeout 60 \
    --access-logfile - \
    --error-logfile -
