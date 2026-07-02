"""Tests for ``adit/upload/forms.py`` (``UploadForm``).

The form has two fields: a required ``pseudonym`` (max 64 chars, no backslash or
control characters) and a required ``destination`` (a ``DicomNodeChoiceField`` whose
queryset is the destination-nodes accessible to the user). Validity therefore depends
on the user's granted destinations, so these tests touch the DB.
"""

import pytest
from adit_radis_shared.accounts.factories import GroupFactory, UserFactory
from adit_radis_shared.common.utils.testing_helpers import add_user_to_group

from adit.core.factories import DicomServerFactory
from adit.core.utils.auth_utils import grant_access
from adit.upload.forms import UploadForm


def _user_with_destination():
    user = UserFactory.create()
    group = GroupFactory.create()
    add_user_to_group(user, group)
    server = DicomServerFactory.create()
    grant_access(group, server, destination=True)
    return user, server


@pytest.mark.django_db
def test_form_valid_with_pseudonym_and_destination():
    user, server = _user_with_destination()
    form = UploadForm(
        data={"pseudonym": "PSEUDO1", "destination": str(server.pk)},
        user=user,
        action="transfer",
    )
    assert form.is_valid(), form.errors
    assert form.cleaned_data["pseudonym"] == "PSEUDO1"
    # The choice field returns the DicomNode base instance for the same row; compare
    # by primary key (a DicomNode == DicomServer subclass compare is not identity-equal).
    assert form.cleaned_data["destination"].pk == server.pk


@pytest.mark.django_db
def test_form_invalid_without_pseudonym():
    user, server = _user_with_destination()
    form = UploadForm(
        data={"pseudonym": "", "destination": str(server.pk)},
        user=user,
        action="transfer",
    )
    assert not form.is_valid()
    assert "pseudonym" in form.errors


@pytest.mark.django_db
def test_form_invalid_without_destination():
    user, _ = _user_with_destination()
    form = UploadForm(
        data={"pseudonym": "PSEUDO1"},
        user=user,
        action="transfer",
    )
    assert not form.is_valid()
    assert "destination" in form.errors


@pytest.mark.django_db
def test_form_rejects_pseudonym_with_backslash():
    user, server = _user_with_destination()
    form = UploadForm(
        data={"pseudonym": "bad\\pseudo", "destination": str(server.pk)},
        user=user,
        action="transfer",
    )
    assert not form.is_valid()
    assert "pseudonym" in form.errors


@pytest.mark.django_db
def test_form_rejects_pseudonym_with_control_char():
    user, server = _user_with_destination()
    form = UploadForm(
        data={"pseudonym": "bad\npseudo", "destination": str(server.pk)},
        user=user,
        action="transfer",
    )
    assert not form.is_valid()
    assert "pseudonym" in form.errors


@pytest.mark.django_db
def test_form_rejects_pseudonym_over_max_length():
    user, server = _user_with_destination()
    form = UploadForm(
        data={"pseudonym": "P" * 65, "destination": str(server.pk)},
        user=user,
        action="transfer",
    )
    assert not form.is_valid()
    assert "pseudonym" in form.errors


@pytest.mark.django_db
def test_form_rejects_inaccessible_destination():
    """A destination the user's group has no access to is not a valid choice."""
    user, _ = _user_with_destination()
    # A second server granted to a *different* group only.
    other_group = GroupFactory.create()
    forbidden_server = DicomServerFactory.create()
    grant_access(other_group, forbidden_server, destination=True)

    form = UploadForm(
        data={"pseudonym": "PSEUDO1", "destination": str(forbidden_server.pk)},
        user=user,
        action="transfer",
    )
    assert not form.is_valid()
    assert "destination" in form.errors


@pytest.mark.django_db
def test_form_helper_and_layout_configured():
    """The crispy FormHelper carries the htmx/alpine attributes the template relies on."""
    user, _ = _user_with_destination()
    form = UploadForm(user=user, action="transfer")

    assert form.helper.attrs["hx-post"] == ""
    assert form.helper.attrs["enctype"] == "multipart/form-data"
    assert form.helper.attrs["id"] == "myForm"
    # The destination + pseudonym fields are wired up.
    assert "destination" in form.fields
    assert form.fields["pseudonym"].required is True
    assert form.fields["destination"].required is True


@pytest.mark.django_db
def test_build_option_field_merges_additional_attrs():
    """build_option_field merges caller-supplied attrs with the enter-key guard
    (forms.py:86-90)."""
    user, _ = _user_with_destination()
    form = UploadForm(user=user, action="transfer")

    column = form.build_option_field("pseudonym", additional_attrs={"data-x": "1"})
    field = column.fields[0]
    # Both the additional attr and the default keydown guard are present.
    assert field.attrs["data-x"] == "1"
    assert "@keydown.enter.prevent" in field.attrs
