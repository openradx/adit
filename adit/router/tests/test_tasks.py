from pathlib import Path

from pytest_mock import MockerFixture

from adit.router import tasks


def test_closing_skips_when_the_spool_is_not_mounted(tmp_path, settings, mocker: MockerFixture):
    missing = tmp_path / "spool"
    settings.ROUTER_SPOOL_PATH = str(missing)
    cycle = mocker.patch.object(tasks, "run_spool_cycle")

    tasks.close_router_batches(timestamp=0)

    cycle.assert_not_called()
    assert not missing.exists()


def test_closing_runs_a_cycle_on_the_mounted_spool(tmp_path, settings, mocker: MockerFixture):
    settings.ROUTER_SPOOL_PATH = str(tmp_path)
    cycle = mocker.patch.object(tasks, "run_spool_cycle")

    tasks.close_router_batches(timestamp=0)

    assert cycle.call_args.args[0] == Path(tmp_path)


def test_failure_report_also_clears_old_sent_lists(mocker: MockerFixture):
    report = mocker.patch.object(tasks, "report_failed_deliveries")
    clear = mocker.patch.object(tasks, "clear_old_sent_lists")

    tasks.report_router_failures(timestamp=0)

    report.assert_called_once()
    clear.assert_called_once()
