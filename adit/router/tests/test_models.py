import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from adit.core.factories import DicomServerFactory
from adit.router.factories import RouterSenderFactory
from adit.router.models import RouterSender, RouterSettings


@pytest.mark.django_db
def test_router_settings_row_exists_after_migrate():
    router_settings = RouterSettings.get()

    assert isinstance(router_settings, RouterSettings)
    assert router_settings.suspended is False


@pytest.mark.django_db
def test_sender_defaults_calling_ae_title_to_the_server_ae_title():
    server = DicomServerFactory.create(ae_title="PACS1")

    sender = RouterSender.objects.create(server=server)

    assert sender.calling_ae_title == "PACS1"


@pytest.mark.django_db
def test_sender_keeps_a_different_sending_ae_title_stripped():
    server = DicomServerFactory.create(ae_title="PACS_QR")

    sender = RouterSender.objects.create(server=server, calling_ae_title=" PACS_SEND ")

    assert sender.calling_ae_title == "PACS_SEND"


@pytest.mark.django_db
def test_full_clean_fills_the_calling_ae_title_for_the_admin_form():
    server = DicomServerFactory.create(ae_title="PACS1")
    sender = RouterSender(server=server)

    sender.full_clean()

    assert sender.calling_ae_title == "PACS1"


@pytest.mark.django_db
def test_calling_ae_titles_are_unique():
    RouterSenderFactory.create(calling_ae_title="PACS1")

    with pytest.raises(IntegrityError):
        RouterSenderFactory.create(calling_ae_title="PACS1")


@pytest.mark.django_db
def test_calling_ae_title_rejects_a_backslash():
    sender = RouterSender(server=DicomServerFactory.create(), calling_ae_title="PA\\CS")

    with pytest.raises(ValidationError) as exc_info:
        sender.full_clean()

    assert "calling_ae_title" in exc_info.value.message_dict


@pytest.mark.django_db
@pytest.mark.parametrize("ae_title", ["PACS KÖLN", "PACS\tA"])
def test_calling_ae_title_rejects_what_pynetdicom_refuses(ae_title):
    sender = RouterSender(server=DicomServerFactory.create(), calling_ae_title=ae_title)

    with pytest.raises(ValidationError) as exc_info:
        sender.full_clean()

    assert "calling_ae_title" in exc_info.value.message_dict


@pytest.mark.django_db
def test_full_clean_rejects_an_invalid_server_ae_title_as_calling_ae_title():
    sender = RouterSender(server=DicomServerFactory.create(ae_title="BAD\\AE"))

    with pytest.raises(ValidationError) as exc_info:
        sender.full_clean()

    assert "calling_ae_title" in exc_info.value.message_dict
