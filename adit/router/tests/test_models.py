import pytest
from adit_radis_shared.accounts.factories import UserFactory
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db.models import ProtectedError

from adit.core.factories import DicomServerFactory
from adit.core.models import DicomTask
from adit.router.factories import (
    RouterJobFactory,
    RouterSenderFactory,
    RouterTaskFactory,
    RoutingRuleFactory,
)
from adit.router.models import RouterJob, RouterSender, RouterSettings, RouterTask, RoutingRule


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


def _unsaved_rule(**kwargs) -> RoutingRule:
    return RoutingRuleFactory.build(
        destination=DicomServerFactory.create(), created_by=UserFactory.create(), **kwargs
    )


@pytest.mark.django_db
def test_rule_clean_validates_the_filters():
    rule = _unsaved_rule(filters_json=[{"mode": "exclude", "modality": "SR"}])

    with pytest.raises(ValidationError) as exc_info:
        rule.clean()

    assert "filters_json" in exc_info.value.message_dict


@pytest.mark.django_db
def test_rule_clean_clears_the_salt_when_not_pseudonymizing():
    rule = _unsaved_rule(pseudonymize=False)

    rule.clean()

    assert rule.pseudonym_salt == ""


@pytest.mark.django_db
def test_rule_clean_gives_a_pseudonymizing_rule_a_salt():
    rule = _unsaved_rule(pseudonymize=True, pseudonym_salt="")

    rule.clean()

    assert len(rule.pseudonym_salt) == 64


@pytest.mark.django_db
def test_rule_destination_must_accept_images():
    server = DicomServerFactory.create(store_scp_support=False, dicomweb_stow_support=False)
    rule = RoutingRuleFactory.build(destination=server, created_by=UserFactory.create())

    with pytest.raises(ValidationError) as exc_info:
        rule.clean()

    assert "destination" in exc_info.value.message_dict


@pytest.mark.django_db
def test_pseudonymization_is_fixed_once_the_rule_has_sent_studies():
    rule = RoutingRuleFactory.create()
    RouterJobFactory.create(rule=rule)
    rule.pseudonym_salt = "0" * 64

    with pytest.raises(ValidationError, match="Create a new rule"):
        rule.clean()


@pytest.mark.django_db
def test_rule_with_jobs_cannot_be_deleted():
    rule = RoutingRuleFactory.create()
    RouterJobFactory.create(rule=rule)

    with pytest.raises(ProtectedError):
        rule.delete()


@pytest.mark.django_db
def test_a_rule_gets_one_job_per_batch():
    job = RouterJobFactory.create()

    with pytest.raises(IntegrityError):
        RouterJobFactory.create(rule=job.rule, batch=job.batch)


@pytest.mark.django_db
def test_router_jobs_have_the_router_priorities():
    job = RouterJobFactory.create()

    assert (job.default_priority, job.urgent_priority) == (3, 7)


@pytest.mark.django_db
def test_already_sent_collects_the_rules_finished_deliveries_of_the_study():
    task = RouterTaskFactory.create(
        status=DicomTask.Status.SUCCESS, sent_instance_uids=["1.1", "1.2"]
    )
    rule = task.job.rule
    RouterTaskFactory.create(
        job=RouterJobFactory.create(rule=rule),
        destination=task.destination,
        study_uid=task.study_uid,
        status=DicomTask.Status.WARNING,
        sent_instance_uids=["1.3"],
    )
    # Not counted: still pending, another study, another rule.
    RouterTaskFactory.create(
        job=RouterJobFactory.create(rule=rule),
        destination=task.destination,
        study_uid=task.study_uid,
        status=DicomTask.Status.PENDING,
        sent_instance_uids=["1.4"],
    )
    RouterTaskFactory.create(
        job=RouterJobFactory.create(rule=rule),
        destination=task.destination,
        study_uid="9.9",
        status=DicomTask.Status.SUCCESS,
        sent_instance_uids=["1.5"],
    )
    RouterTaskFactory.create(
        destination=task.destination,
        study_uid=task.study_uid,
        status=DicomTask.Status.SUCCESS,
        sent_instance_uids=["1.6"],
    )

    sent = RouterTask.already_sent(rule.pk, task.study_uid, task.destination_id)

    assert sent == {"1.1", "1.2", "1.3"}


@pytest.mark.django_db
def test_router_job_and_task_link_to_their_admin_pages():
    task = RouterTaskFactory.create()

    assert task.get_absolute_url() == f"/django-admin/router/routertask/{task.pk}/change/"
    assert task.job.get_absolute_url() == (f"/django-admin/router/routerjob/{task.job.pk}/change/")
    assert isinstance(task.job, RouterJob)
