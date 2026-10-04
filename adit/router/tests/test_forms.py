import json

import pytest
from adit_radis_shared.accounts.factories import UserFactory
from adit_radis_shared.accounts.models import User
from adit_radis_shared.common.utils.testing_helpers import add_permission

from adit.core.factories import DicomServerFactory
from adit.core.utils.series_filters import parse_filters
from adit.router.factories import RouterJobFactory, RoutingRuleFactory
from adit.router.forms import FILTERS_EXAMPLE, RoutingRuleForm
from adit.router.models import RoutingRule

NOT_ALLOWED = "You are not allowed to send studies without pseudonymization."


def _staff(*, unpseudonymized: bool = False) -> User:
    user = UserFactory.create(is_staff=True)
    if unpseudonymized:
        add_permission(user, "router", "can_transfer_unpseudonymized")
    return user


def _data(rule: RoutingRule | None = None, **overrides: str | None) -> dict[str, str]:
    """The POST data of the rule form; an override of None leaves the field out."""
    data: dict[str, str | None] = {
        "name": rule.name if rule else "CT to XNAT",
        "enabled": "on",
        "destination": str(rule.destination_id if rule else DicomServerFactory.create().pk),
        "filters_json": '[{"modality": "CT"}]',
        "pseudonymize": "on",
        "pseudonym_salt": rule.pseudonym_salt if rule else "a" * 64,
        "trial_protocol_id": "",
        "trial_protocol_name": "",
    }
    data.update(overrides)
    return {key: value for key, value in data.items() if value is not None}


@pytest.mark.django_db
def test_new_rule_form_suggests_example_filters_as_indented_json():
    form = RoutingRuleForm(user=_staff())

    value = form["filters_json"].value()

    assert json.loads(value) == FILTERS_EXAMPLE
    assert '\n  {\n    "mode": "include"' in value


@pytest.mark.django_db
def test_edit_form_shows_the_rules_filters_as_json():
    rule = RoutingRuleFactory.create(filters_json=parse_filters([{"modality": "MR"}]))

    form = RoutingRuleForm(instance=rule, user=_staff())

    assert json.loads(form["filters_json"].value()) == rule.filters_json


@pytest.mark.django_db
def test_invalid_json_keeps_the_typed_text():
    form = RoutingRuleForm(data=_data(filters_json='[{"modality": "CT"'), user=_staff())

    assert not form.is_valid()
    assert "filters_json" in form.errors
    assert form["filters_json"].value() == '[{"modality": "CT"'


@pytest.mark.django_db
def test_filters_are_validated_like_mass_transfer_filters():
    form = RoutingRuleForm(
        data=_data(filters_json='[{"mode": "exclude", "modality": "SR"}]'), user=_staff()
    )

    assert not form.is_valid()
    assert form.errors["filters_json"] == ["At least one filter must have mode=include."]


@pytest.mark.django_db
def test_saved_rule_keeps_the_normalized_filters():
    user = _staff()
    form = RoutingRuleForm(data=_data(), user=user)
    assert form.is_valid(), form.errors

    rule = form.save(commit=False)
    rule.created_by = user
    rule.save()

    rule.refresh_from_db()
    assert rule.filters_json == parse_filters([{"modality": "CT"}])


@pytest.mark.django_db
def test_new_unpseudonymized_rule_needs_the_permission():
    refused = RoutingRuleForm(data=_data(pseudonymize=None), user=_staff())
    allowed = RoutingRuleForm(data=_data(pseudonymize=None), user=_staff(unpseudonymized=True))

    assert refused.errors["pseudonymize"] == [NOT_ALLOWED]
    assert allowed.is_valid(), allowed.errors


@pytest.mark.django_db
def test_switching_pseudonymization_off_needs_the_permission():
    rule = RoutingRuleFactory.create(pseudonymize=True)

    form = RoutingRuleForm(data=_data(rule, pseudonymize=None), instance=rule, user=_staff())

    assert form.errors["pseudonymize"] == [NOT_ALLOWED]


@pytest.mark.django_db
def test_editing_an_unpseudonymized_rule_needs_no_permission():
    rule = RoutingRuleFactory.create(pseudonymize=False, pseudonym_salt="")

    form = RoutingRuleForm(
        data=_data(rule, name="Renamed", pseudonymize=None), instance=rule, user=_staff()
    )

    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_pseudonymization_is_locked_once_the_rule_has_jobs():
    rule = RoutingRuleFactory.create()
    unlocked = RoutingRuleForm(instance=rule, user=_staff())
    RouterJobFactory.create(rule=rule)

    locked = RoutingRuleForm(instance=rule, user=_staff())

    assert not unlocked.fields["pseudonymize"].disabled
    assert locked.fields["pseudonymize"].disabled
    assert locked.fields["pseudonym_salt"].disabled


@pytest.mark.django_db
def test_posted_pseudonymization_of_a_locked_rule_is_ignored():
    rule = RoutingRuleFactory.create(pseudonymize=True)
    RouterJobFactory.create(rule=rule)
    salt = rule.pseudonym_salt

    form = RoutingRuleForm(
        data=_data(rule, pseudonymize=None, pseudonym_salt="0" * 64),
        instance=rule,
        user=_staff(),
    )
    assert form.is_valid(), form.errors
    form.save()

    rule.refresh_from_db()
    assert rule.pseudonymize is True
    assert rule.pseudonym_salt == salt


@pytest.mark.django_db
def test_locked_rule_saves_when_the_browser_leaves_out_its_disabled_fields():
    rule = RoutingRuleFactory.create(pseudonymize=True)
    RouterJobFactory.create(rule=rule)
    salt = rule.pseudonym_salt

    form = RoutingRuleForm(
        data=_data(rule, name="Renamed", pseudonymize=None, pseudonym_salt=None),
        instance=rule,
        user=_staff(),
    )
    assert form.is_valid(), form.errors
    form.save()

    rule.refresh_from_db()
    assert rule.name == "Renamed"
    assert rule.pseudonym_salt == salt
