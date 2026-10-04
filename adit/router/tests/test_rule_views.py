import pytest
from adit_radis_shared.accounts.factories import UserFactory
from adit_radis_shared.accounts.models import User
from adit_radis_shared.common.utils.testing_helpers import add_permission
from django.conf import settings
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from pytest_django.asserts import assertContains, assertNotContains, assertTemplateUsed

from adit.core.factories import DicomServerFactory
from adit.core.models import DicomServer
from adit.core.utils.series_filters import parse_filters
from adit.router.factories import RouterJobFactory, RoutingRuleFactory
from adit.router.models import RouterJob, RouterTask, RoutingRule
from adit.router.utils.testing_helpers import create_delivery


def _staff() -> User:
    return UserFactory.create(is_staff=True)


def _messages(response) -> list[str]:
    return [str(message) for message in response.context["messages"]]


def _rule_pages_and_actions(rule: RoutingRule) -> list[tuple[str, str]]:
    return [
        ("get", reverse("router_rule_list")),
        ("get", reverse("router_rule_detail", args=[rule.pk])),
        ("post", reverse("router_rule_toggle", args=[rule.pk])),
        ("post", reverse("router_rule_retry_failed", args=[rule.pk])),
    ]


@pytest.mark.django_db
def test_rule_pages_and_actions_need_a_login(client: Client):
    for method, url in _rule_pages_and_actions(RoutingRuleFactory.create()):
        response = getattr(client, method)(url)
        assert response.status_code == 302, url
        assert response["Location"].startswith(settings.LOGIN_URL), url


@pytest.mark.django_db
def test_rule_pages_and_actions_are_refused_to_the_non_staff_rule_creator(client: Client):
    creator = UserFactory.create()
    rule = RoutingRuleFactory.create(created_by=creator, enabled=True)
    client.force_login(creator)

    for method, url in _rule_pages_and_actions(rule):
        assert getattr(client, method)(url).status_code == 403, url

    rule.refresh_from_db()
    assert rule.enabled


@pytest.mark.django_db
def test_router_menu_item_is_shown_to_staff_only(client: Client):
    rule_list_link = f'href="{reverse("router_rule_list")}"'

    client.force_login(_staff())
    staff_home = client.get(reverse("home"))
    client.force_login(UserFactory.create())
    user_home = client.get(reverse("home"))

    assertContains(staff_home, rule_list_link)
    assertNotContains(user_home, rule_list_link)


@pytest.mark.django_db
def test_rule_list_shows_each_rules_deliveries_by_status(client: Client):
    rule = RoutingRuleFactory.create(name="CT to XNAT", enabled=False)
    for status in (RouterJob.Status.FAILURE, RouterJob.Status.SUCCESS, RouterJob.Status.SUCCESS):
        RouterJobFactory.create(rule=rule, status=status)
    RoutingRuleFactory.create(name="Never matched")
    client.force_login(_staff())

    response = client.get(reverse("router_rule_list"))

    assert response.status_code == 200
    assertContains(response, f'href="{rule.get_absolute_url()}"')
    assertContains(response, '<span class="text-muted">Off</span>', html=True)
    jobs_of_rule = f"{reverse('router_job_list')}?rule={rule.pk}&amp;status="
    assertContains(response, f'href="{jobs_of_rule}FA"')
    assertContains(response, "Failure 1")
    assertContains(response, f'href="{jobs_of_rule}SU"')
    assertContains(response, "Success 2")
    never_matched = next(
        row for row in response.context["table"].rows if row.record.name == "Never matched"
    )
    assert never_matched.get_cell("deliveries") == "—"
    assert never_matched.get_cell("last_match") == "—"


def _rule_with_deliveries() -> RoutingRule:
    rule = RoutingRuleFactory.create()
    RouterJobFactory.create(rule=rule, status=RouterJob.Status.FAILURE)
    RouterJobFactory.create(rule=rule, status=RouterJob.Status.SUCCESS)
    return rule


@pytest.mark.django_db
def test_rule_list_counts_in_the_same_number_of_queries_for_more_rules(
    client: Client, django_assert_max_num_queries
):
    client.force_login(_staff())
    _rule_with_deliveries()
    client.get(reverse("router_rule_list"))  # fills the per-process caches, like the site
    with CaptureQueriesContext(connection) as one_rule:
        client.get(reverse("router_rule_list"))
    for _ in range(3):
        _rule_with_deliveries()

    with django_assert_max_num_queries(len(one_rule)):
        response = client.get(reverse("router_rule_list"))

    assert len(response.context["table"].rows) == 4


@pytest.mark.django_db
def test_router_jobs_link_their_rule(client: Client):
    job = RouterJobFactory.create()
    client.force_login(_staff())

    response = client.get(reverse("router_job_list"))

    assertContains(response, f'href="{job.rule.get_absolute_url()}"')


@pytest.mark.django_db
def test_rule_page_shows_the_settings_but_not_the_salt(client: Client):
    rule = RoutingRuleFactory.create(trial_protocol_id="XNATPROJ")
    client.force_login(_staff())

    response = client.get(reverse("router_rule_detail", args=[rule.pk]))

    assert response.status_code == 200
    assertContains(response, rule.name)
    assertContains(response, "XNATPROJ")
    assertContains(response, "&quot;modality&quot;: &quot;CT&quot;")
    assertNotContains(response, rule.pseudonym_salt)


@pytest.mark.django_db
def test_rule_page_lists_only_the_rules_deliveries(client: Client):
    rule = RoutingRuleFactory.create()
    sent = create_delivery(RouterJob.Status.SUCCESS, rule=rule)
    RouterTask.objects.filter(pk=sent.pk).update(sent_instance_uids=["1.1", "1.2"])
    list_cleared = create_delivery(RouterJob.Status.SUCCESS, rule=rule)
    create_delivery(RouterJob.Status.SUCCESS)
    client.force_login(_staff())

    response = client.get(reverse("router_rule_detail", args=[rule.pk]))

    rows = {row.record.pk: row for row in response.context["table"].rows}
    assert set(rows) == {sent.job.pk, list_cleared.job.pk}
    assert str(rows[sent.job.pk].get_cell("images_sent")) == "2"
    assert rows[list_cleared.job.pk].get_cell("images_sent") == "—"
    assert rows[sent.job.pk].get_cell("patient_id") == sent.patient_id
    assertContains(response, sent.job.get_absolute_url())


@pytest.mark.django_db
def test_rule_page_filters_the_deliveries_by_status(client: Client):
    rule = RoutingRuleFactory.create()
    failed = create_delivery(RouterJob.Status.FAILURE, rule=rule)
    create_delivery(RouterJob.Status.SUCCESS, rule=rule)
    client.force_login(_staff())

    response = client.get(
        reverse("router_rule_detail", args=[rule.pk]), {"status": RouterJob.Status.FAILURE}
    )

    assert [row.record for row in response.context["table"].rows] == [failed.job]
    assertContains(response, "Retry Failed Deliveries (1)")


def _destination_cannot_receive(rule: RoutingRule) -> None:
    DicomServer.objects.filter(pk=rule.destination_id).update(
        store_scp_support=False, dicomweb_stow_support=False
    )


@pytest.mark.django_db
def test_disable_rule_switches_a_rule_off(client: Client):
    rule = RoutingRuleFactory.create(enabled=True)
    client.force_login(_staff())

    response = client.post(reverse("router_rule_toggle", args=[rule.pk]), {"enabled": "0"})

    assert response["Location"] == rule.get_absolute_url()
    rule.refresh_from_db()
    assert rule.enabled is False


@pytest.mark.django_db
def test_enable_rule_switches_a_valid_rule_on(client: Client):
    rule = RoutingRuleFactory.create(enabled=False)
    client.force_login(_staff())

    response = client.post(
        reverse("router_rule_toggle", args=[rule.pk]), {"enabled": "1"}, follow=True
    )

    assert _messages(response) == [f'Routing rule "{rule.name}" is now enabled.']
    rule.refresh_from_db()
    assert rule.enabled is True


@pytest.mark.django_db
def test_rule_that_no_longer_validates_can_still_be_disabled(client: Client):
    rule = RoutingRuleFactory.create(enabled=True)
    _destination_cannot_receive(rule)
    client.force_login(_staff())

    client.post(reverse("router_rule_toggle", args=[rule.pk]), {"enabled": "0"})

    rule.refresh_from_db()
    assert rule.enabled is False


@pytest.mark.django_db
def test_rule_that_no_longer_validates_cannot_be_enabled(client: Client):
    rule = RoutingRuleFactory.create(enabled=False)
    _destination_cannot_receive(rule)
    client.force_login(_staff())

    response = client.post(
        reverse("router_rule_toggle", args=[rule.pk]), {"enabled": "1"}, follow=True
    )

    assert _messages(response) == [
        "The rule can't be enabled: The destination must support C-STORE or STOW-RS. "
        "Edit the rule first."
    ]
    rule.refresh_from_db()
    assert rule.enabled is False


@pytest.mark.django_db
def test_posting_the_state_a_rule_already_has_changes_nothing(client: Client):
    rule = RoutingRuleFactory.create(enabled=True)
    updated = rule.updated
    client.force_login(_staff())

    response = client.post(
        reverse("router_rule_toggle", args=[rule.pk]), {"enabled": "1"}, follow=True
    )

    assert _messages(response) == [f'Routing rule "{rule.name}" is already enabled.']
    rule.refresh_from_db()
    assert rule.enabled is True
    assert rule.updated == updated


@pytest.mark.django_db
@pytest.mark.parametrize("data", [{}, {"enabled": "yes"}])
def test_toggle_without_a_valid_state_is_refused(client: Client, data: dict[str, str]):
    rule = RoutingRuleFactory.create(enabled=True)
    client.force_login(_staff())

    response = client.post(reverse("router_rule_toggle", args=[rule.pk]), data)

    assert response.status_code == 400
    rule.refresh_from_db()
    assert rule.enabled is True


@pytest.mark.django_db
def test_retry_failed_deliveries_reports_those_without_images(client: Client):
    rule = RoutingRuleFactory.create()
    retriable = create_delivery(RouterJob.Status.FAILURE, rule=rule)
    images_deleted = create_delivery(RouterJob.Status.FAILURE, rule=rule, files_deleted=True)
    client.force_login(_staff())

    response = client.post(reverse("router_rule_retry_failed", args=[rule.pk]), follow=True)

    assert response.redirect_chain[-1][0] == rule.get_absolute_url()
    assert _messages(response) == [
        "1 failed delivery will be retried. 1 more could not be retried because the images "
        "were deleted from the spool; have the PACS forward that study again."
    ]
    assert RouterTask.objects.get(pk=retriable.pk).status == RouterTask.Status.PENDING
    assert RouterTask.objects.get(pk=images_deleted.pk).status == RouterTask.Status.FAILURE


@pytest.mark.django_db
def test_retry_failed_deliveries_says_when_none_could_be_retried(client: Client):
    rule = RoutingRuleFactory.create()
    create_delivery(RouterJob.Status.FAILURE, rule=rule, files_deleted=True)
    create_delivery(RouterJob.Status.FAILURE, rule=rule, files_deleted=True)
    client.force_login(_staff())

    response = client.post(reverse("router_rule_retry_failed", args=[rule.pk]), follow=True)

    assert _messages(response) == [
        "No failed delivery could be retried because the images were deleted from the "
        "spool; have the PACS forward those studies again."
    ]


@pytest.mark.django_db
def test_retry_failed_deliveries_of_a_rule_without_failures(client: Client):
    rule = RoutingRuleFactory.create()
    create_delivery(RouterJob.Status.SUCCESS, rule=rule)
    client.force_login(_staff())

    response = client.post(reverse("router_rule_retry_failed", args=[rule.pk]), follow=True)

    assert _messages(response) == ["This rule has no failed deliveries."]


def _form_data(**overrides: str | None) -> dict[str, str]:
    """POST data of the rule form; an override of None leaves the field out."""
    data: dict[str, str | None] = {
        "name": "CT to XNAT",
        "enabled": "on",
        "destination": str(DicomServerFactory.create().pk),
        "filters_json": '[{"modality": "CT"}]',
        "pseudonymize": "on",
        "pseudonym_salt": "a" * 64,
        "trial_protocol_id": "XNATPROJ",
        "trial_protocol_name": "",
    }
    data.update(overrides)
    return {key: value for key, value in data.items() if value is not None}


@pytest.mark.django_db
def test_rule_form_pages_need_a_login(client: Client):
    rule = RoutingRuleFactory.create()

    for url in (reverse("router_rule_create"), reverse("router_rule_update", args=[rule.pk])):
        response = client.get(url)
        assert response.status_code == 302, url
        assert response["Location"].startswith(settings.LOGIN_URL), url


@pytest.mark.django_db
def test_rule_form_pages_and_help_are_refused_to_non_staff(client: Client):
    creator = UserFactory.create()
    rule = RoutingRuleFactory.create(created_by=creator)
    client.force_login(creator)

    assert client.get(reverse("router_rule_create")).status_code == 403
    assert client.post(reverse("router_rule_create"), _form_data()).status_code == 403
    assert client.get(reverse("router_rule_update", args=[rule.pk])).status_code == 403
    assert client.get(reverse("router_help"), HTTP_HX_REQUEST="true").status_code == 403
    assert not RoutingRule.objects.filter(name="CT to XNAT").exists()


@pytest.mark.django_db
def test_help_is_an_htmx_dialog(client: Client):
    client.force_login(_staff())

    dialog = client.get(reverse("router_help"), HTTP_HX_REQUEST="true")
    page = client.get(reverse("router_help"))

    assertContains(dialog, "Routing Rule Help")
    assert page.status_code == 400


@pytest.mark.django_db
def test_rule_form_has_the_filter_editor_and_its_help(client: Client):
    client.force_login(_staff())

    response = client.get(reverse("router_rule_create"))

    assertTemplateUsed(response, "router/routing_rule_form.html")
    assertContains(response, "CodeMirror.fromTextArea")
    assertContains(response, '[data-bs-theme="dark"] .CodeMirror')
    assertContains(response, reverse("router_help"))
    assertContains(response, "XNAT files the images under this project ID")


@pytest.mark.django_db
def test_staff_create_a_rule(client: Client):
    user = _staff()
    client.force_login(user)

    response = client.post(reverse("router_rule_create"), _form_data())

    rule = RoutingRule.objects.get(name="CT to XNAT")
    assert response["Location"] == rule.get_absolute_url()
    assert rule.created_by == user
    assert rule.filters_json == parse_filters([{"modality": "CT"}])
    assert rule.trial_protocol_id == "XNATPROJ"


@pytest.mark.django_db
def test_creating_an_unpseudonymized_rule_needs_the_permission(client: Client):
    client.force_login(_staff())

    refused = client.post(reverse("router_rule_create"), _form_data(pseudonymize=None))

    assert refused.status_code == 200
    assertContains(refused, "You are not allowed to send studies without pseudonymization.")
    assert not RoutingRule.objects.exists()

    allowed_user = _staff()
    add_permission(allowed_user, "router", "can_transfer_unpseudonymized")
    client.force_login(allowed_user)
    client.post(reverse("router_rule_create"), _form_data(pseudonymize=None))

    rule = RoutingRule.objects.get()
    assert rule.pseudonymize is False
    assert rule.pseudonym_salt == ""


@pytest.mark.django_db
def test_staff_edit_a_rule(client: Client):
    rule = RoutingRuleFactory.create()
    client.force_login(_staff())
    data = _form_data(name="Renamed", pseudonym_salt=rule.pseudonym_salt)

    response = client.post(reverse("router_rule_update", args=[rule.pk]), data)

    assert response["Location"] == rule.get_absolute_url()
    rule.refresh_from_db()
    assert rule.name == "Renamed"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "locked_fields",
    [
        # What a browser posts: nothing for the disabled inputs.
        {"pseudonymize": None, "pseudonym_salt": None},
        # A crafted POST that tries to switch pseudonymization off and change the salt.
        {"pseudonymize": None, "pseudonym_salt": "0" * 64},
    ],
)
def test_editing_a_rule_with_deliveries_keeps_its_pseudonymization(
    client: Client, locked_fields: dict[str, str | None]
):
    rule = RoutingRuleFactory.create(pseudonymize=True)
    RouterJobFactory.create(rule=rule)
    salt = rule.pseudonym_salt
    client.force_login(_staff())
    page = client.get(reverse("router_rule_update", args=[rule.pk]))

    response = client.post(
        reverse("router_rule_update", args=[rule.pk]), _form_data(name="Renamed", **locked_fields)
    )

    assertContains(page, "Fixed once the rule has sent studies.")
    assert response["Location"] == rule.get_absolute_url()
    rule.refresh_from_db()
    assert rule.name == "Renamed"
    assert rule.pseudonymize is True
    assert rule.pseudonym_salt == salt
