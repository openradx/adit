import pytest
from adit_radis_shared.accounts.factories import UserFactory
from adit_radis_shared.accounts.models import User
from django.conf import settings
from django.test import Client
from django.urls import NoReverseMatch, reverse
from pytest_django.asserts import assertContains, assertNotContains

from adit.router import urls as router_urls
from adit.router.factories import RouterJobFactory, RoutingRuleFactory
from adit.router.mixins import RouterStaffRequiredMixin
from adit.router.models import RouterJob, RouterTask
from adit.router.utils.testing_helpers import create_delivery


def _staff() -> User:
    return UserFactory.create(is_staff=True)


def _listed_jobs(response) -> list[RouterJob]:
    return [row.record for row in response.context["table"].rows]


def test_every_router_page_is_staff_only():
    for pattern in router_urls.urlpatterns:
        view_class = getattr(pattern.callback, "view_class")
        assert issubclass(view_class, RouterStaffRequiredMixin), pattern.name


@pytest.mark.django_db
def test_job_list_needs_a_login(client: Client):
    response = client.get(reverse("router_job_list"))

    assert response.status_code == 302
    assert response["Location"].startswith(settings.LOGIN_URL)


@pytest.mark.django_db
def test_job_list_is_refused_to_a_non_staff_rule_owner(client: Client):
    owner = UserFactory.create()
    RouterJobFactory.create(rule=RoutingRuleFactory.create(created_by=owner))
    client.force_login(owner)

    response = client.get(reverse("router_job_list"))

    assert response.status_code == 403


@pytest.mark.django_db
def test_staff_see_every_router_job(client: Client):
    jobs = [RouterJobFactory.create(), RouterJobFactory.create()]
    client.force_login(_staff())

    response = client.get(reverse("router_job_list"))

    assert response.status_code == 200
    assert set(_listed_jobs(response)) == set(jobs)


@pytest.mark.django_db
def test_router_jobs_can_be_filtered_by_rule_and_status(client: Client):
    rule = RoutingRuleFactory.create()
    match = RouterJobFactory.create(rule=rule, status=RouterJob.Status.FAILURE)
    RouterJobFactory.create(rule=rule, status=RouterJob.Status.SUCCESS)
    RouterJobFactory.create(status=RouterJob.Status.FAILURE)
    client.force_login(_staff())

    response = client.get(
        reverse("router_job_list"), {"rule": rule.pk, "status": RouterJob.Status.FAILURE}
    )

    assert _listed_jobs(response) == [match]
    assertContains(response, 'name="rule"')
    assertContains(response, 'name="status"')


@pytest.mark.django_db
def test_admin_section_links_router_jobs_by_status(client: Client):
    failed = RouterJobFactory.create(status=RouterJob.Status.FAILURE)
    RouterJobFactory.create(status=RouterJob.Status.SUCCESS)
    client.force_login(_staff())
    link = f"{reverse('router_job_list')}?all=1&status={RouterJob.Status.FAILURE.value}"

    overview = client.get(reverse("admin_section"))
    response = client.get(link)

    assertContains(overview, "<td>Router</td>", html=True)
    assertContains(overview, f'href="{link}"')
    assert _listed_jobs(response) == [failed]


def _job_pages_and_actions(task: RouterTask) -> list[tuple[str, str]]:
    job = task.job
    return [
        ("get", reverse("router_job_detail", args=[job.pk])),
        ("get", reverse("router_task_detail", args=[task.pk])),
        ("post", reverse("router_job_cancel", args=[job.pk])),
        ("post", reverse("router_job_retry", args=[job.pk])),
        ("post", reverse("router_job_restart", args=[job.pk])),
        ("post", reverse("router_task_reset", args=[task.pk])),
        ("post", reverse("router_task_kill", args=[task.pk])),
    ]


@pytest.mark.django_db
def test_job_pages_and_actions_need_a_login(client: Client):
    task = create_delivery(RouterJob.Status.FAILURE)

    for method, url in _job_pages_and_actions(task):
        response = getattr(client, method)(url)
        assert response.status_code == 302, url
        assert response["Location"].startswith(settings.LOGIN_URL), url


@pytest.mark.django_db
def test_job_pages_and_actions_are_refused_to_the_non_staff_owner(client: Client):
    owner = UserFactory.create()
    rule = RoutingRuleFactory.create(created_by=owner)
    task = create_delivery(RouterJob.Status.FAILURE, rule=rule)
    assert task.job.owner == owner
    client.force_login(owner)

    for method, url in _job_pages_and_actions(task):
        assert getattr(client, method)(url).status_code == 403, url

    task.refresh_from_db()
    assert task.status == RouterTask.Status.FAILURE


def test_router_jobs_have_no_delete_verify_or_resume_urls():
    for url_name in (
        "router_job_delete",
        "router_job_verify",
        "router_job_resume",
        "router_task_delete",
    ):
        with pytest.raises(NoReverseMatch):
            reverse(url_name, args=[1])


@pytest.mark.django_db
def test_job_page_shows_the_rule_and_the_batch(client: Client):
    task = create_delivery(RouterJob.Status.SUCCESS)
    job = task.job
    client.force_login(_staff())

    response = client.get(reverse("router_job_detail", args=[job.pk]))

    assert response.status_code == 200
    assertContains(response, f'<a href="{job.rule.get_absolute_url()}">{job.rule.name}</a>')
    assertContains(response, str(job.batch.batch_id))
    assertContains(response, job.batch.study_instance_uid)
    assertContains(response, job.batch.sender.calling_ae_title)
    assertContains(response, task.get_absolute_url())


@pytest.mark.django_db
def test_task_page_shows_the_delivery(client: Client):
    task = create_delivery(RouterJob.Status.SUCCESS)
    client.force_login(_staff())

    response = client.get(reverse("router_task_detail", args=[task.pk]))

    assert response.status_code == 200
    assertContains(response, task.patient_id)
    assertContains(response, reverse("router_job_detail", args=[task.job.pk]))


@pytest.mark.django_db
@pytest.mark.parametrize("status", [RouterJob.Status.PENDING, RouterJob.Status.CANCELED])
def test_job_and_task_pages_offer_no_delete_verify_or_resume(client: Client, status: str):
    task = create_delivery(status)
    client.force_login(_staff())

    job_page = client.get(reverse("router_job_detail", args=[task.job.pk]))
    task_page = client.get(reverse("router_task_detail", args=[task.pk]))

    assert job_page.status_code == 200
    assert task_page.status_code == 200
    for label in ("Delete Job", "Verify Job", "Resume Job"):
        assertNotContains(job_page, label)
    assertNotContains(task_page, "Delete Task")


@pytest.mark.django_db
def test_canceled_job_is_offered_a_restart(client: Client):
    task = create_delivery(RouterJob.Status.CANCELED)
    client.force_login(_staff())

    response = client.get(reverse("router_job_detail", args=[task.job.pk]))

    assertContains(response, "Restart Entire Job")


@pytest.mark.django_db
def test_cancel_stops_a_pending_delivery(client: Client):
    task = create_delivery(RouterJob.Status.PENDING)
    client.force_login(_staff())

    response = client.post(reverse("router_job_cancel", args=[task.job.pk]))

    assert response["Location"] == task.job.get_absolute_url()
    task.refresh_from_db()
    assert task.status == RouterTask.Status.CANCELED
    assert RouterJob.objects.get(pk=task.job.pk).status == RouterJob.Status.CANCELED


@pytest.mark.django_db
def test_retry_queues_a_failed_delivery_again(client: Client):
    task = create_delivery(RouterJob.Status.FAILURE)
    client.force_login(_staff())

    response = client.post(reverse("router_job_retry", args=[task.job.pk]))

    assert response["Location"] == task.job.get_absolute_url()
    task.refresh_from_db()
    assert task.status == RouterTask.Status.PENDING
    assert task.queued_job is not None


@pytest.mark.django_db
def test_restart_queues_a_finished_delivery_again(client: Client):
    task = create_delivery(RouterJob.Status.SUCCESS)
    client.force_login(_staff())

    response = client.post(reverse("router_job_restart", args=[task.job.pk]))

    assert response["Location"] == task.job.get_absolute_url()
    task.refresh_from_db()
    assert task.status == RouterTask.Status.PENDING
    assert task.queued_job is not None


@pytest.mark.django_db
def test_reset_queues_a_failed_task_again(client: Client):
    task = create_delivery(RouterJob.Status.FAILURE)
    client.force_login(_staff())

    response = client.post(reverse("router_task_reset", args=[task.pk]))

    assert response["Location"] == task.get_absolute_url()
    task.refresh_from_db()
    assert task.status == RouterTask.Status.PENDING
    assert RouterJob.objects.get(pk=task.job.pk).status == RouterJob.Status.PENDING


@pytest.mark.django_db
def test_kill_is_offered_for_a_running_task(client: Client):
    task = create_delivery(RouterJob.Status.IN_PROGRESS)
    client.force_login(_staff())

    page = client.get(reverse("router_task_detail", args=[task.pk]))
    response = client.post(reverse("router_task_kill", args=[task.pk]))

    assertContains(page, "Kill Task")
    assert response["Location"] == task.get_absolute_url()


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("url_name", "on_task"),
    [("router_job_retry", False), ("router_job_restart", False), ("router_task_reset", True)],
)
def test_sending_again_is_refused_once_the_images_are_deleted(
    client: Client, url_name: str, on_task: bool
):
    task = create_delivery(RouterJob.Status.FAILURE, files_deleted=True)
    client.force_login(_staff())

    response = client.post(reverse(url_name, args=[task.pk if on_task else task.job.pk]))

    assert response.status_code == 400
    task.refresh_from_db()
    assert task.status == RouterTask.Status.FAILURE
    assert task.queued_job is None


@pytest.mark.django_db
def test_job_page_explains_that_deleted_images_cannot_be_sent_again(client: Client):
    task = create_delivery(RouterJob.Status.FAILURE, files_deleted=True)
    client.force_login(_staff())

    job_page = client.get(reverse("router_job_detail", args=[task.job.pk]))
    task_page = client.get(reverse("router_task_detail", args=[task.pk]))

    assertContains(job_page, "have the PACS forward it to the router")
    assertNotContains(job_page, "Retry Failed Tasks")
    assertNotContains(job_page, "Restart Entire Job")
    assertNotContains(task_page, "Reset Task")
