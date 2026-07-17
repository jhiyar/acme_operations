#!/bin/sh
set -e
python manage.py migrate --noinput
python manage.py seed_data
exec python manage.py runserver 0.0.0.0:8000 --noreload
