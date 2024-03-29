import time
from typing import Callable

import pytest
from django.conf import settings
from django.contrib.sites.models import Site
from playwright.sync_api import Locator, Page, Response

from adit_radis_shared.accounts.factories import UserFactory
from adit_radis_shared.common.models import SiteProfile
from adit_radis_shared.common.utils.testing import ChannelsLiveServer


@pytest.fixture(autouse=True)
def simulate_data_migration(db):
    # In development and production Site and SiteProfile are created by some data migration.
    # Unfortunately, transaction tests to flush the database and this data is lost. Also the
    # `serialized_rollback` doesn't work correctly when using fixtures like `page` of Playwright
    # (see my issue below). With this fixture we make sure that the data that is normally added
    # by the data migrations (common/0002_* and common/0003_*) is present in the database.
    # This is an ugly workaround as we do redundant things, but it works.
    # TODO: A solution in the future could be the below pull request with cloning the database.
    # https://github.com/pytest-dev/pytest-django/issues/1117
    # https://github.com/wemake-services/django-test-migrations/issues/438
    # https://code.djangoproject.com/ticket/25251
    # https://github.com/django/django/pull/14147
    Site.objects.get_or_create(
        pk=settings.SITE_ID,
        defaults={
            "domain": settings.SITE_DOMAIN,
            "name": settings.SITE_NAME,
        },
    )
    SiteProfile.objects.get_or_create(
        site_id=settings.SITE_ID,
        defaults={
            "meta_keywords": settings.SITE_META_KEYWORDS,
            "meta_description": settings.SITE_META_DESCRIPTION,
            "project_url": settings.SITE_PROJECT_URL,
        },
    )


@pytest.fixture
def channels_live_server(request):
    server = ChannelsLiveServer()
    request.addfinalizer(server.stop)
    return server


@pytest.fixture
def poll():
    def _poll(
        locator: Locator,
        func: Callable[[Locator], Response | None] = lambda loc: loc.page.reload(),
        interval: int = 1_500,
        timeout: int = 15_000,
    ):
        start_time = time.time()
        while True:
            try:
                locator.wait_for(timeout=interval)
                return locator
            except Exception as err:
                elapsed_time = (time.time() - start_time) * 1000
                if elapsed_time > timeout:
                    raise err

            func(locator)

    return _poll


@pytest.fixture
def login_user(page: Page):
    def _login_user(server_url: str, username: str, password: str):
        page.goto(server_url + "/accounts/login")
        page.get_by_label("Username").fill(username)
        page.get_by_label("Password").fill(password)
        page.get_by_text("Log in").click()

    return _login_user


# TODO: See if we can make it a yield fixture with name logged_in_user
@pytest.fixture
def create_and_login_user(page: Page, login_user):
    def _create_and_login_user(server_url: str):
        password = "mysecret"
        user = UserFactory(password=password)

        login_user(server_url, user.username, password)

        return user

    return _create_and_login_user
