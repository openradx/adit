from adit_radis_shared.common.management.base.hard_reset_migrations import (
    HardResetMigrationsCommand,
)


class Command(HardResetMigrationsCommand):
    project = "adit"
