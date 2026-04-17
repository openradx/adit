import importlib
import sys

import pytest
from django.core.files.storage import storages

DEPRECATED_DBBACKUP_SETTINGS_ERROR = (
    "The settings DBBACKUP_STORAGE and DBBACKUP_STORAGE_OPTIONS have been deprecated"
)


def _import_dbbackup_settings():
    storages._storages.clear()  # type: ignore[attr-defined]
    sys.modules.pop("dbbackup.settings", None)
    importlib.import_module("dbbackup.settings")


def test_dbbackup_settings_import_succeeds():
    _import_dbbackup_settings()


def test_dbbackup_settings_import_fails_with_legacy_storage_settings(settings):
    settings.DBBACKUP_STORAGE = "irrelevant"
    settings.DBBACKUP_STORAGE_OPTIONS = {}

    with pytest.raises(
        RuntimeError,
        match=DEPRECATED_DBBACKUP_SETTINGS_ERROR,
    ):
        _import_dbbackup_settings()
