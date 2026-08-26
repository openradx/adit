# Backups

Database backups use the [django-dbbackup](https://django-dbbackup.readthedocs.io/) app.

**Periodic backups**: The shared `backup_db` task (`adit_radis_shared.common.tasks`) runs `dbbackup --clean` on the `default` worker at `BACKUP_CRON` (default `0 3 * * *`, i.e. every night at 3 am). Set `BACKUP_ENABLED=false` in `.env` to turn the task into a no-op (the test settings do this). `--clean` keeps the newest `DBBACKUP_CLEANUP_KEEP = 30` backups (`adit/settings/base.py`) and deletes older ones.

**Location**: Backups are written to `/backups` inside the containers, which is a bind mount of the host directory `BACKUP_DIR` from `.env` (default `./.docker-data/backups`, see `docker-compose.base.yml`).

**Manual backup and restore**:

```terminal
uv run cli db-backup    # runs dbbackup in the web container
uv run cli db-restore   # runs dbrestore in the web container
```
