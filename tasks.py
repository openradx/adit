from pathlib import Path

from adit_radis_shared import invoke_tasks
from adit_radis_shared.invoke_tasks import (  # noqa: F401
    Utility,
    backup_db,
    compose_down,
    compose_up,
    format,
    generate_auth_token,
    generate_certificate_files,
    generate_django_secret_key,
    generate_secure_password,
    init_workspace,
    lint,
    randomize_env_secrets,
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
def populate_orthancs(ctx: Context, reset: bool = False):
    """Populate Orthancs with example DICOMs"""
    cmd = f"{Utility.build_compose_cmd()} exec web python manage.py populate_orthancs"
    if reset:
        cmd += " --reset"

    ctx.run(cmd, pty=True)
