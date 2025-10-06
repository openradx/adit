#! /usr/bin/env python3
# PYTHON_ARGCOMPLETE_OK
import argparse

from adit_radis_shared.cli import helper as cli_helper
from adit_radis_shared.cli import parsers
from adit_radis_shared.cli.setup import setup_root_parser


def populate_orthancs(reset: bool, **kwargs):
    helper = cli_helper.CommandHelper()

    cmd = f"{helper.build_compose_cmd()} exec web python manage.py populate_orthancs"
    if reset:
        cmd += " --reset"

    helper.execute_cmd(cmd)


def main():
    root_parser = argparse.ArgumentParser()
    subparsers = root_parser.add_subparsers(dest="command")

    parsers.register_compose_build(subparsers)
    parsers.register_compose_watch(subparsers)
    parsers.register_compose_up(subparsers)
    parsers.register_compose_down(subparsers)
    parsers.register_compose_pull(subparsers)
    parsers.register_db_backup(subparsers)
    parsers.register_db_restore(subparsers)
    parsers.register_format_code(subparsers)
    parsers.register_generate_auth_token(subparsers)
    parsers.register_generate_certificate_chain(subparsers)
    parsers.register_generate_certificate_files(subparsers)
    parsers.register_generate_django_secret_key(subparsers)
    parsers.register_generate_secure_password(subparsers)
    parsers.register_init_workspace(subparsers)
    parsers.register_lint(subparsers)
    parsers.register_randomize_env_secrets(subparsers)
    parsers.register_shell(subparsers)
    parsers.register_show_outdated(subparsers)
    parsers.register_stack_deploy(subparsers)
    parsers.register_stack_rm(subparsers)
    parsers.register_test(subparsers)
    parsers.register_try_github_actions(subparsers)
    parsers.register_upgrade_postgres_volume(subparsers)

    info = "Populate Orthancs with example DICOMs"
    parser = subparsers.add_parser("populate-orthancs", help=info, description=info)
    parser.add_argument(
        "--reset", action="store_true", help="Fully reset the Orthancs and and then repopulate"
    )
    parser.set_defaults(func=populate_orthancs)

    setup_root_parser(root_parser)


if __name__ == "__main__":
    main()
