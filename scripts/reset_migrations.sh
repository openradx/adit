#!/usr/bin/env bash

# TODO delete if not needed anymore cause of reset_migrations command

find . -path "./adit/*/migrations/*.py" -not -name "__init__.py" -delete
find . -path "./adit/*/migrations/*.pyc" -delete
python manage.py reset_db --noinput
python manage.py makemigrations
python manage.py migrate