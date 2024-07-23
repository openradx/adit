from pathlib import Path

from adit_radis_shared import invoke_tasks
from adit_radis_shared.invoke_tasks import (  # noqa: F401
    backup_db,
    bump_version,
    compose_down,
    compose_up,
    format,
    init_workspace,
    lint,
    reset_dev,
    restore_db,
    show_outdated,
    stack_deploy,
    stack_rm,
    test,
    try_github_actions,
    upgrade_adit_radis_shared,
    upgrade_postgresql,
    web_shell,
)
from invoke.context import Context
from invoke.tasks import task

invoke_tasks.PROJECT_NAME = "adit"
invoke_tasks.PROJECT_DIR = Path(__file__).resolve().parent


@task
def reset_orthancs(ctx: Context, env: invoke_tasks.Environments = "dev"):
    """Reset Orthancs"""
    cmd = f"{invoke_tasks.build_compose_cmd(env)} exec web python manage.py reset_orthancs"
    ctx.run(cmd, pty=True)
