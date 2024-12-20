# Backups

For database backups django-dbbackup app is used. The backups are done every night at 3 am by a periodic task using the dbbackup management command and stored in the `backups` directory which is mounted as a volume. The dbbackup command can also be called manually with `invoke backup_db`.
