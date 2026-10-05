import pytest
from adit_radis_shared.accounts.factories import UserFactory
from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import Permission
from django.test import RequestFactory

from adit.core.factories import DicomServerFactory
from adit.router.admin import RouterBatchAdmin, RoutingRuleAdmin
from adit.router.factories import RouterBatchFactory, RouterJobFactory, RoutingRuleFactory
from adit.router.forms import RoutingRuleForm
from adit.router.models import RouterBatch, RoutingRule


def _request(user):
    request = RequestFactory().get("/")
    request.user = user
    return request


def _rule_editor():
    """A staff user who may edit rules but not switch pseudonymization off."""
    user = UserFactory.create(is_staff=True)
    user.user_permissions.add(
        Permission.objects.get(content_type__app_label="router", codename="change_routingrule")
    )
    return user


def _rule_editor_allowed_unpseudonymized():
    """A staff user who may also switch pseudonymization off."""
    user = _rule_editor()
    user.user_permissions.add(
        Permission.objects.get(
            content_type__app_label="router", codename="can_transfer_unpseudonymized"
        )
    )
    return user


@pytest.mark.django_db
def test_pseudonymization_is_read_only_once_the_rule_has_jobs():
    admin = RoutingRuleAdmin(RoutingRule, AdminSite())
    rule = RoutingRuleFactory.create()
    request = _request(UserFactory.create(is_staff=True, is_superuser=True))

    assert "pseudonym_salt" not in admin.get_readonly_fields(request, rule)

    RouterJobFactory.create(rule=rule)

    readonly = admin.get_readonly_fields(request, rule)
    assert "pseudonymize" in readonly
    assert "pseudonym_salt" in readonly


@pytest.mark.django_db
def test_switching_pseudonymization_off_needs_the_permission():
    admin = RoutingRuleAdmin(RoutingRule, AdminSite())
    rule = RoutingRuleFactory.create()
    request = _request(_rule_editor())
    form_class = admin.get_form(request, rule, change=True)
    data = {
        "name": rule.name,
        "enabled": "on",
        "filters_json": '[{"modality": "CT"}]',
        "destination": rule.destination.pk,
        "pseudonym_salt": "",
        "trial_protocol_id": "",
        "trial_protocol_name": "",
    }

    form = form_class(data=data, instance=rule)

    assert not form.is_valid()
    assert "pseudonymize" in form.errors


@pytest.mark.django_db
def test_new_unpseudonymized_rule_is_refused():
    admin = RoutingRuleAdmin(RoutingRule, AdminSite())
    request = _request(_rule_editor())
    form_class = admin.get_form(request, None, change=False)
    data = {
        "name": "New rule",
        "enabled": "on",
        "filters_json": '[{"modality": "CT"}]',
        "destination": DicomServerFactory.create().pk,
        "pseudonym_salt": "",
        "trial_protocol_id": "",
        "trial_protocol_name": "",
    }

    form = form_class(data=data)

    assert not form.is_valid()
    assert "pseudonymize" in form.errors


@pytest.mark.django_db
def test_existing_unpseudonymized_rule_without_jobs_can_be_disabled():
    admin = RoutingRuleAdmin(RoutingRule, AdminSite())
    rule = RoutingRuleFactory.create(pseudonymize=False)
    request = _request(_rule_editor())
    form_class = admin.get_form(request, rule, change=True)
    data = {
        "name": rule.name,
        # "enabled" left unchecked: disabling the rule itself, not pseudonymization.
        "filters_json": '[{"modality": "CT"}]',
        "destination": rule.destination.pk,
        "pseudonym_salt": "",
        "trial_protocol_id": "",
        "trial_protocol_name": "",
    }

    form = form_class(data=data, instance=rule)

    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_switching_pseudonymization_off_is_allowed_with_the_permission():
    admin = RoutingRuleAdmin(RoutingRule, AdminSite())
    rule = RoutingRuleFactory.create()
    request = _request(_rule_editor_allowed_unpseudonymized())
    form_class = admin.get_form(request, rule, change=True)
    data = {
        "name": rule.name,
        "enabled": "on",
        "filters_json": '[{"modality": "CT"}]',
        "destination": rule.destination.pk,
        "pseudonym_salt": "",
        "trial_protocol_id": "",
        "trial_protocol_name": "",
    }

    form = form_class(data=data, instance=rule)

    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_batches_are_read_only_in_the_admin():
    admin = RouterBatchAdmin(RouterBatch, AdminSite())
    request = _request(UserFactory.create(is_staff=True, is_superuser=True))

    assert not admin.has_add_permission(request)
    assert not admin.has_change_permission(request, RouterBatchFactory.create())
    assert not admin.has_delete_permission(request)


@pytest.mark.django_db
def test_rule_with_jobs_stays_editable_without_the_permission():
    admin = RoutingRuleAdmin(RoutingRule, AdminSite())
    rule = RoutingRuleFactory.create()
    RouterJobFactory.create(rule=rule)
    request = _request(_rule_editor())
    form_class = admin.get_form(request, rule, change=True)
    data = {
        "name": "Renamed",
        "enabled": "on",
        "filters_json": '[{"modality": "CT"}]',
        "destination": rule.destination.pk,
        "trial_protocol_id": "",
        "trial_protocol_name": "",
    }

    form = form_class(data=data, instance=rule)

    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_admin_edits_rules_with_the_form_of_the_router_pages():
    admin = RoutingRuleAdmin(RoutingRule, AdminSite())
    rule = RoutingRuleFactory.create()

    form_class = admin.get_form(_request(_rule_editor()), rule, change=True)

    assert issubclass(form_class, RoutingRuleForm)
