source "$(dirname "$0")/common.sh"

eval $COMPOSE_COMMAND_DEV exec web python manage.py reset_orthancs
eval $COMPOSE_COMMAND_DEV exec web python manage.py flush --noinput
eval $COMPOSE_COMMAND_DEV exec web python manage.py populate_dev_db
