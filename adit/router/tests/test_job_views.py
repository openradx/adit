import pytest
from adit_radis_shared.accounts.factories import UserFactory
from adit_radis_shared.accounts.models import User
from django.conf import settings
from django.test import Client
from django.urls import reverse
from pytest_django.asserts import assertContains

from adit.router import urls as router_urls
from adit.router.factories import RouterJobFactory, RoutingRuleFactory
from adit.router.mixins import RouterStaffRequiredMixin
from adit.router.models import RouterJob


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
