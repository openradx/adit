import json

import pytest
from adit_radis_shared.accounts.factories import UserFactory
from adit_radis_shared.common.utils.testing_helpers import login_user
from playwright.sync_api import Page, expect
from pytest_django.live_server_helper import LiveServer

from adit.core.factories import DicomServerFactory
from adit.core.utils.series_filters import parse_filters
from adit.router.models import RoutingRule

FILTERS = [{"mode": "include", "modality": "CT"}, {"mode": "exclude", "modality": "SR"}]


@pytest.mark.acceptance
@pytest.mark.order("last")
@pytest.mark.django_db(transaction=True)
def test_staff_create_a_routing_rule_in_the_browser(page: Page, live_server: LiveServer):
    password = "my_secret_secret"
    staff = UserFactory.create(is_staff=True, password=password)
    DicomServerFactory.create(name="XNAT Test", store_scp_support=True)
    login_user(page, live_server.url, staff.username, password)

    page.get_by_role("link", name="Router", exact=True).click()
    page.get_by_role("link", name="New Rule").click()

    page.get_by_role("button", name="Help").click()
    # get_by_text("Routing Rule Help") is ambiguous: the page heading's "New Routing
    # Rule" title and "Help" button combine into a match too. The modal's own heading
    # is unique.
    expect(page.get_by_role("heading", name="Routing Rule Help")).to_be_visible()
    page.locator("#htmx-modal .btn-close").click()
    expect(page.get_by_role("heading", name="Routing Rule Help")).to_be_hidden()

    page.locator("#id_name").fill("CT to XNAT")
    page.locator("#id_destination").select_option(label="DICOM Server XNAT Test")
    page.evaluate(
        """(value) => {
            const cm = document.querySelector('.CodeMirror').CodeMirror;
            cm.setValue(value);
        }""",
        json.dumps(FILTERS),
    )
    page.locator("#id_trial_protocol_id").fill("XNATPROJ")
    page.get_by_role("button", name="Save Rule").click()

    expect(page.get_by_text('Routing rule "CT to XNAT" was created.')).to_be_visible()
    expect(page.get_by_role("button", name="Disable Rule")).to_be_visible()
    rule = RoutingRule.objects.get(name="CT to XNAT")
    assert rule.created_by == staff
    assert rule.filters_json == parse_filters(FILTERS)
    assert rule.trial_protocol_id == "XNATPROJ"
    assert page.url == live_server.url + rule.get_absolute_url()
