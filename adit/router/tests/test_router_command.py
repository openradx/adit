import io

import pytest
from django.db import ProgrammingError

from adit.router.factories import RouterSenderFactory
from adit.router.management.commands import router as router_command
from adit.router.utils import spool
from adit.router.utils.intake import IntakeConfig, RouterStoreHandler, build_router_scp


@pytest.fixture
def command() -> router_command.Command:
    return router_command.Command(stdout=io.StringIO())


@pytest.fixture
def handler_and_scp(tmp_path):
    spool.ensure_spool_dirs(tmp_path)
    handler = RouterStoreHandler(tmp_path, min_free_bytes=0)
    scp = build_router_scp(tmp_path, handler, ae_title="ROUTERTEST", host="127.0.0.1", port=11112)
    return handler, scp


def test_router_without_ae_title_is_disabled(command, settings):
    settings.ROUTER_AE_TITLE = ""
    command._stopped.set()

    command.run_server()

    assert "disabled" in command.stdout.getvalue()


@pytest.mark.django_db
def test_refresh_applies_senders_and_suspension_to_scp_and_handler(command, handler_and_scp):
    handler, scp = handler_and_scp
    sender = RouterSenderFactory.create(calling_ae_title="PACS1")

    command._refresh(scp, handler)

    assert handler.config == IntakeConfig(sender_ids={"PACS1": sender.pk}, suspended=False)
    assert scp._allowed_calling_aets == frozenset({"PACS1"})


@pytest.mark.django_db
def test_disabling_a_sender_takes_effect_at_the_next_refresh(command, handler_and_scp):
    handler, scp = handler_and_scp
    sender = RouterSenderFactory.create(calling_ae_title="PACS1")
    command._refresh(scp, handler)

    sender.enabled = False
    sender.save()
    command._refresh(scp, handler)

    assert handler.config.sender_ids == {}
    assert scp._allowed_calling_aets == frozenset()


def test_startup_waits_for_the_database(command, handler_and_scp, monkeypatch):
    handler, scp = handler_and_scp
    attempts: list[int] = []

    def flaky_load():
        attempts.append(1)
        if len(attempts) == 1:
            raise ProgrammingError('relation "router_routersettings" does not exist')
        return IntakeConfig(sender_ids={"PACS1": 1}, suspended=False)

    monkeypatch.setattr(router_command, "load_intake_config", flaky_load)
    monkeypatch.setattr(router_command, "STARTUP_RETRY_SECONDS", 0)

    assert command._load_config_until_ready(scp, handler) is True
    assert len(attempts) == 2
    assert handler.config.sender_ids == {"PACS1": 1}


def test_startup_gives_up_when_the_command_stops(command, handler_and_scp, monkeypatch):
    handler, scp = handler_and_scp

    def broken_load():
        command._stopped.set()
        raise ProgrammingError('relation "router_routersettings" does not exist')

    monkeypatch.setattr(router_command, "load_intake_config", broken_load)
    monkeypatch.setattr(router_command, "STARTUP_RETRY_SECONDS", 0)

    assert command._load_config_until_ready(scp, handler) is False
