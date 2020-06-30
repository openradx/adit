python manage.py reset_db --noinput
python manage.py migrate
python manage.py shell < populate_db.py