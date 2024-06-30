from pathlib import Path
from typing import Literal

from adit_radis_shared.invoke_tasks import Environments, InvokeTasks
from invoke.context import Context
from invoke.tasks import task

Profile = Literal["full", "web"]

stack_name_dev = "adit_dev"
stack_name_prod = "adit_prod"

postgres_dev_volume = f"{stack_name_dev}_postgres_data"
postgres_prod_volume = f"{stack_name_prod}_postgres_data"

project_dir = Path(__file__).resolve().parent
compose_dir = project_dir / "compose"

compose_file_base = compose_dir / "docker-compose.base.yml"
compose_file_dev = compose_dir / "docker-compose.dev.yml"
compose_file_prod = compose_dir / "docker-compose.prod.yml"

invoke_tasks = InvokeTasks("adit", project_dir)

###
# Shared tasks
###


@task
def compose_up(
    ctx: Context,
    env: Environments = "dev",
    no_build: bool = False,
    profile: Profile = "full",
):
    """Start containers in specified environment"""
    invoke_tasks.compose_up(ctx, env=env, no_build=no_build, profile=profile)


@task
def compose_down(
    ctx: Context,
    env: Environments = "dev",
    profile: Profile = "full",
    cleanup: bool = False,
):
    """Stop containers in specified environment"""
    invoke_tasks.compose_down(ctx, env=env, profile=profile, cleanup=cleanup)


@task
def stack_deploy(ctx: Context, env: Environments = "prod", build: bool = False):
    """Deploy the stack to Docker Swarm (prod by default!). Optional build it before."""
    invoke_tasks.stack_deploy(ctx, env=env, build=build)


@task
def stack_rm(ctx: Context, env: Environments = "prod"):
    """Remove the stack from Docker Swarm (prod by default!)."""
    invoke_tasks.stack_rm(ctx, env=env)


@task
def format(ctx: Context):
    """Format the source code with ruff and djlint"""
    invoke_tasks.format(ctx)


@task
def lint(ctx: Context):
    """Lint the source code (ruff, djlint, pyright)"""
    invoke_tasks.lint(ctx)


@task
def test(
    ctx: Context,
    path: str | None = None,
    cov: bool | str = False,
    html: bool = False,
    keyword: str | None = None,
    mark: str | None = None,
    stdout: bool = False,
    failfast: bool = False,
):
    """Run the test suite"""
    invoke_tasks.test(
        ctx,
        path=path,
        cov=cov,
        html=html,
        keyword=keyword,
        mark=mark,
        stdout=stdout,
        failfast=failfast,
    )


@task
def reset_dev(ctx: Context):
    """Reset dev container environment"""
    invoke_tasks.reset_dev(ctx)


@task
def adit_web_shell(ctx: Context, env: Environments = "dev"):
    """Open Python shell in ADIT web container of specified environment"""
    cmd = f"{invoke_tasks._build_compose_cmd(env)} exec web python manage.py shell_plus"
    ctx.run(cmd, pty=True)


@task
def init_workspace(ctx: Context):
    """Initialize workspace for Github Codespaces or Gitpod"""
    invoke_tasks.init_workspace(ctx)


@task
def show_outdated(ctx: Context):
    """Show outdated dependencies"""
    invoke_tasks.show_outdated(ctx)


@task
def try_github_actions(ctx: Context):
    """Try Github Actions locally using Act"""
    invoke_tasks.try_github_actions(ctx)


@task
def backup_db(ctx: Context, env: Environments = "prod"):
    """Backup database

    For backup location see setting DBBACKUP_STORAGE_OPTIONS
    For possible commands see:
    https://django-dbbackup.readthedocs.io/en/master/commands.html
    """
    invoke_tasks.backup_db(ctx, env)


@task
def restore_db(ctx: Context, env: Environments = "prod"):
    """Restore database from backup"""
    invoke_tasks.restore_db(ctx, env)


@task
def bump_version(ctx: Context, rule: Literal["patch", "minor", "major"]):
    """Bump version, create a tag, commit and push to GitHub"""
    invoke_tasks.bump_version(ctx, rule)


@task
def upgrade_postgresql(ctx: Context, env: Environments = "dev", version: str = "latest"):
    invoke_tasks.upgrade_postgresql(ctx, env, version)


@task
def upgrade_adit_radis_shared(ctx: Context, version: str | None = None):
    invoke_tasks.upgrade_adit_radis_shared(ctx, version)


###
# Custom tasks
###


@task
def reset_orthancs(ctx: Context, env: Environments = "dev"):
    """Reset Orthancs"""
    cmd = f"{invoke_tasks._build_compose_cmd(env)} exec web python manage.py reset_orthancs"
    ctx.run(cmd, pty=True)
