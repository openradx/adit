import psycopg
from django import db


def ping_db():
    with db.connection.cursor() as cursor:
        cursor.execute("SELECT 1")


# Django ORM does not work well with long running tasks in production as the
# database server closes the connection, but Django still tries to use the closed
# connection and then throws an error. This helper function does ensure that the
# connection is established and if not closes all old connections that new ones
# can be created.
# References:
# <https://code.djangoproject.com/ticket/24810>
# <https://github.com/jdelic/django-dbconn-retry> No support for psycopg v3
# <https://tryolabs.com/blog/2014/02/12/long-running-process-and-django-orm>
# <https://docs.djangoproject.com/en/4.2/ref/databases/#caveats>
def ensure_db_connection():
    try:
        ping_db()
    except (db.utils.OperationalError, psycopg.OperationalError):
        db.close_old_connections()
        ping_db()
