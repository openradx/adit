# DICOM Router Stage 4: Staff Pages and Docs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give staff web pages for the DICOM router (routing rules with their deliveries, a rule form, router jobs and tasks with the usual job actions) and document the router for administrators.

**Architecture:** The router app gets the same kind of pages as the other job apps, all behind one staff-only mixin.

- **Rules.** A rule list with delivery counts by status, annotated in one query. A rule page with the rule's deliveries, enable/disable and "retry failed deliveries". Create and edit pages built on one `RoutingRuleForm` that the Django admin uses too, with the mass transfer CodeMirror filter editor and an in-app help dialog.
- **Jobs and tasks.** A router job list filtered by rule and status, and job and task pages that subclass the generic core views. The action hooks of `RouterJob`/`RouterTask` remove Delete, Verify and Resume and refuse Retry, Restart and Reset once a batch's images are deleted, so the core views enforce this on the server.
- **Wiring and docs.** A staff-only "Router" main menu item, a Router row in the Admin Section's job overview, and a "DICOM Router" section in the admin guide.

**Tech Stack:** Django 6.1 class-based views, django-tables2, django-filter with crispy forms (Bootstrap 5), django-cotton components, HTMX (help dialog), django-codemirror, pytest-django, factory_boy, pytest-playwright.

**Spec:** `docs/superpowers/specs/2026-09-30-dicom-router-design.md`
- Stage 4 in §10.
- §5.2 rule editing, §6 staff pages, and the docs bullets of §7.
- The model and form tests of §12.
- The controller's stage 4 design rulings (1–16, plus additions (a)–(d) from the stage 3 final review) decide where the spec is silent. They are folded into the Global Constraints and the tasks below.

## Global Constraints

- **Code style:**
  - Google Python style, ruff line length 100, pyright in basic mode (django-stubs are installed, so Django APIs are typed).
  - Comments only where the code can't speak for itself, and they explain why.
  - No history in comments or docstrings.
- **Templates:** djlint (profile django, line length 120). Pages extend `core/core_layout.html` and use `<c-page-heading>`, `<c-table-heading>`, crispy forms and django-tables2 the way the batch transfer pages do. Django 6 `format_html()` refuses calls without arguments.
- **Django fields:** a CharField uses `blank=True` (never `null=True`), plus `default=""` when it has no initial value. Other fields use `blank=True, null=True`. This stage adds no model field and no migration.
- **Invariants:** use `assert` for internal invariants. ADIT never runs with `python -O`.
- **Access:** every router view requires `is_staff` through `RouterStaffRequiredMixin` (`adit/router/mixins.py`), also for a non-staff user who owns router jobs as a rule's creator. Anonymous users are redirected to the login page, non-staff users get 403. This covers the actions and the HTMX help view too.
- **URLs**, mounted at `router/` in `adit/urls.py`:
  - `router_rule_list` (the menu target), `router_rule_create`, `router_rule_detail`, `router_rule_update`, `router_rule_toggle` (POST, sets `enabled` to the posted state; enabling validates the rule), `router_rule_retry_failed` (POST), `router_help` (HTMX).
  - `router_job_list`, `router_job_detail`, `router_job_cancel`, `router_job_retry`, `router_job_restart`, `router_task_detail`, `router_task_reset`, `router_task_kill`.
- **No delete, verify or resume:** there are no such URLs. `RouterJob.is_deletable`, `RouterTask.is_deletable` and `RouterJob.is_resumable` are always False, and the `router_extras` control panel tags pass only the cancel/retry/restart and reset/kill URL names.
- **Files guard:** Retry, Restart and Reset are refused once the batch folder is deleted (`RouterBatch.files_deleted_at` is set). `RouterJob.is_retriable`, `RouterJob.is_restartable` and `RouterTask.is_resettable` add that condition, and the core action views answer 400 (`SuspiciousOperation`) when the hook is False.
- **Rule editing:**
  - `pseudonymize` and `pseudonym_salt` can't change once a rule has a job.
  - Only switching pseudonymization off needs `router.can_transfer_unpseudonymized`: a new unpseudonymized rule, or an existing rule switched from on to off. Editing or enabling an unpseudonymized rule needs no permission.
  - One `RoutingRuleForm` (`adit/router/forms.py`) serves the staff pages and the Django admin. `RoutingRule.clean()` stays the validation authority. `created_by` is the staff user who creates the rule.
  - Senders are managed only in the Django admin. Batches, jobs and tasks stay read-only there.
- **Unchanged behaviour:** the core job and task views behave as before for every other app, and the mass transfer form looks as before.
- **Docs in this PR:** keep `AGENTS.md` (which `CLAUDE.md` links to), `README.md`, `docs/user-docs/admin-guide.md`, `docs/user-docs/features.md` and `docs/dev-docs/architecture.md` in sync.
- **Branch:** `feat/dicom-router-pages`, stacked on `feat/dicom-router-rules` (stage 3, including its fix wave). The controller commits this plan first.
- **Running tests and lint:**
  - Tests run in the web container: `uv run cli test -- <paths>`. Use `-m "not acceptance"` for everything but the acceptance tests.
  - Lint runs on the host: `uv run cli lint`.
- **Commits:** every commit message ends with the attribution trailer lines that the executing session's harness specifies.

## Review Focus

These are the inputs most likely to bite a person using the router pages, and the test that pins each one:

1. **Editing a rule that has already sent studies, in a browser.** A browser posts nothing for the disabled Pseudonymize and salt inputs. The save must apply the other changes and keep the pseudonymization, not fail with the permission error or the model's "can't change" error. Task 2: `test_locked_rule_saves_when_the_browser_leaves_out_its_disabled_fields`. Task 6: `test_editing_a_rule_with_deliveries_keeps_its_pseudonymization`, which covers a crafted POST as well.
2. **Opening the rule form.** The filter editor must show valid, indented JSON: the example for a new rule, the stored filters for an existing one (not `null`, and not a Python repr with single quotes and `True`). After a typo it must keep the typed text. Task 2: `test_new_rule_form_suggests_example_filters_as_indented_json`, `test_edit_form_shows_the_rules_filters_as_json`, `test_invalid_json_keeps_the_typed_text`.
3. **Opening a pending or canceled router job, or a pending task.** The core control panels would reverse the missing delete, verify or resume URL names and crash with `NoReverseMatch`. The pages must render and offer only the actions that exist. Task 5: `test_job_and_task_pages_offer_no_delete_verify_or_resume`.
4. **Switching off a rule that no longer validates**, for example after its destination lost C-STORE and STOW-RS support. Staff must always be able to stop a standing export. Task 4: `test_rule_that_no_longer_validates_can_still_be_disabled`.
5. **Following a cell of the Admin Section's job overview** (`?all=1&status=FA`). The router job list must show exactly the router jobs with that status. Task 3: `test_admin_section_links_router_jobs_by_status`.

## Plan Notes

- **Stage 3's fix wave.** Task 2 moves the permission check of the Django admin's `RoutingRuleAdminForm` into `RoutingRuleForm` as stage 3's fix wave left it: the `changed_data` check, per addition (c). If the fix wave changed that check again before this plan runs, move the check as it is then, without rewriting it. The fix wave's admin tests call `admin.get_form(...)` and then the returned class, so they keep working.
- **"The mass transfer CodeMirror editor with its help" (§6).** The mass transfer field help explains C-FIND and PACS-side matching, which doesn't apply to images the router received. The router form uses the same widget with its own help text, which lists the same filter keys and matching rules. The help dialog (ruling 13) carries the details.
- **Retry failed deliveries (§6, ruling 8).** Task 1 extracts the core Retry view's steps into `DicomJob.retry()`, and the core view calls it, so the rule-level retry and the job-level Retry run the same code. The other apps' Retry view tests keep covering the core view.
- **Read-only salt (§5.2, ruling 4).** On the staff pages, Pseudonymize and the salt are disabled form fields. The Django admin keeps showing them as read-only fields (stage 3's `get_readonly_fields`). The shared form handles both.
- **Toggle (controller ruling on the stage 4 open question).** `router_rule_toggle` stays one POST URL, but the POST carries the target state: the button sends `enabled=1` (Enable Rule) or `enabled=0` (Disable Rule). A missing or other value is refused with 400. Posting the state the rule already has changes nothing and shows an info message, so a stale page can't flip a rule the wrong way. Disabling never validates (Review Focus 4). Enabling runs `rule.full_clean()` first; when the rule doesn't validate, it stays disabled and the page names the problems and points to Edit Rule.
- **Task order.** The rule pages (Task 4) come before the job pages (Task 5). Until Task 5 points `get_absolute_url` at the staff pages, the job IDs on a rule page link to the Django admin pages, which still work.
- **Extra navigation.** The rules page also links to the router job list, and every page links back. The spec's table names no such buttons; they keep the job list reachable, since the menu item targets the rules.
- **`CLAUDE.md`** (§7) is a symlink to `AGENTS.md`, so Task 7 edits `AGENTS.md`. Task 7 also removes the stage 3 caveat that failed deliveries can't be retried from ADIT yet (addition (b)).

---

### Task 1: What a router job allows, and retrying a rule's failed deliveries

**Files:**
- Modify: `adit/core/models.py` (`DicomJob.retry`)
- Modify: `adit/core/views.py` (`DicomJobRetryView.post`)
- Modify: `adit/router/models.py` (`RoutingRule`, `RouterJob`, `RouterTask`)
- Modify: `adit/router/factories.py` (`RouterJobFactory.owner`)
- Create: `adit/router/utils/testing_helpers.py`
- Test: `adit/core/tests/test_models.py`, `adit/router/tests/test_models.py`

**Interfaces:**
- Consumes: `DicomJob.reset_tasks(only_failed=True)`, `RouterJob.queue_pending_tasks()`, `RouterBatch.files_deleted_at`, and the router factories.
- Produces:
  - `DicomJob.retry(self) -> None`. Its precondition is `self.is_retriable`. It resets the failed tasks, sets the job to `PENDING`, saves it and queues its pending tasks.
  - `RouterJob.is_deletable` and `RouterJob.is_resumable` (properties, always `False`).
  - `RouterJob.is_retriable` and `RouterJob.is_restartable` (properties): the base condition and `self.batch.files_deleted_at is None`.
  - `RouterTask.is_deletable` (always `False`) and `RouterTask.is_resettable` (the base condition and `self.job.batch.files_deleted_at is None`).
  - `RoutingRule.retry_failed_deliveries(self) -> tuple[int, int]`, which returns `(retried, not_retriable)`.
  - `RouterJobFactory` builds jobs owned by their rule's creator, as `decide_batch` does.
  - `create_delivery(status: str, *, files_deleted: bool = False, **job_kwargs) -> RouterTask` in `adit/router/utils/testing_helpers.py`: a router job and its one task, both with `status`.

- [ ] **Step 1: Write the failing tests**

In `adit/core/tests/test_models.py`, add this test as the first method of `class TestDicomJob:`:

```python
    @pytest.mark.django_db
    def test_retry_resets_and_queues_only_the_failed_tasks(self):
        job = ExampleTransferJobFactory.create(status=DicomJob.Status.FAILURE)
        failed = ExampleTransferTaskFactory.create(
            job=job, status=DicomTask.Status.FAILURE, attempts=3, message="Failed"
        )
        succeeded = ExampleTransferTaskFactory.create(job=job, status=DicomTask.Status.SUCCESS)

        job.retry()

        job.refresh_from_db()
        failed.refresh_from_db()
        succeeded.refresh_from_db()
        assert job.status == DicomJob.Status.PENDING
        assert (failed.status, failed.attempts, failed.message) == (DicomTask.Status.PENDING, 0, "")
        assert failed.queued_job is not None
        assert succeeded.status == DicomTask.Status.SUCCESS
        assert succeeded.queued_job is None
```

Create `adit/router/utils/testing_helpers.py`. The tests import it, so it is part of this step:

```python
from typing import Any

from django.utils import timezone

from ..factories import RouterBatchFactory, RouterJobFactory, RouterTaskFactory
from ..models import RouterTask


def create_delivery(status: str, *, files_deleted: bool = False, **job_kwargs: Any) -> RouterTask:
    """Create a router job and its one task, both with *status*.

    The images of their batch are in the spool unless *files_deleted* is set.
    """
    batch = RouterBatchFactory.create(files_deleted_at=timezone.now() if files_deleted else None)
    job = RouterJobFactory.create(status=status, batch=batch, **job_kwargs)
    return RouterTaskFactory.create(job=job, status=status)
```

In `adit/router/tests/test_models.py`, add this import after `from adit.router.models import ...`:

```python
from adit.router.utils.testing_helpers import create_delivery
```

Then append these tests to the end of the file:

```python
@pytest.mark.django_db
def test_router_jobs_and_tasks_are_never_deleted():
    task = create_delivery(RouterJob.Status.PENDING)

    assert not task.job.is_deletable
    assert not task.is_deletable


@pytest.mark.django_db
def test_canceled_router_jobs_are_restarted_not_resumed():
    task = create_delivery(RouterJob.Status.CANCELED)

    assert not task.job.is_resumable
    assert task.job.is_restartable


@pytest.mark.django_db
def test_failed_delivery_can_be_sent_again_while_its_images_are_in_the_spool():
    task = create_delivery(RouterJob.Status.FAILURE)

    assert task.job.is_retriable
    assert task.job.is_restartable
    assert task.is_resettable


@pytest.mark.django_db
def test_delivery_whose_images_were_deleted_cannot_be_sent_again():
    task = create_delivery(RouterJob.Status.FAILURE, files_deleted=True)

    assert not task.job.is_retriable
    assert not task.job.is_restartable
    assert not task.is_resettable


@pytest.mark.django_db
def test_retrying_a_rules_failed_deliveries_skips_those_without_images():
    rule = RoutingRuleFactory.create()
    retriable = create_delivery(RouterJob.Status.FAILURE, rule=rule)
    images_deleted = create_delivery(RouterJob.Status.FAILURE, rule=rule, files_deleted=True)
    succeeded = create_delivery(RouterJob.Status.SUCCESS, rule=rule)
    other_rule = create_delivery(RouterJob.Status.FAILURE)

    assert rule.retry_failed_deliveries() == (1, 1)

    retried_task = RouterTask.objects.get(pk=retriable.pk)
    assert retried_task.status == RouterTask.Status.PENDING
    assert retried_task.queued_job is not None
    assert RouterJob.objects.get(pk=retriable.job.pk).status == RouterJob.Status.PENDING
    for task, status in (
        (images_deleted, RouterTask.Status.FAILURE),
        (succeeded, RouterTask.Status.SUCCESS),
        (other_rule, RouterTask.Status.FAILURE),
    ):
        assert RouterTask.objects.get(pk=task.pk).status == status
        assert RouterJob.objects.get(pk=task.job.pk).status == status
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run cli test -- adit/core/tests/test_models.py adit/router/tests/test_models.py -v`
Expected: FAIL:
- `test_retry_resets_and_queues_only_the_failed_tasks` with `AttributeError: 'ExampleTransferJob' object has no attribute 'retry'`.
- `test_retrying_a_rules_failed_deliveries_skips_those_without_images` with `AttributeError: 'RoutingRule' object has no attribute 'retry_failed_deliveries'`.
- `test_router_jobs_and_tasks_are_never_deleted`, `test_canceled_router_jobs_are_restarted_not_resumed` and `test_delivery_whose_images_were_deleted_cannot_be_sent_again` with `assert not True`, because the base hooks still allow Delete, Resume, Retry, Restart and Reset.

`test_failed_delivery_can_be_sent_again_while_its_images_are_in_the_spool` already passes. It checks that the guard doesn't block deliveries whose images are still there. The existing tests pass.

- [ ] **Step 3: Extract the core Retry steps into `DicomJob.retry`**

In `adit/core/models.py`, add this method to `DicomJob`, right after `reset_tasks`:

```python
    def retry(self) -> None:
        """Reset the failed tasks and queue them again."""
        assert self.is_retriable
        self.reset_tasks(only_failed=True)
        self.status = DicomJob.Status.PENDING
        self.save()
        self.queue_pending_tasks()
```

In `adit/core/views.py`, `DicomJobRetryView.post`, replace these lines:

```python
        job.reset_tasks(only_failed=True)

        job.status = DicomJob.Status.PENDING
        job.save()

        job.queue_pending_tasks()
```

with:

```python
        job.retry()
```

- [ ] **Step 4: Add the router hooks and the rule-level retry**

In `adit/router/models.py`:
- Change `from django.db import models` to `from django.db import models, transaction`.
- In `RoutingRule`, add this method right after `get_filters`:

```python
    def retry_failed_deliveries(self) -> tuple[int, int]:
        """Retry the rule's failed deliveries whose images are still in the spool.

        Returns how many deliveries were retried and how many could not be, because the
        images of their batch were deleted.
        """
        retried = not_retriable = 0
        with transaction.atomic():
            failed = self.jobs.filter(status=DicomJob.Status.FAILURE).select_related("batch")
            for job in failed:
                if job.is_retriable:
                    job.retry()
                    retried += 1
                else:
                    not_retriable += 1
        return retried, not_retriable
```

- In `RouterJob`, add these properties right after `get_absolute_url`:

```python
    @property
    def is_deletable(self) -> bool:
        # Canceling stops a delivery and keeps its history.
        return False

    @property
    def is_resumable(self) -> bool:
        # A router job has one task, so Restart covers a canceled job.
        return False

    @property
    def is_retriable(self) -> bool:
        return super().is_retriable and self.batch.files_deleted_at is None

    @property
    def is_restartable(self) -> bool:
        return super().is_restartable and self.batch.files_deleted_at is None
```

- In `RouterTask`, add these properties right after `get_absolute_url`:

```python
    @property
    def is_deletable(self) -> bool:
        # Like its job, a delivery task keeps its history.
        return False

    @property
    def is_resettable(self) -> bool:
        return super().is_resettable and self.job.batch.files_deleted_at is None
```

In `adit/router/factories.py`, in `RouterJobFactory`, add this line after `rule = factory.SubFactory(RoutingRuleFactory)`:

```python
    owner = factory.LazyAttribute(lambda job: job.rule.created_by)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run cli test -- adit/core/tests/test_models.py adit/router/tests/test_models.py -v`
Expected: PASS.

Run: `uv run cli test -- adit/batch_transfer/tests/test_views.py adit/batch_query/tests/test_views.py adit/selective_transfer/tests/test_views.py -k retry -v`
Expected: PASS. The core Retry view behaves as before.

- [ ] **Step 6: Lint**

Run: `uv run cli lint`
Expected: no errors.

- [ ] **Step 7: Commit**

```bash
git add adit/core/models.py adit/core/views.py adit/core/tests/test_models.py \
  adit/router/models.py adit/router/factories.py adit/router/utils/testing_helpers.py \
  adit/router/tests/test_models.py
git commit -m "Keep router job history and refuse resending deleted images"
```

---

### Task 2: One routing rule form for the staff pages and the Django admin

**Files:**
- Create: `adit/router/forms.py`
- Modify: `adit/router/admin.py` (`RoutingRuleAdminForm` moves out, `RoutingRuleAdmin` uses the shared form)
- Test: `adit/router/tests/test_forms.py` (new), `adit/router/tests/test_admin.py`

**Interfaces:**
- Consumes: `RoutingRule` and its `clean()`, `RouterJobFactory`, `RoutingRuleFactory`, `DicomServerFactory`, `parse_filters`, and `add_permission` from `adit_radis_shared.common.utils.testing_helpers`.
- Produces, in `adit/router/forms.py`:
  - `FILTERS_EXAMPLE: list[dict]`, the filters a new rule's editor starts with.
  - `FILTERS_HELP_TEXT: str` and `LOCKED_HELP_TEXT: str`.
  - `FiltersJSONField(forms.JSONField)`, which renders indented JSON.
  - `RoutingRuleForm(forms.ModelForm)` with `__init__(self, *args, user: User, **kwargs)`. Its fields are `name`, `enabled`, `destination`, `filters_json`, `pseudonymize`, `pseudonym_salt`, `trial_protocol_id` and `trial_protocol_name`. A crispy `helper` has one submit input, `save`, labelled "Save Rule".
  - `RoutingRuleAdmin.form = RoutingRuleForm`. `RoutingRuleAdmin.get_form()` returns a subclass that passes `user=request.user`. `RoutingRuleAdminForm` no longer exists.

- [ ] **Step 1: Write the failing tests**

Create `adit/router/tests/test_forms.py`:

```python
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
```

In `adit/router/tests/test_admin.py`, add this import after `from adit.router.factories import ...`:

```python
from adit.router.forms import RoutingRuleForm
```

Then append this test to the end of the file:

```python
@pytest.mark.django_db
def test_admin_edits_rules_with_the_form_of_the_router_pages():
    admin = RoutingRuleAdmin(RoutingRule, AdminSite())
    rule = RoutingRuleFactory.create()

    form_class = admin.get_form(_request(_rule_editor()), rule, change=True)

    assert issubclass(form_class, RoutingRuleForm)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run cli test -- adit/router/tests/test_forms.py adit/router/tests/test_admin.py -v`
Expected: FAIL, collection errors with `ModuleNotFoundError: No module named 'adit.router.forms'`.

- [ ] **Step 3: Write the shared form**

Create `adit/router/forms.py`:

```python
import json
from typing import Any

from adit_radis_shared.accounts.models import User
from codemirror.widgets import CodeMirror
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit
from django import forms
from django.forms.fields import InvalidJSONInput

from .models import RoutingRule

FILTERS_EXAMPLE = [
    {"mode": "include", "modality": "CT", "min_age": 20, "max_age": 30},
    {"mode": "exclude", "series_description": "*localizer*"},
]

FILTERS_HELP_TEXT = (
    "A JSON array of filter objects. Each filter can have: mode ('include' or 'exclude', "
    "default 'include'), modality, institution_name, apply_institution_on_study, "
    "study_description, series_description, series_number, min_age, max_age and "
    "min_number_of_series_related_instances. A series is sent when it matches an include "
    "filter and no exclude filter; at least one include filter is required. String criteria "
    "support the DICOM wildcards * and ? and must match the whole value: case-sensitively "
    "on include filters, case-insensitively on exclude filters. The Help button explains "
    "more."
)

LOCKED_HELP_TEXT = "Fixed once the rule has sent studies. Create a new rule to change it."


class FiltersJSONField(forms.JSONField):
    def prepare_value(self, value: Any) -> Any:
        # Indented, so the editor shows the filters the way staff write them.
        if isinstance(value, InvalidJSONInput):
            return value
        return json.dumps(value, indent=2, ensure_ascii=False, cls=self.encoder)


class RoutingRuleForm(forms.ModelForm):
    """The routing rule form of the router pages, also used by the Django admin."""

    filters_json = FiltersJSONField(
        label="Filters (JSON)",
        widget=CodeMirror(mode={"name": "javascript", "json": True}),
        help_text=FILTERS_HELP_TEXT,
    )

    class Meta:
        model = RoutingRule
        fields = (
            "name",
            "enabled",
            "destination",
            "filters_json",
            "pseudonymize",
            "pseudonym_salt",
            "trial_protocol_id",
            "trial_protocol_name",
        )
        labels = {"trial_protocol_id": "Trial protocol ID"}
        help_texts = {
            "enabled": "Only enabled rules route the studies that arrive.",
            "pseudonym_salt": (
                "The same salt gives a patient the same pseudonym. Keep the pre-filled salt, "
                "or paste the salt of a mass transfer job to give its patients the same "
                "pseudonyms."
            ),
        }

    def __init__(self, *args: Any, user: User, **kwargs: Any) -> None:
        self.user = user
        super().__init__(*args, **kwargs)

        if self.instance.pk is None and self.initial.get("filters_json") is None:
            self.initial["filters_json"] = FILTERS_EXAMPLE

        if self.instance.pk is not None and self.instance.jobs.exists():
            # A patient must keep the same pseudonym under a rule. Disabled fields ignore
            # what is posted for them.
            for name in ("pseudonymize", "pseudonym_salt"):
                # The Django admin shows these two as read-only fields instead.
                if name in self.fields:
                    self.fields[name].disabled = True
                    self.fields[name].help_text = LOCKED_HELP_TEXT

        self.helper = FormHelper()
        self.helper.add_input(Submit("save", "Save Rule"))

    def clean(self) -> dict[str, Any]:
        cleaned_data = super().clean()
        assert cleaned_data is not None
        if cleaned_data.get("pseudonymize") is False and not self.user.has_perm(
            "router.can_transfer_unpseudonymized"
        ):
            # Only turning pseudonymization off needs the permission: a new rule
            # saved that way, or an existing one flipping from True to False.
            # Editing, enabling or disabling an already-unpseudonymized rule doesn't.
            is_new = self.instance.pk is None
            switched_off = "pseudonymize" in self.changed_data
            if is_new or switched_off:
                self.add_error(
                    "pseudonymize",
                    "You are not allowed to send studies without pseudonymization.",
                )
        return cleaned_data
```

Before you save, compare `clean()` with `RoutingRuleAdminForm.clean()` in `adit/router/admin.py`. It must make the same decision with the same message. Only the user attribute differs: the admin form reads `request_user`, this form reads `user`, which is always given.

- [ ] **Step 4: Move the Django admin onto the shared form**

In `adit/router/admin.py`:
- Replace the imports at the top with:

```python
from typing import Any, cast

from adit_radis_shared.accounts.models import User
from django.contrib import admin
from django.http import HttpRequest

from adit.core.admin import DicomJobAdmin, DicomTaskAdmin

from .forms import RoutingRuleForm
from .models import RouterBatch, RouterJob, RouterSender, RouterSettings, RouterTask, RoutingRule
```

- Delete the whole `class RoutingRuleAdminForm(forms.ModelForm):`, from its `class` line through its `return self.cleaned_data`.
- In `RoutingRuleAdmin`, change `form = RoutingRuleAdminForm` to `form = RoutingRuleForm`, and replace its `get_form` method with:

```python
    def get_form(
        self, request: HttpRequest, obj: Any = None, change: bool = False, **kwargs: Any
    ) -> Any:
        form_class = cast(type[RoutingRuleForm], super().get_form(request, obj, change, **kwargs))
        user = cast(User, request.user)

        # The admin creates the form itself, so the subclass hands over the user.
        class UserRoutingRuleForm(form_class):
            def __init__(self, *args: Any, **form_kwargs: Any) -> None:
                super().__init__(*args, user=user, **form_kwargs)

        return UserRoutingRuleForm
```

Leave `get_readonly_fields`, `save_model` and the rest of `admin.py` as they are.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run cli test -- adit/router/tests/test_forms.py adit/router/tests/test_admin.py -v`
Expected: PASS. This includes stage 3's admin tests: refusing a new unpseudonymized rule, allowing to disable an unpseudonymized rule, read-only pseudonymization, and the rest.

- [ ] **Step 6: Lint**

Run: `uv run cli lint`
Expected: no errors.

- [ ] **Step 7: Commit**

```bash
git add adit/router/forms.py adit/router/admin.py adit/router/tests/test_forms.py \
  adit/router/tests/test_admin.py
git commit -m "Share one routing rule form between the router pages and the admin"
```

---

### Task 3: Staff-only router job list and the Admin Section's job overview

**Files:**
- Create: `adit/router/mixins.py`
- Create: `adit/router/filters.py`
- Create: `adit/router/tables.py`
- Create: `adit/router/views.py`
- Create: `adit/router/urls.py`
- Create: `adit/router/templates/router/router_job_list.html`
- Modify: `adit/urls.py` (mount the router URLs)
- Modify: `adit/router/apps.py` (job stats collector)
- Test: `adit/router/tests/test_job_views.py` (new)

**Interfaces:**
- Consumes: `RouterJobFactory` and `RoutingRuleFactory` (jobs owned by the rule's creator, Task 1), `TransferJobTable` (`adit/core/tables.py`), `JobStats` and `register_job_stats_collector` (`adit/core/site.py`), and `with_form_helper` (`adit_radis_shared.common.types`).
- Produces:
  - `RouterStaffRequiredMixin(LoginRequiredMixin, UserPassesTestMixin)` in `adit/router/mixins.py`, the first base of every router view.
  - `RouterJobFilterFormHelper(params: QueryDict)` and `RouterJobFilter` (fields `rule` and `status`) in `adit/router/filters.py`.
  - `RouterJobTable(TransferJobTable)` in `adit/router/tables.py`, with the columns `id`, `rule`, `status`, `message` and `created`.
  - `RouterJobListView` in `adit/router/views.py`, and `adit/router/urls.py` with the URL name `router_job_list` (`/router/jobs/`).
  - A "Router" row in the Admin Section's job overview, linking to `router_job_list`.

- [ ] **Step 1: Write the failing tests**

Create `adit/router/tests/test_job_views.py`:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run cli test -- adit/router/tests/test_job_views.py -v`
Expected: FAIL, a collection error with `ImportError: cannot import name 'urls' from 'adit.router'`.

- [ ] **Step 3: Write the staff mixin**

Create `adit/router/mixins.py`:

```python
from adit_radis_shared.common.types import AuthenticatedHttpRequest
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin


class RouterStaffRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Lets only staff in, also a non-staff user who owns router jobs as a rule's creator.

    A routing rule is a standing export of patient data, so its pages, its jobs and their
    actions are for staff only.
    """

    request: AuthenticatedHttpRequest

    def test_func(self) -> bool:
        return self.request.user.is_staff
```

- [ ] **Step 4: Write the two-field filter and the job table**

Create `adit/router/filters.py`:

```python
import django_filters
from adit_radis_shared.common.types import with_form_helper
from crispy_forms.bootstrap import FieldWithButtons
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Div, Field, Hidden, Layout, Submit
from django.http import HttpRequest, QueryDict

from .models import RouterJob

FILTER_FIELD_TEMPLATE = "common/_filter_set_field.html"


class RouterJobFilterFormHelper(FormHelper):
    """Renders the rule and the status filter side by side, styled like the other filters.

    SingleFilterFieldFormHelper only takes one field. Like it, this helper keeps the other
    query parameters, such as the page size, as hidden fields.
    """

    def __init__(self, params: QueryDict, **kwargs):
        super().__init__(**kwargs)
        self.form_method = "get"
        self.disable_csrf = True
        self.layout = Layout(
            Div(
                Field(
                    "rule", css_class="form-select form-select-sm", template=FILTER_FIELD_TEMPLATE
                ),
                FieldWithButtons(
                    Field("status", css_class="form-select form-select-sm"),
                    Submit("", "Filter", css_class="btn-secondary btn-sm"),
                    template=FILTER_FIELD_TEMPLATE,
                ),
                css_class="d-flex gap-3",
            ),
            Div(
                *(
                    Hidden(key, value)
                    for key, value in params.items()
                    if key not in ("rule", "status", "page")
                )
            ),
        )


class RouterJobFilter(django_filters.FilterSet):
    request: HttpRequest

    class Meta:
        model = RouterJob
        fields = ("rule", "status")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        with_form_helper(self.form).helper = RouterJobFilterFormHelper(self.request.GET)
```

Create `adit/router/tables.py`:

```python
from adit.core.tables import TransferJobTable

from .models import RouterJob


class RouterJobTable(TransferJobTable):
    class Meta(TransferJobTable.Meta):
        model = RouterJob
        fields = ("id", "rule", "status", "message", "created")
        empty_text = "No router jobs to show"
```

- [ ] **Step 5: Write the job list view, its URL and its template**

Create `adit/router/views.py`:

```python
from adit_radis_shared.common.mixins import PageSizeSelectMixin
from django.db.models import QuerySet
from django_filters.views import FilterView
from django_tables2 import SingleTableMixin

from .filters import RouterJobFilter
from .mixins import RouterStaffRequiredMixin
from .models import RouterJob
from .tables import RouterJobTable


class RouterJobListView(
    RouterStaffRequiredMixin, SingleTableMixin, PageSizeSelectMixin, FilterView
):
    model = RouterJob
    table_class = RouterJobTable
    filterset_class = RouterJobFilter
    template_name = "router/router_job_list.html"

    def get_queryset(self) -> QuerySet[RouterJob]:
        # Staff see every router job, so the Admin Section's ?all=1 changes nothing here.
        return RouterJob.objects.select_related("rule").order_by("-created")
```

Create `adit/router/urls.py`:

```python
from django.urls import path

from .views import RouterJobListView

urlpatterns = [
    path("jobs/", RouterJobListView.as_view(), name="router_job_list"),
]
```

Create `adit/router/templates/router/router_job_list.html`:

```django
{% extends "core/core_layout.html" %}
{% load crispy from crispy_forms_tags %}
{% load render_table from django_tables2 %}
{% block title %}
    Router Jobs
{% endblock title %}
{% block heading %}
    <c-page-heading title="Router Jobs" />
{% endblock heading %}
{% block content %}
    <c-table-heading>
        <c-slot name="right">
            {% crispy filter.form %}
        </c-slot>
    </c-table-heading>
    {% render_table table %}
{% endblock content %}
```

In `adit/urls.py`, add this line after `path("dicom-explorer/", include("adit.dicom_explorer.urls")),`:

```python
    path("router/", include("adit.router.urls")),
```

- [ ] **Step 6: Count router jobs in the Admin Section**

In `adit/router/apps.py`, replace `register_app` with:

```python
def register_app():
    from adit.core.site import JobStats, register_dicom_processor, register_job_stats_collector

    from .models import RouterJob, RouterTask
    from .processors import RouterTaskProcessor

    register_dicom_processor(get_model_label(RouterTask), RouterTaskProcessor)

    def collect_job_stats() -> JobStats:
        counts: dict[RouterJob.Status, int] = {}
        for status in RouterJob.Status:
            counts[status] = RouterJob.objects.filter(status=status).count()
        return JobStats("Router", "router_job_list", counts)

    register_job_stats_collector(collect_job_stats)
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `uv run cli test -- adit/router/tests/test_job_views.py -v`
Expected: PASS.

- [ ] **Step 8: Lint**

Run: `uv run cli lint`
Expected: no errors.

- [ ] **Step 9: Commit**

```bash
git add adit/router/mixins.py adit/router/filters.py adit/router/tables.py adit/router/views.py \
  adit/router/urls.py adit/router/templates/router/router_job_list.html adit/urls.py \
  adit/router/apps.py adit/router/tests/test_job_views.py
git commit -m "List router jobs for staff and count them in the Admin Section"
```

---

### Task 4: Rule list, rule page, enabling and disabling, and retrying failed deliveries

**Files:**
- Modify: `adit/router/models.py` (`RoutingRule.get_absolute_url`)
- Modify: `adit/router/filters.py` (`RoutingRuleJobFilter`)
- Modify: `adit/router/tables.py` (rule tables, linked rule column)
- Modify: `adit/router/views.py` (rule views)
- Modify: `adit/router/urls.py`
- Modify: `adit/router/apps.py` (main menu item)
- Create: `adit/router/templates/router/routing_rule_list.html`
- Create: `adit/router/templates/router/routing_rule_detail.html`
- Modify: `adit/router/templates/router/router_job_list.html` (link to the rules)
- Test: `adit/router/tests/test_rule_views.py` (new), `adit/router/tests/test_models.py`

**Interfaces:**
- Consumes:
  - From Task 1: `RoutingRule.retry_failed_deliveries() -> tuple[int, int]` and `create_delivery(...)`.
  - From Task 3: `RouterStaffRequiredMixin`, `RouterJobListView`, `RouterJobFilter`, `RouterJobTable`, and the URL name `router_job_list`.
  - `RecordIdColumn` and `TransferJobTable` (`adit/core/tables.py`), `DicomJobFilter` (`adit/core/filters.py`), `dicom_job_status_css_class` (`adit/core/templatetags/core_extras.py`), and `MainMenuItem`/`register_main_menu_item` (`adit_radis_shared.common.site`).
- Produces:
  - `RoutingRule.get_absolute_url() -> str`, which returns `/router/rules/<pk>/`.
  - In `adit/router/tables.py`: `DELIVERY_STATUSES` (every job status but `UNVERIFIED`), `with_deliveries(rules: QuerySet[RoutingRule]) -> QuerySet[RoutingRule]`, `RoutingRuleTable` and `RoutingRuleJobTable`. `with_deliveries` annotates `deliveries_<status value>` (for example `deliveries_FA`) and `last_match`.
  - `RoutingRuleJobFilter` in `adit/router/filters.py`, a status-only filter for a rule's jobs.
  - The views `RoutingRuleListView`, `RoutingRuleDetailView`, `RoutingRuleToggleView` and `RoutingRuleRetryFailedView`. The rule page's context holds `rule`, `filter`, `table`, `filters_json` (indented JSON) and `failed_count`.
  - `RoutingRuleToggleView` takes the target state as POST `enabled`: `"1"` enables, `"0"` disables, anything else is a 400. Posting the current state changes nothing. Only enabling validates the rule.
  - The URL names `router_rule_list` (`/router/rules/`), `router_rule_detail`, `router_rule_toggle` and `router_rule_retry_failed`.
  - The staff-only "Router" main menu item, targeting `router_rule_list`.
  - The rule column of the router job list links to the rule.

- [ ] **Step 1: Write the failing tests**

In `adit/router/tests/test_models.py`, append:

```python
@pytest.mark.django_db
def test_rule_links_to_its_page():
    rule = RoutingRuleFactory.create()

    assert rule.get_absolute_url() == f"/router/rules/{rule.pk}/"
```

Create `adit/router/tests/test_rule_views.py`:

```python
import pytest
from adit_radis_shared.accounts.factories import UserFactory
from adit_radis_shared.accounts.models import User
from django.conf import settings
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from pytest_django.asserts import assertContains, assertNotContains

from adit.core.models import DicomServer
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run cli test -- adit/router/tests/test_rule_views.py adit/router/tests/test_models.py -v`
Expected: FAIL. The rule view tests fail with `NoReverseMatch: Reverse for 'router_rule_list' not found` (or `router_rule_detail`), and `test_rule_links_to_its_page` with `AttributeError: 'RoutingRule' object has no attribute 'get_absolute_url'`.

- [ ] **Step 3: Link rules to their page**

In `adit/router/models.py`, `RoutingRule`, add this method right after `__str__` (Django's style order puts it before `clean`):

```python
    def get_absolute_url(self) -> str:
        return reverse("router_rule_detail", args=[self.pk])
```

- [ ] **Step 4: Add the rule tables and the rule-level status filter**

In `adit/router/filters.py`, add `from adit.core.filters import DicomJobFilter` as the first-party import (after `from django.http import HttpRequest, QueryDict`, separated by a blank line), and append:

```python
class RoutingRuleJobFilter(DicomJobFilter):
    class Meta(DicomJobFilter.Meta):
        model = RouterJob
```

Replace `adit/router/tables.py` with:

```python
from urllib.parse import urlencode

import django_tables2 as tables
from django.db.models import Count, Max, Q, QuerySet
from django.urls import reverse
from django.utils.html import format_html, format_html_join

from adit.core.tables import RecordIdColumn, TransferJobTable
from adit.core.templatetags.core_extras import dicom_job_status_css_class

from .models import RouterJob, RouterTask, RoutingRule

# Router jobs start pending, so they are never unverified.
DELIVERY_STATUSES = [status for status in RouterJob.Status if status != RouterJob.Status.UNVERIFIED]


def with_deliveries(rules: QuerySet[RoutingRule]) -> QuerySet[RoutingRule]:
    """Annotate each rule with its delivery counts by status and its last match."""
    counts = {
        f"deliveries_{status.value}": Count("jobs", filter=Q(jobs__status=status))
        for status in DELIVERY_STATUSES
    }
    return rules.annotate(last_match=Max("jobs__created"), **counts)


class RoutingRuleTable(tables.Table):
    name = tables.Column(linkify=True)
    enabled = tables.Column(verbose_name="On/Off")
    destination = tables.Column()
    pseudonymize = tables.Column(verbose_name="Pseudonymizes")
    deliveries = tables.Column(empty_values=(), orderable=False)
    last_match = tables.DateTimeColumn(verbose_name="Last Match", default="—")

    class Meta:
        model = RoutingRule
        fields = ("name", "enabled", "destination", "pseudonymize", "deliveries", "last_match")
        empty_text = "No routing rules yet"
        attrs = {"class": "table table-bordered table-hover"}

    def render_enabled(self, value: bool) -> str:
        css_class, label = ("text-success", "On") if value else ("text-muted", "Off")
        return format_html('<span class="{}">{}</span>', css_class, label)

    def render_pseudonymize(self, value: bool) -> str:
        return "Yes" if value else "No"

    def render_deliveries(self, record: RoutingRule) -> str:
        job_list_url = reverse("router_job_list")
        links = format_html_join(
            " ",
            '<a href="{}" class="{} text-nowrap">{} {}</a>',
            (
                (
                    f"{job_list_url}?{urlencode({'rule': record.pk, 'status': status.value})}",
                    dicom_job_status_css_class(status),
                    status.label,
                    count,
                )
                for status in DELIVERY_STATUSES
                if (count := getattr(record, f"deliveries_{status.value}"))
            ),
        )
        return links or "—"


class RoutingRuleJobTable(tables.Table):
    id = RecordIdColumn(verbose_name="Job ID")
    closed_at = tables.DateTimeColumn(accessor="batch__closed_at", verbose_name="Closed At")
    patient_id = tables.Column(empty_values=(), orderable=False, verbose_name="Patient ID")
    pseudonym = tables.Column(empty_values=(), orderable=False)
    study = tables.Column(accessor="batch__study_instance_uid", verbose_name="Study Instance UID")
    images_sent = tables.Column(empty_values=(), orderable=False, verbose_name="Images Sent")

    class Meta:
        model = RouterJob
        fields = ("id", "closed_at", "patient_id", "pseudonym", "study", "images_sent", "status")
        empty_text = "No deliveries yet"
        attrs = {"class": "table table-bordered table-hover"}

    def render_patient_id(self, record: RouterJob) -> str:
        task = _delivery_task(record)
        return task.patient_id if task else "—"

    def render_pseudonym(self, record: RouterJob) -> str:
        task = _delivery_task(record)
        return task.pseudonym if task and task.pseudonym else "—"

    def render_images_sent(self, record: RouterJob) -> int | str:
        # The sent lists are cleared after ROUTER_SENT_LIST_RETENTION_DAYS.
        task = _delivery_task(record)
        return len(task.sent_instance_uids) if task and task.sent_instance_uids else "—"

    def render_status(self, value: str, record: RouterJob) -> str:
        css_class = dicom_job_status_css_class(record.status)
        return format_html('<span class="{} text-nowrap">{}</span>', css_class, value)


def _delivery_task(job: RouterJob) -> RouterTask | None:
    # The view prefetches the tasks; a router job has exactly one.
    return next(iter(job.tasks.all()), None)


class RouterJobTable(TransferJobTable):
    rule = tables.Column(linkify=True)

    class Meta(TransferJobTable.Meta):
        model = RouterJob
        fields = ("id", "rule", "status", "message", "created")
        empty_text = "No router jobs to show"
```

- [ ] **Step 5: Write the rule views and their URLs**

Replace `adit/router/views.py` with:

```python
import json
from typing import Any, cast

from adit_radis_shared.common.mixins import PageSizeSelectMixin, RelatedFilterMixin
from adit_radis_shared.common.types import AuthenticatedHttpRequest
from django.contrib import messages
from django.core.exceptions import SuspiciousOperation, ValidationError
from django.db.models import QuerySet
from django.http import HttpResponse
from django.shortcuts import redirect
from django.template.defaultfilters import pluralize
from django.views.generic import DetailView, View
from django.views.generic.detail import SingleObjectMixin
from django_filters.views import FilterView
from django_tables2 import SingleTableMixin, SingleTableView

from .filters import RouterJobFilter, RoutingRuleJobFilter
from .mixins import RouterStaffRequiredMixin
from .models import RouterJob, RoutingRule
from .tables import RouterJobTable, RoutingRuleJobTable, RoutingRuleTable, with_deliveries


class RouterJobListView(
    RouterStaffRequiredMixin, SingleTableMixin, PageSizeSelectMixin, FilterView
):
    model = RouterJob
    table_class = RouterJobTable
    filterset_class = RouterJobFilter
    template_name = "router/router_job_list.html"

    def get_queryset(self) -> QuerySet[RouterJob]:
        # Staff see every router job, so the Admin Section's ?all=1 changes nothing here.
        return RouterJob.objects.select_related("rule").order_by("-created")


class RoutingRuleListView(RouterStaffRequiredMixin, SingleTableView):
    model = RoutingRule
    table_class = RoutingRuleTable
    template_name = "router/routing_rule_list.html"

    def get_queryset(self) -> QuerySet[RoutingRule]:
        return with_deliveries(RoutingRule.objects.select_related("destination"))


class RoutingRuleDetailView(
    RouterStaffRequiredMixin,
    SingleTableMixin,
    RelatedFilterMixin,
    PageSizeSelectMixin,
    DetailView,
):
    model = RoutingRule
    context_object_name = "rule"
    template_name = "router/routing_rule_detail.html"
    table_class = RoutingRuleJobTable
    filterset_class = RoutingRuleJobFilter
    object: RoutingRule

    def get_queryset(self) -> QuerySet[RoutingRule]:
        return RoutingRule.objects.select_related("destination", "created_by")

    def get_filter_queryset(self) -> QuerySet[RouterJob]:
        return (
            self.object.jobs.select_related("batch")
            .prefetch_related("tasks")
            .order_by("-batch__closed_at", "-pk")
        )

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["filters_json"] = json.dumps(self.object.filters_json, indent=2)
        context["failed_count"] = self.object.jobs.filter(status=RouterJob.Status.FAILURE).count()
        return context


class RoutingRuleToggleView(RouterStaffRequiredMixin, SingleObjectMixin, View):
    model = RoutingRule

    def post(self, request: AuthenticatedHttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        rule = cast(RoutingRule, self.get_object())
        posted = request.POST.get("enabled")
        if posted not in ("0", "1"):
            raise SuspiciousOperation(f"Routing rule {rule.pk} can't be set to enabled={posted!r}.")
        enable = posted == "1"
        state = "enabled" if enable else "disabled"
        # The page posts the state its button shows, so a stale page can't flip a rule back.
        if rule.enabled == enable:
            messages.info(request, f'Routing rule "{rule.name}" is already {state}.')
            return redirect(rule)

        # Only enabling validates: a rule must stay easy to switch off, even one that no
        # longer validates, for example after its destination lost C-STORE support.
        if enable:
            try:
                rule.full_clean()
            except ValidationError as err:
                problems = " ".join(err.messages)
                messages.error(
                    request, f"The rule can't be enabled: {problems} Edit the rule first."
                )
                return redirect(rule)

        rule.enabled = enable
        rule.save(update_fields=["enabled", "updated"])
        messages.success(request, f'Routing rule "{rule.name}" is now {state}.')
        return redirect(rule)


class RoutingRuleRetryFailedView(RouterStaffRequiredMixin, SingleObjectMixin, View):
    model = RoutingRule

    def post(self, request: AuthenticatedHttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        rule = cast(RoutingRule, self.get_object())
        retried, not_retriable = rule.retry_failed_deliveries()
        studies = "that study" if not_retriable == 1 else "those studies"
        images_deleted = (
            "because the images were deleted from the spool; "
            f"have the PACS forward {studies} again."
        )
        if retried:
            message = f"{retried} failed deliver{pluralize(retried, 'y,ies')} will be retried."
            if not_retriable:
                message += f" {not_retriable} more could not be retried {images_deleted}"
            messages.success(request, message)
        elif not_retriable:
            messages.warning(request, f"No failed delivery could be retried {images_deleted}")
        else:
            messages.info(request, "This rule has no failed deliveries.")
        return redirect(rule)
```

Replace `adit/router/urls.py` with:

```python
from django.urls import path

from .views import (
    RouterJobListView,
    RoutingRuleDetailView,
    RoutingRuleListView,
    RoutingRuleRetryFailedView,
    RoutingRuleToggleView,
)

urlpatterns = [
    path("rules/", RoutingRuleListView.as_view(), name="router_rule_list"),
    path("rules/<int:pk>/", RoutingRuleDetailView.as_view(), name="router_rule_detail"),
    path("rules/<int:pk>/toggle/", RoutingRuleToggleView.as_view(), name="router_rule_toggle"),
    path(
        "rules/<int:pk>/retry-failed/",
        RoutingRuleRetryFailedView.as_view(),
        name="router_rule_retry_failed",
    ),
    path("jobs/", RouterJobListView.as_view(), name="router_job_list"),
]
```

- [ ] **Step 6: Write the rule templates and link the job list to the rules**

Create `adit/router/templates/router/routing_rule_list.html`:

```django
{% extends "core/core_layout.html" %}
{% load render_table from django_tables2 %}
{% load bootstrap_icon from common_extras %}
{% block title %}
    Routing Rules
{% endblock title %}
{% block heading %}
    <c-page-heading title="Routing Rules">
        <c-slot name="right">
            <a href="{% url 'router_job_list' %}" class="btn btn-secondary">
                {% bootstrap_icon "list" %}
                Router Jobs
            </a>
        </c-slot>
    </c-page-heading>
{% endblock heading %}
{% block content %}
    {% render_table table %}
{% endblock content %}
```

Create `adit/router/templates/router/routing_rule_detail.html`:

```django
{% extends "core/core_layout.html" %}
{% load crispy from crispy_forms_tags %}
{% load render_table from django_tables2 %}
{% load bootstrap_icon from common_extras %}
{% block title %}
    Routing Rule
{% endblock title %}
{% block heading %}
    <c-page-heading title="Routing Rule">
        <c-slot name="right">
            <a href="{% url 'router_rule_list' %}" class="btn btn-secondary">
                {% bootstrap_icon "list" %}
                Routing Rules
            </a>
        </c-slot>
    </c-page-heading>
{% endblock heading %}
{% block content %}
    <dl class="row">
        <dt class="col-sm-3">Name</dt>
        <dd class="col-sm-9">
            {{ rule.name }}
        </dd>
        <dt class="col-sm-3">On/Off</dt>
        <dd class="col-sm-9">
            {% if rule.enabled %}
                <span class="text-success">On</span>
            {% else %}
                <span class="text-muted">Off</span>
            {% endif %}
        </dd>
        <dt class="col-sm-3">Destination</dt>
        <dd class="col-sm-9">
            {{ rule.destination }}
        </dd>
        <dt class="col-sm-3">Pseudonymizes</dt>
        <dd class="col-sm-9">
            {{ rule.pseudonymize|yesno:"Yes,No" }}
        </dd>
        <dt class="col-sm-3">Trial Protocol ID</dt>
        <dd class="col-sm-9">
            {{ rule.trial_protocol_id|default:"—" }}
        </dd>
        <dt class="col-sm-3">Trial Protocol Name</dt>
        <dd class="col-sm-9">
            {{ rule.trial_protocol_name|default:"—" }}
        </dd>
        <dt class="col-sm-3">Filters</dt>
        <dd class="col-sm-9">
            <pre class="mb-0">{{ filters_json }}</pre>
        </dd>
        <dt class="col-sm-3">Created By</dt>
        <dd class="col-sm-9">
            {{ rule.created_by }}
        </dd>
        <dt class="col-sm-3">Created At</dt>
        <dd class="col-sm-9">
            {{ rule.created }}
        </dd>
        <dt class="col-sm-3">Updated At</dt>
        <dd class="col-sm-9">
            {{ rule.updated }}
        </dd>
    </dl>
    <div class="d-flex mb-4">
        <form class="me-3"
              action="{% url 'router_rule_toggle' rule.pk %}"
              method="post">
            {% csrf_token %}
            {% if rule.enabled %}
                <input type="hidden" name="enabled" value="0" />
                <button type="submit" class="btn btn-warning">
                    {% bootstrap_icon "pause" %}
                    Disable Rule
                </button>
            {% else %}
                <input type="hidden" name="enabled" value="1" />
                <button type="submit" class="btn btn-success">
                    {% bootstrap_icon "play" %}
                    Enable Rule
                </button>
            {% endif %}
        </form>
        {% if failed_count %}
            <form class="me-3"
                  action="{% url 'router_rule_retry_failed' rule.pk %}"
                  method="post"
                  onSubmit="return confirm('Are you sure you want to retry the failed deliveries of this rule?');">
                {% csrf_token %}
                <button type="submit" class="btn btn-secondary">
                    {% bootstrap_icon "arrow-clockwise" %}
                    Retry Failed Deliveries ({{ failed_count }})
                </button>
            </form>
        {% endif %}
    </div>
    <c-table-heading title="Deliveries">
        <c-slot name="right">
            {% crispy filter.form %}
        </c-slot>
    </c-table-heading>
    {% render_table table %}
{% endblock content %}
```

In `adit/router/templates/router/router_job_list.html`:
- Add `{% load bootstrap_icon from common_extras %}` after `{% load render_table from django_tables2 %}`.
- Replace `<c-page-heading title="Router Jobs" />` with:

```django
    <c-page-heading title="Router Jobs">
        <c-slot name="right">
            <a href="{% url 'router_rule_list' %}" class="btn btn-secondary">
                {% bootstrap_icon "list" %}
                Routing Rules
            </a>
        </c-slot>
    </c-page-heading>
```

- [ ] **Step 7: Add the main menu item**

In `adit/router/apps.py`, replace `register_app` with:

```python
def register_app():
    from adit_radis_shared.common.site import MainMenuItem, register_main_menu_item

    from adit.core.site import JobStats, register_dicom_processor, register_job_stats_collector

    from .models import RouterJob, RouterTask
    from .processors import RouterTaskProcessor

    # Staff-only like the Admin Section, and listed right before it.
    register_main_menu_item(
        MainMenuItem(url_name="router_rule_list", label="Router", order=9, staff_only=True)
    )

    register_dicom_processor(get_model_label(RouterTask), RouterTaskProcessor)

    def collect_job_stats() -> JobStats:
        counts: dict[RouterJob.Status, int] = {}
        for status in RouterJob.Status:
            counts[status] = RouterJob.objects.filter(status=status).count()
        return JobStats("Router", "router_job_list", counts)

    register_job_stats_collector(collect_job_stats)
```

The other apps register with the default `order=1` and the Admin Section with `order=10`, so the Router item sits between them.

- [ ] **Step 8: Run the tests to verify they pass**

Run: `uv run cli test -- adit/router/tests/test_rule_views.py adit/router/tests/test_job_views.py adit/router/tests/test_models.py -v`
Expected: PASS. Until Task 5, the job IDs on a rule page link to the Django admin pages; `test_rule_page_lists_only_the_rules_deliveries` compares with `get_absolute_url()`, so it passes before and after.

- [ ] **Step 9: Lint**

Run: `uv run cli lint`
Expected: no errors.

- [ ] **Step 10: Commit**

```bash
git add adit/router/models.py adit/router/filters.py adit/router/tables.py adit/router/views.py \
  adit/router/urls.py adit/router/apps.py adit/router/templates/router/ \
  adit/router/tests/test_rule_views.py adit/router/tests/test_models.py
git commit -m "Show routing rules with their deliveries to staff"
```

---

### Task 5: Router job and task pages with their actions

**Files:**
- Modify: `adit/router/models.py` (`RouterJob.get_absolute_url`, `RouterTask.get_absolute_url`)
- Modify: `adit/router/filters.py` (`RouterTaskFilter`)
- Modify: `adit/router/tables.py` (`RouterTaskTable`)
- Modify: `adit/router/views.py` (job and task views)
- Modify: `adit/router/urls.py`
- Create: `adit/router/templatetags/__init__.py` (empty), `adit/router/templatetags/router_extras.py`
- Create: `adit/router/templates/router/router_job_detail.html`, `adit/router/templates/router/router_task_detail.html`
- Test: `adit/router/tests/test_job_views.py`, `adit/router/tests/test_models.py`

**Interfaces:**
- Consumes:
  - From Task 1: the hooks `is_deletable`, `is_resumable`, `is_retriable`, `is_restartable` and `is_resettable`, and `create_delivery(...)`.
  - From Task 3: `RouterStaffRequiredMixin` and `router_job_list`.
  - From Task 4: `RoutingRule.get_absolute_url()`.
  - The core views `DicomJobDetailView`, `DicomJobCancelView`, `DicomJobRetryView`, `DicomJobRestartView`, `DicomTaskDetailView`, `DicomTaskResetView` and `DicomTaskKillView` (`adit/core/views.py`).
  - The templates `core/_job_detail_control_panel.html`, `core/_task_detail_control_panel.html` and `core/_transfer_task_detail.html`. The task partial needs `job_url_name` in its context, which `DicomTaskDetailView` provides.
- Produces:
  - `RouterJob.get_absolute_url()` returns `/router/jobs/<pk>/`, and `RouterTask.get_absolute_url()` returns `/router/tasks/<pk>/`. Every core action redirect and table ID link uses them.
  - `RouterTaskFilter` and `RouterTaskTable`.
  - The views `RouterJobDetailView`, `RouterJobCancelView`, `RouterJobRetryView`, `RouterJobRestartView`, `RouterTaskDetailView`, `RouterTaskResetView` and `RouterTaskKillView`.
  - The URL names `router_job_detail`, `router_job_cancel`, `router_job_retry`, `router_job_restart`, `router_task_detail`, `router_task_reset` and `router_task_kill`.
  - The template tag library `router_extras` with `job_control_panel` and `task_control_panel`.

- [ ] **Step 1: Write the failing tests**

In `adit/router/tests/test_models.py`, replace stage 3's `test_router_job_and_task_link_to_their_admin_pages` with:

```python
@pytest.mark.django_db
def test_router_job_and_task_link_to_their_staff_pages():
    task = RouterTaskFactory.create()

    assert task.get_absolute_url() == f"/router/tasks/{task.pk}/"
    assert task.job.get_absolute_url() == f"/router/jobs/{task.job.pk}/"
```

In `adit/router/tests/test_job_views.py`, replace the imports with:

```python
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
```

and append:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run cli test -- adit/router/tests/test_job_views.py adit/router/tests/test_models.py -v`
Expected: FAIL. The new job view tests fail with `NoReverseMatch: Reverse for 'router_job_detail' not found` (or another missing router job/task URL name). `test_router_job_and_task_link_to_their_staff_pages` fails because the URLs still point at the Django admin. `test_router_jobs_have_no_delete_verify_or_resume_urls` already passes, and the Task 3 tests still pass.

- [ ] **Step 3: Point jobs and tasks at the staff pages**

In `adit/router/models.py`:
- In `RouterJob.get_absolute_url`, replace `reverse("admin:router_routerjob_change", args=[self.pk])` with `reverse("router_job_detail", args=[self.pk])`.
- In `RouterTask.get_absolute_url`, replace `reverse("admin:router_routertask_change", args=[self.pk])` with `reverse("router_task_detail", args=[self.pk])`.

- [ ] **Step 4: Add the task filter and table**

In `adit/router/filters.py`:
- Change `from adit.core.filters import DicomJobFilter` to `from adit.core.filters import DicomJobFilter, DicomTaskFilter`.
- Change `from .models import RouterJob` to `from .models import RouterJob, RouterTask`.
- Append:

```python
class RouterTaskFilter(DicomTaskFilter):
    class Meta(DicomTaskFilter.Meta):
        model = RouterTask
```

In `adit/router/tables.py`:
- Change `from adit.core.tables import RecordIdColumn, TransferJobTable` to `from adit.core.tables import DicomTaskTable, RecordIdColumn, TransferJobTable`.
- Append:

```python
class RouterTaskTable(DicomTaskTable):
    class Meta(DicomTaskTable.Meta):
        model = RouterTask
        empty_text = "No delivery tasks to show"
```

- [ ] **Step 5: Write the job and task views and their URLs**

In `adit/router/views.py`, replace the imports with:

```python
import json
from typing import Any, cast

from adit_radis_shared.common.mixins import PageSizeSelectMixin, RelatedFilterMixin
from adit_radis_shared.common.types import AuthenticatedHttpRequest
from django.contrib import messages
from django.core.exceptions import SuspiciousOperation, ValidationError
from django.db.models import QuerySet
from django.http import HttpResponse
from django.shortcuts import redirect
from django.template.defaultfilters import pluralize
from django.views.generic import DetailView, View
from django.views.generic.detail import SingleObjectMixin
from django_filters.views import FilterView
from django_tables2 import SingleTableMixin, SingleTableView

from adit.core.views import (
    DicomJobCancelView,
    DicomJobDetailView,
    DicomJobRestartView,
    DicomJobRetryView,
    DicomTaskDetailView,
    DicomTaskKillView,
    DicomTaskResetView,
)

from .filters import RouterJobFilter, RouterTaskFilter, RoutingRuleJobFilter
from .mixins import RouterStaffRequiredMixin
from .models import RouterJob, RouterTask, RoutingRule
from .tables import (
    RouterJobTable,
    RouterTaskTable,
    RoutingRuleJobTable,
    RoutingRuleTable,
    with_deliveries,
)
```

and append:

```python
class RouterJobDetailView(RouterStaffRequiredMixin, DicomJobDetailView):
    table_class = RouterTaskTable
    filterset_class = RouterTaskFilter
    model = RouterJob
    context_object_name = "job"
    template_name = "router/router_job_detail.html"

    def get_queryset(self) -> QuerySet[RouterJob]:
        return RouterJob.objects.select_related("rule", "owner", "batch__sender__server")


class RouterJobCancelView(RouterStaffRequiredMixin, DicomJobCancelView):
    model = RouterJob


class RouterJobRetryView(RouterStaffRequiredMixin, DicomJobRetryView):
    model = RouterJob


class RouterJobRestartView(RouterStaffRequiredMixin, DicomJobRestartView):
    model = RouterJob


class RouterTaskDetailView(RouterStaffRequiredMixin, DicomTaskDetailView):
    model = RouterTask
    job_url_name = "router_job_detail"
    template_name = "router/router_task_detail.html"


class RouterTaskResetView(RouterStaffRequiredMixin, DicomTaskResetView):
    model = RouterTask


class RouterTaskKillView(RouterStaffRequiredMixin, DicomTaskKillView):
    model = RouterTask
```

The mixin comes first, so a non-staff user gets 403 before the core views look at ownership.

Replace `adit/router/urls.py` with:

```python
from django.urls import path

from .views import (
    RouterJobCancelView,
    RouterJobDetailView,
    RouterJobListView,
    RouterJobRestartView,
    RouterJobRetryView,
    RouterTaskDetailView,
    RouterTaskKillView,
    RouterTaskResetView,
    RoutingRuleDetailView,
    RoutingRuleListView,
    RoutingRuleRetryFailedView,
    RoutingRuleToggleView,
)

urlpatterns = [
    path("rules/", RoutingRuleListView.as_view(), name="router_rule_list"),
    path("rules/<int:pk>/", RoutingRuleDetailView.as_view(), name="router_rule_detail"),
    path("rules/<int:pk>/toggle/", RoutingRuleToggleView.as_view(), name="router_rule_toggle"),
    path(
        "rules/<int:pk>/retry-failed/",
        RoutingRuleRetryFailedView.as_view(),
        name="router_rule_retry_failed",
    ),
    path("jobs/", RouterJobListView.as_view(), name="router_job_list"),
    path("jobs/<int:pk>/", RouterJobDetailView.as_view(), name="router_job_detail"),
    path("jobs/<int:pk>/cancel/", RouterJobCancelView.as_view(), name="router_job_cancel"),
    path("jobs/<int:pk>/retry/", RouterJobRetryView.as_view(), name="router_job_retry"),
    path("jobs/<int:pk>/restart/", RouterJobRestartView.as_view(), name="router_job_restart"),
    path("tasks/<int:pk>/", RouterTaskDetailView.as_view(), name="router_task_detail"),
    path("tasks/<int:pk>/reset/", RouterTaskResetView.as_view(), name="router_task_reset"),
    path("tasks/<int:pk>/kill/", RouterTaskKillView.as_view(), name="router_task_kill"),
]
```

- [ ] **Step 6: Write the control panel tags and the templates**

Create `adit/router/templatetags/__init__.py` (empty) and `adit/router/templatetags/router_extras.py`:

```python
from typing import Any

from django.template import Library

register = Library()


# Router jobs can't be deleted, verified or resumed, so only these actions get URLs.
@register.inclusion_tag("core/_job_detail_control_panel.html", takes_context=True)
def job_control_panel(context: dict[str, Any]) -> dict[str, Any]:
    return {
        "job_cancel_url": "router_job_cancel",
        "job_retry_url": "router_job_retry",
        "job_restart_url": "router_job_restart",
        "user": context["user"],
        "job": context["job"],
    }


@register.inclusion_tag("core/_task_detail_control_panel.html", takes_context=True)
def task_control_panel(context: dict[str, Any]) -> dict[str, Any]:
    return {
        "task_reset_url": "router_task_reset",
        "task_kill_url": "router_task_kill",
        "user": context["user"],
        "task": context["task"],
    }
```

Create `adit/router/templates/router/router_job_detail.html`:

```django
{% extends "core/core_layout.html" %}
{% load crispy from crispy_forms_tags %}
{% load render_table from django_tables2 %}
{% load bootstrap_icon from common_extras %}
{% load dicom_job_status_css_class from core_extras %}
{% load job_control_panel from router_extras %}
{% block title %}
    Router Job
{% endblock title %}
{% block heading %}
    <c-page-heading title="Router Job">
        <c-slot name="right">
            <a href="{% url 'router_job_list' %}" class="btn btn-secondary">
                {% bootstrap_icon "list" %}
                Job List
            </a>
        </c-slot>
    </c-page-heading>
{% endblock heading %}
{% block content %}
    {% if job.batch.files_deleted_at %}
        <div class="alert alert-info" role="alert">
            The images of this batch were deleted from the spool, so this delivery can't be
            retried, restarted or reset. To send the study again, have the PACS forward it to the router.
        </div>
    {% endif %}
    <dl class="row">
        <dt class="col-sm-3">Job ID</dt>
        <dd class="col-sm-9">
            {{ job.id }}
        </dd>
        <dt class="col-sm-3">Routing Rule</dt>
        <dd class="col-sm-9">
            <a href="{{ job.rule.get_absolute_url }}">{{ job.rule.name }}</a>
        </dd>
        <dt class="col-sm-3">Status</dt>
        <dd class="col-sm-9">
            <span class="{{ job.status|dicom_job_status_css_class }}"
                  data-status="{{ job.status }}">{{ job.get_status_display }}</span>
        </dd>
        <dt class="col-sm-3">Message</dt>
        <dd class="col-sm-9">
            {{ job.message|default:"—" }}
        </dd>
        <dt class="col-sm-3">Created At</dt>
        <dd class="col-sm-9">
            {{ job.created }}
        </dd>
        <dt class="col-sm-3">Created By</dt>
        <dd class="col-sm-9">
            {{ job.owner }}
        </dd>
        <dt class="col-sm-3">Trial Protocol ID</dt>
        <dd class="col-sm-9">
            {{ job.trial_protocol_id|default:"—" }}
        </dd>
        <dt class="col-sm-3">Trial Protocol Name</dt>
        <dd class="col-sm-9">
            {{ job.trial_protocol_name|default:"—" }}
        </dd>
        <dt class="col-sm-3">Batch ID</dt>
        <dd class="col-sm-9">
            {{ job.batch.batch_id }}
        </dd>
        <dt class="col-sm-3">Sender</dt>
        <dd class="col-sm-9">
            {{ job.batch.sender.server }} ({{ job.batch.sender.calling_ae_title }})
        </dd>
        <dt class="col-sm-3">Study Instance UID</dt>
        <dd class="col-sm-9">
            {{ job.batch.study_instance_uid }}
        </dd>
        <dt class="col-sm-3">Images Received</dt>
        <dd class="col-sm-9">
            {{ job.batch.number_of_images }}
        </dd>
        <dt class="col-sm-3">Closed At</dt>
        <dd class="col-sm-9">
            {{ job.batch.closed_at }}
        </dd>
        <dt class="col-sm-3">Images Deleted At</dt>
        <dd class="col-sm-9">
            {{ job.batch.files_deleted_at|default:"—" }}
        </dd>
    </dl>
    <c-table-heading title="Delivery Task">
        <c-slot name="right">
            {% crispy filter.form %}
        </c-slot>
    </c-table-heading>
    {% render_table table %}
    {% job_control_panel %}
{% endblock content %}
```

Create `adit/router/templates/router/router_task_detail.html`:

```django
{% extends "core/core_layout.html" %}
{% load task_control_panel from router_extras %}
{% block title %}
    Router Task
{% endblock title %}
{% block heading %}
    <c-page-heading title="Router Task" />
{% endblock heading %}
{% block content %}
    {% include "core/_transfer_task_detail.html" %}
    {% task_control_panel %}
{% endblock content %}
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `uv run cli test -- adit/router/tests/ -m "not acceptance" -v`
Expected: PASS, including stage 3's router tests and the Task 3 and 4 page tests. The job IDs on a rule page now link to the staff job pages.

- [ ] **Step 8: Lint**

Run: `uv run cli lint`
Expected: no errors.

- [ ] **Step 9: Commit**

```bash
git add adit/router/models.py adit/router/filters.py adit/router/tables.py adit/router/views.py \
  adit/router/urls.py adit/router/templatetags/ adit/router/templates/router/ \
  adit/router/tests/test_job_views.py adit/router/tests/test_models.py
git commit -m "Add router job and task pages with cancel, retry, restart, reset and kill"
```

---

### Task 6: Rule form pages, the shared CodeMirror theme and the rule help

**Files:**
- Modify: `adit/router/views.py` (create, update and help views)
- Modify: `adit/router/urls.py`
- Create: `adit/router/templates/router/routing_rule_form.html`
- Create: `adit/router/templates/router/_routing_rule_help.html`
- Create: `adit/core/templates/core/_codemirror_css.html`
- Modify: `adit/mass_transfer/templates/mass_transfer/mass_transfer_job_form.html` (include the partial)
- Modify: `adit/router/templates/router/routing_rule_list.html` ("New Rule"), `adit/router/templates/router/routing_rule_detail.html` ("Edit Rule")
- Test: `adit/router/tests/test_rule_views.py`, `adit/mass_transfer/tests/test_views.py`

**Interfaces:**
- Consumes:
  - From Task 2: `RoutingRuleForm(*args, user: User, **kwargs)`.
  - From Task 3: `RouterStaffRequiredMixin`.
  - From Task 4: `RoutingRule.get_absolute_url()`, the success redirect of both form views.
  - `HtmxTemplateView` (`adit_radis_shared.common.views`).
- Produces:
  - The views `RoutingRuleCreateView` and `RoutingRuleUpdateView`, whose context holds `form` and `page_title`, and `RouterHelpView`.
  - The URL names `router_rule_create` (`/router/rules/new/`), `router_rule_update` (`/router/rules/<pk>/edit/`) and `router_help` (`/router/help/`).
  - `core/_codemirror_css.html`, the dark-mode CodeMirror style that both filter forms include.

- [ ] **Step 1: Write the failing tests**

In `adit/router/tests/test_rule_views.py`, replace the imports with:

```python
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
```

and append:

```python
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
```

In `adit/mass_transfer/tests/test_views.py`, add `from pytest_django.asserts import assertContains` after `from django.urls import reverse`, and append:

```python
@pytest.mark.django_db
def test_create_form_has_the_dark_theme_of_the_filter_editor(client: Client, settings_no_toolbar):
    user = UserFactory.create(is_active=True)
    group = GroupFactory.create()
    add_user_to_group(user, group)
    add_permission(user, "mass_transfer", "add_masstransferjob")
    client.force_login(user)

    response = client.get(reverse("mass_transfer_job_create"))

    assertContains(response, '[data-bs-theme="dark"] .CodeMirror')
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run cli test -- adit/router/tests/test_rule_views.py adit/mass_transfer/tests/test_views.py -v`
Expected: FAIL. The new rule form tests fail with `NoReverseMatch: Reverse for 'router_rule_create' not found` (or `router_rule_update`, `router_help`). The mass transfer test already passes: it guards the style while it moves into the partial. The Task 4 tests still pass.

- [ ] **Step 3: Move the dark-mode CodeMirror style into a shared partial**

Create `adit/core/templates/core/_codemirror_css.html` with the `<style>` block from `mass_transfer_job_form.html`, unchanged:

```django
<style>
    .CodeMirror {
        border: 1px solid #ced4da;
        border-radius: 0.375rem;
        font-size: 0.85em;
        height: auto;
        min-height: 200px;
        max-height: 400px;
    }
    [data-bs-theme="dark"] .CodeMirror {
        background: #1e1e1e;
        color: #d4d4d4;
        border-color: #495057;
    }
    [data-bs-theme="dark"] .CodeMirror-gutters {
        background: #1e1e1e;
        border-right-color: #333;
    }
    [data-bs-theme="dark"] .CodeMirror-linenumber {
        color: #858585;
    }
    [data-bs-theme="dark"] .CodeMirror-cursor {
        border-left-color: #d4d4d4;
    }
    [data-bs-theme="dark"] .CodeMirror-selected {
        background: #264f78;
    }
    [data-bs-theme="dark"] .CodeMirror-focused .CodeMirror-selected {
        background: #264f78;
    }
    [data-bs-theme="dark"] .CodeMirror-activeline-background {
        background: #2a2a2a;
    }
    [data-bs-theme="dark"] .CodeMirror-matchingbracket {
        color: #d4d4d4 !important;
        background: #3b514d;
    }
    [data-bs-theme="dark"] .cm-s-default .cm-keyword { color: #569cd6; }
    [data-bs-theme="dark"] .cm-s-default .cm-atom { color: #b5cea8; }
    [data-bs-theme="dark"] .cm-s-default .cm-number { color: #b5cea8; }
    [data-bs-theme="dark"] .cm-s-default .cm-string { color: #ce9178; }
    [data-bs-theme="dark"] .cm-s-default .cm-string-2 { color: #ce9178; }
    [data-bs-theme="dark"] .cm-s-default .cm-variable { color: #9cdcfe; }
    [data-bs-theme="dark"] .cm-s-default .cm-variable-2 { color: #9cdcfe; }
    [data-bs-theme="dark"] .cm-s-default .cm-property { color: #9cdcfe; }
    [data-bs-theme="dark"] .cm-s-default .cm-comment { color: #6a9955; }
    [data-bs-theme="dark"] .cm-s-default .cm-bracket { color: #d4d4d4; }
    [data-bs-theme="dark"] .cm-s-default .cm-tag { color: #569cd6; }
    [data-bs-theme="dark"] .cm-s-default .cm-attribute { color: #9cdcfe; }
</style>
```

In `adit/mass_transfer/templates/mass_transfer/mass_transfer_job_form.html`, replace the whole `<style>…</style>` block inside `{% block css %}` with one line, so the block reads:

```django
{% block css %}
    {{ block.super }}
    {{ form.media.css }}
    {% include "core/_codemirror_css.html" %}
{% endblock css %}
```

- [ ] **Step 4: Write the form and help views and their URLs**

In `adit/router/views.py`, replace the imports with:

```python
import json
from typing import Any, cast

from adit_radis_shared.common.mixins import PageSizeSelectMixin, RelatedFilterMixin
from adit_radis_shared.common.types import AuthenticatedHttpRequest
from adit_radis_shared.common.views import HtmxTemplateView
from django.contrib import messages
from django.core.exceptions import SuspiciousOperation, ValidationError
from django.db.models import QuerySet
from django.http import HttpResponse
from django.shortcuts import redirect
from django.template.defaultfilters import pluralize
from django.views.generic import DetailView, View
from django.views.generic.detail import SingleObjectMixin
from django.views.generic.edit import CreateView, UpdateView
from django_filters.views import FilterView
from django_tables2 import SingleTableMixin, SingleTableView

from adit.core.views import (
    DicomJobCancelView,
    DicomJobDetailView,
    DicomJobRestartView,
    DicomJobRetryView,
    DicomTaskDetailView,
    DicomTaskKillView,
    DicomTaskResetView,
)

from .filters import RouterJobFilter, RouterTaskFilter, RoutingRuleJobFilter
from .forms import RoutingRuleForm
from .mixins import RouterStaffRequiredMixin
from .models import RouterJob, RouterTask, RoutingRule
from .tables import (
    RouterJobTable,
    RouterTaskTable,
    RoutingRuleJobTable,
    RoutingRuleTable,
    with_deliveries,
)
```

and append:

```python
class RoutingRuleCreateView(RouterStaffRequiredMixin, CreateView):
    model = RoutingRule
    form_class = RoutingRuleForm
    template_name = "router/routing_rule_form.html"
    extra_context = {"page_title": "New Routing Rule"}

    def get_form_kwargs(self) -> dict[str, Any]:
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form: RoutingRuleForm) -> HttpResponse:
        form.instance.created_by = self.request.user
        messages.success(self.request, f'Routing rule "{form.instance.name}" was created.')
        return super().form_valid(form)


class RoutingRuleUpdateView(RouterStaffRequiredMixin, UpdateView):
    model = RoutingRule
    form_class = RoutingRuleForm
    template_name = "router/routing_rule_form.html"
    extra_context = {"page_title": "Edit Routing Rule"}

    def get_form_kwargs(self) -> dict[str, Any]:
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form: RoutingRuleForm) -> HttpResponse:
        messages.success(self.request, f'Routing rule "{form.instance.name}" was saved.')
        return super().form_valid(form)


class RouterHelpView(RouterStaffRequiredMixin, HtmxTemplateView):
    template_name = "router/_routing_rule_help.html"
```

Both form views redirect to `rule.get_absolute_url()` after saving, which is Django's default.

Replace `adit/router/urls.py` with:

```python
from django.urls import path

from .views import (
    RouterHelpView,
    RouterJobCancelView,
    RouterJobDetailView,
    RouterJobListView,
    RouterJobRestartView,
    RouterJobRetryView,
    RouterTaskDetailView,
    RouterTaskKillView,
    RouterTaskResetView,
    RoutingRuleCreateView,
    RoutingRuleDetailView,
    RoutingRuleListView,
    RoutingRuleRetryFailedView,
    RoutingRuleToggleView,
    RoutingRuleUpdateView,
)

urlpatterns = [
    path("rules/", RoutingRuleListView.as_view(), name="router_rule_list"),
    path("rules/new/", RoutingRuleCreateView.as_view(), name="router_rule_create"),
    path("rules/<int:pk>/", RoutingRuleDetailView.as_view(), name="router_rule_detail"),
    path("rules/<int:pk>/edit/", RoutingRuleUpdateView.as_view(), name="router_rule_update"),
    path("rules/<int:pk>/toggle/", RoutingRuleToggleView.as_view(), name="router_rule_toggle"),
    path(
        "rules/<int:pk>/retry-failed/",
        RoutingRuleRetryFailedView.as_view(),
        name="router_rule_retry_failed",
    ),
    path("help/", RouterHelpView.as_view(), name="router_help"),
    path("jobs/", RouterJobListView.as_view(), name="router_job_list"),
    path("jobs/<int:pk>/", RouterJobDetailView.as_view(), name="router_job_detail"),
    path("jobs/<int:pk>/cancel/", RouterJobCancelView.as_view(), name="router_job_cancel"),
    path("jobs/<int:pk>/retry/", RouterJobRetryView.as_view(), name="router_job_retry"),
    path("jobs/<int:pk>/restart/", RouterJobRestartView.as_view(), name="router_job_restart"),
    path("tasks/<int:pk>/", RouterTaskDetailView.as_view(), name="router_task_detail"),
    path("tasks/<int:pk>/reset/", RouterTaskResetView.as_view(), name="router_task_reset"),
    path("tasks/<int:pk>/kill/", RouterTaskKillView.as_view(), name="router_task_kill"),
]
```

- [ ] **Step 5: Write the form page and the help dialog**

Create `adit/router/templates/router/routing_rule_form.html`:

```django
{% extends "core/core_layout.html" %}
{% load crispy from crispy_forms_tags %}
{% load bootstrap_icon from common_extras %}
{% block title %}
    {{ page_title }}
{% endblock title %}
{% block css %}
    {{ block.super }}
    {{ form.media.css }}
    {% include "core/_codemirror_css.html" %}
{% endblock css %}
{% block heading %}
    <c-page-heading title="{{ page_title }}">
        <c-slot name="left">
            <button type="button"
                    class="btn btn-info"
                    hx-get="{% url 'router_help' %}"
                    hx-target="#htmx-dialog">
                Help
                {% bootstrap_icon "question-circle" %}
            </button>
        </c-slot>
        <c-slot name="right">
            <a href="{% url 'router_rule_list' %}" class="btn btn-secondary">
                {% bootstrap_icon "list" %}
                Routing Rules
            </a>
        </c-slot>
    </c-page-heading>
{% endblock heading %}
{% block content %}
    {# crispy renders form.media, so the editor's JavaScript loads before the editor #}
    {% crispy form %}
{% endblock content %}
```

Create `adit/router/templates/router/_routing_rule_help.html`:

```django
<div class="modal-content">
    <div class="modal-header">
        <h5 class="modal-title">Routing Rule Help</h5>
        <button type="button"
                class="btn-close"
                data-bs-dismiss="modal"
                aria-label="Close" />
    </div>
    <div class="modal-body">
        <p>
            A routing rule decides which of the studies a PACS forwards to the DICOM router are sent where. The router
            checks every enabled rule once per study, when no image of the study has arrived for a few minutes. Every
            matching rule sends the series it selects to its destination, independently of the other rules. A changed
            rule applies to the studies checked afterwards, and a study checked while a rule is disabled is not sent
            for that rule later.
        </p>
        <h6>Filters</h6>
        <p>
            The filters are a JSON array in the format of the mass transfer filters, and they select the same series.
            A series is sent when it matches at least one include filter and no exclude filter. At least one include
            filter is required. Text conditions accept the DICOM wildcards * and ? and must match the whole value:
            include filters match case-sensitively, exclude filters case-insensitively.
        </p>
        <dl>
            <dt>Study-level conditions</dt>
            <dd>
                study_description, min_age and max_age (the age on the study date; a study without a birth date
                matches no include filter with an age), and institution_name while apply_institution_on_study is
                true, which is the default. They are checked on the images of the study the router received.
            </dd>
            <dt>Series-level conditions</dt>
            <dd>
                modality ("CT" selects the CT series of a study), series_description, series_number,
                min_number_of_series_related_instances, and institution_name when apply_institution_on_study is
                false. A rule without series-level conditions sends the whole study.
            </dd>
        </dl>
        <p>
            This rule sends every series of the studies described as head examinations of patients aged 20 to 30,
            without presentation states and structured reports:
        </p>
        <pre>[
  {"mode": "include", "study_description": "*Head*", "min_age": 20, "max_age": 30},
  {"mode": "exclude", "modality": "PR"},
  {"mode": "exclude", "modality": "SR"}
]</pre>
        <h6>Presentation states and structured reports</h6>
        <p>
            EXCLUDE_MODALITIES does not apply to the router; only the rule's filters decide what is sent. Leave out
            presentation states (PR), structured reports (SR) or dose screenshots with exclude filters, as above.
        </p>
        <h6>Pseudonyms</h6>
        <p>
            A pseudonymizing rule computes each patient's pseudonym from its salt and the Patient ID. The same patient
            always gets the same pseudonym under a rule, and different rules give different pseudonyms. Once the rule
            has sent a study, Pseudonymize and the salt are fixed; create a new rule to change them. A mass transfer
            job with the same filters and salt gives the same pseudonyms, which is how older studies are sent
            afterwards. Sending without pseudonymization needs the permission to transfer unpseudonymized.
        </p>
        <h6>XNAT</h6>
        <p>
            Set the trial protocol ID to the XNAT project ID. When the rule pseudonymizes, the router writes
            "Project:&lt;trial protocol ID&gt; Subject:&lt;pseudonym&gt; Session:…" into the Patient Comments of every
            image, and XNAT files the images under that project and subject.
        </p>
        <h6>Late images</h6>
        <p>
            Images that arrive after a study was checked are checked again as a new batch of the same study and sent
            as a follow-up, with the same pseudonym and the same replacement UIDs, so the destination ends up with the
            whole study. Images the rule sent before are not sent again.
        </p>
    </div>
</div>
```

- [ ] **Step 6: Add the "New Rule" and "Edit Rule" buttons**

In `adit/router/templates/router/routing_rule_list.html`, add this link after the "Router Jobs" link, inside the right slot:

```django
            <a href="{% url 'router_rule_create' %}" class="btn btn-primary">
                {% bootstrap_icon "plus-lg" %}
                New Rule
            </a>
```

In `adit/router/templates/router/routing_rule_detail.html`, add this link as the first element inside `<div class="d-flex mb-4">`, before the toggle form:

```django
        <a href="{% url 'router_rule_update' rule.pk %}"
           class="btn btn-primary me-3">
            {% bootstrap_icon "pencil" %}
            Edit Rule
        </a>
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `uv run cli test -- adit/router/tests/ adit/mass_transfer/tests/test_views.py -m "not acceptance" -v`
Expected: PASS.

- [ ] **Step 8: Lint**

Run: `uv run cli lint`
Expected: no errors.

- [ ] **Step 9: Check the pages in the dev stack**

With the dev containers up (`uv run cli compose-up -- --watch`), log in as the superuser and open `http://localhost:8000/router/rules/`:
- The navbar shows "Router" between "DICOM Explorer" and "Admin Section".
- "New Rule" shows the CodeMirror editor with the example filters. "Help" opens the dialog.
- Switch the theme to dark: the editor turns dark, and so does the mass transfer form's editor.
- The example rule from `populate_example_data` ("Example: CT to Orthanc 2") is listed as Off. Its page shows "Enable Rule".

- [ ] **Step 10: Commit**

```bash
git add adit/router/views.py adit/router/urls.py adit/router/templates/router/ \
  adit/core/templates/core/_codemirror_css.html \
  adit/mass_transfer/templates/mass_transfer/mass_transfer_job_form.html \
  adit/router/tests/test_rule_views.py adit/mass_transfer/tests/test_views.py
git commit -m "Let staff create and edit routing rules on the router pages"
```

---

### Task 7: Router docs

**Files:**
- Modify: `docs/user-docs/admin-guide.md` (a new "DICOM Router" section, the "Optional tuning" paragraph, "Job Overview")
- Modify: `docs/user-docs/features.md`, `README.md` (feature lists)
- Modify: `AGENTS.md`, which `CLAUDE.md` is a symlink to (the router entry)
- Modify: `docs/dev-docs/architecture.md` (the DICOM Router section)
- Modify: `docs/superpowers/specs/2026-09-30-dicom-router-design.md` (status line)

**Interfaces:**
- Consumes: the page, button and URL names of Tasks 3 to 6 ("Router", "Router Jobs", "New Rule", "Edit Rule", "Disable Rule", "Retry Failed Deliveries", `/router/`), and the settings documented in `example.env`.
- Produces: no code.

- [ ] **Step 1: Write the admin guide's "DICOM Router" section**

In `docs/user-docs/admin-guide.md`, insert this section right before `## Job Overview`:

````markdown
## DICOM Router

The DICOM router receives the studies a PACS forwards to it and sends the series that staff-defined routing rules select to other DICOM servers, optionally pseudonymized. For example, every CT head study of a patient aged 20 to 30 can be pseudonymized and sent to a research XNAT, filed under the right project. The `router` container only receives the images and stores them in a spool; the default worker checks the rules once no image of a study has arrived for `ROUTER_QUIET_PERIOD_SECONDS` (5 minutes by default), and the DICOM workers deliver.

### Setting Up the Router

1. **Choose an AE title**: Set `ROUTER_AE_TITLE` in `.env` (different from `RECEIVER_AE_TITLE`, for example `ADIT1ROUTER`) and, in production, the host port `ROUTER_PORT` (default 11113). Redeploy the stack. An empty `ROUTER_AE_TITLE` keeps the router off.
2. **Place the spool**: The spool is shared by the `router`, `default_worker` and `dicom_worker` containers. Like `MOUNT_DIR`, it assumes these containers run on one host or share a network filesystem. By default it is a Docker volume; `ROUTER_SPOOL_DIR` puts it in a host folder instead, which belongs on an encrypted disk (see [Router Security](#router-security)).
3. **Register the PACS as a sender** (see [Registering Senders](#registering-senders)).
4. **Configure forwarding on the PACS**: Add ADIT as a DICOM destination with the router's AE title, the ADIT host and `ROUTER_PORT`, and forward new studies to it. Keep the PACS's forwarding filter as narrow as your rules allow, for example CT only: everything the PACS forwards is received and checked, and studies no rule matches are only deleted again.

### Registering Senders

The router only accepts images from registered senders and rejects everyone else.

1. Make sure the PACS exists as a DICOM server (**Django Admin** → **Core** → **Dicom servers**)
2. Go to **Django Admin** → **Router** → **Router senders** and click **Add router sender**
3. Choose the PACS as **Server**. Leave **Calling AE title** empty to use the server's AE title, or enter the AE title the PACS sends from if it differs from the one it answers queries on
4. Save. Unchecking **Enabled** later makes the router refuse that sender

Senders are managed only in the Django admin. **Router** → **Router settings** → **Suspended** pauses receiving: the router answers every image with "out of resources", so the PACS keeps the images and sends them again later. Deliveries continue while the router is suspended.

### Writing Routing Rules

Routing rules are managed on the **Router** pages, which only staff users see in the main menu.

- **Router** lists every rule with its destination, whether it pseudonymizes, its deliveries by status and its last match. **New Rule** opens the rule form: a name, the destination (a DICOM server with C-STORE or STOW-RS support), the filters in the JSON format of mass transfer, pseudonymization and the trial protocol ID and name. The **Help** button of the form explains the filters.
- A series is sent when it matches at least one include filter and no exclude filter. A rule without series-level conditions (modality, series description, series number, minimum number of images) sends the whole study. Every matching rule sends its own copy, independently of the other rules.
- A rule's page shows its settings and deliveries and offers **Edit Rule**, **Disable Rule** (or **Enable Rule**) and **Retry Failed Deliveries**. A rule that has sent studies can't be deleted, only disabled. A changed rule applies to the studies checked afterwards; studies checked while a rule is disabled are not sent for it later.
- **Disable Rule** always works. **Enable Rule** first checks the rule: if it no longer validates, for example because its destination can't receive images any more, the rule stays disabled and the page names the problem. Fix it with **Edit Rule**.
- Once a rule has sent a study, **Pseudonymize** and the salt can't change any more, because a patient must keep the same pseudonym. Create a new rule instead.
- Creating a rule without pseudonymization, or switching it off, needs the permission `router | router job | Can transfer unpseudonymized`.
- A destination must never forward studies back to the router's AE title: the router would receive its own deliveries and send them again, in a loop.

### XNAT Projects

Set the rule's trial protocol ID to the XNAT project ID and keep pseudonymization on. The router then writes `Project:<trial protocol ID> Subject:<pseudonym> Session:<pseudonym>_<study date>-<study time>` into the Patient Comments of every image, and XNAT files the session under that project and subject. This text needs a pseudonym, so a rule without pseudonymization only sets the trial protocol attributes. A study whose images arrive with long pauses is delivered in several batches under the same pseudonym; XNAT merges them automatically only in projects that archive automatically.

### Presentation States and Structured Reports

`EXCLUDE_MODALITIES` does not apply to the router: as in mass transfer, only the rule's filters decide what is sent. A rule that sends whole studies also sends their presentation states (PR) and structured reports (SR). Leave them out with exclude filters:

```json
[
  {"mode": "include", "study_description": "*Head*", "min_age": 20, "max_age": 30},
  {"mode": "exclude", "modality": "PR"},
  {"mode": "exclude", "modality": "SR"}
]
```

### Sending Older Studies

The router only sees the studies the PACS forwards from now on. To send older studies (a backfill), create a mass transfer job over their date range with the rule's filters, pseudonymization on, the rule's salt (shown in the rule's edit form) and the same trial protocol ID. The same filters and salt give the same selection, pseudonyms and replacement UIDs, so the destination files the backfill together with the router's deliveries.

### Deliveries and Retention

For every study a rule matches, and for every follow-up batch of it, the router creates a router job with one delivery task, owned by the rule's creator. The jobs are listed on the rule's page and under **Router Jobs**, and the [Job Overview](#job-overview) counts them. A job can be canceled, retried, restarted and reset, and a running task killed, like other jobs; it can't be deleted, so canceling keeps its history. Images that arrive after a study was checked are sent as a follow-up batch with the same pseudonym. Images a rule sent before are not sent again for `ROUTER_SENT_LIST_RETENTION_DAYS` (30 days).

How long data stays in the spool:

- An open study waits until no image of it has arrived for `ROUTER_QUIET_PERIOD_SECONDS` (300), at most `ROUTER_MAX_OPEN_SECONDS` (3600) after its first image
- A study no rule matches is deleted right after the check
- A batch whose deliveries all succeeded (also with warnings) or were canceled is deleted at the next run of `close_router_batches` (`ROUTER_CLOSE_CRON`, every minute)
- A batch with a failed delivery is kept for `ROUTER_FAILED_RETENTION_DAYS` (7) after it closed, so the delivery can be retried; the admins get a daily mail with the failed deliveries and the date their images will be deleted. Afterwards Retry, Restart and Reset are refused, and the PACS has to forward the study again
- Unreadable files stay in quarantine for `ROUTER_QUARANTINE_RETENTION_DAYS` (7)

When the spool has less than `ROUTER_SPOOL_MIN_FREE_GB` (20) free, the router refuses new images (the PACS sends them again later) and mails the admins, at most every `ROUTER_LOW_SPACE_MAIL_HOURS` (6).

### Router Security

- Only the PACS network may reach the router port (`ROUTER_PORT`); block it for everyone else in the firewall.
- An AE title is not authentication. Anyone who can reach the port and knows a sender's AE title can send images, and the rules forward them.
- The spool holds identifiable images, so it belongs on an encrypted disk (`ROUTER_SPOOL_DIR`).
- A routing rule is a standing export of patient data, so only staff users can see and change rules and router jobs.
````

- [ ] **Step 2: Update the rest of the admin guide**

In `docs/user-docs/admin-guide.md`:
- **"Optional tuning" paragraph** (under "Environment Variables"): replace everything from ` Routing rules (` to the end of that paragraph with the text below. That stretch includes the sentence that says rules are configured in the Django admin, and stage 3's caveat that a failed delivery can't be retried from ADIT yet; both go away.

```markdown
 The router is set up as described in [DICOM Router](#dicom-router); `ROUTER_QUIET_PERIOD_SECONDS`, `ROUTER_MAX_OPEN_SECONDS` and `ROUTER_FAILED_RETENTION_DAYS` tune how long studies wait in the spool.
```

- **"Job Overview" section:** change `(Selective Transfer, Batch Query, Batch Transfer, Mass Transfer)` to `(Selective Transfer, Batch Query, Batch Transfer, Mass Transfer, Router)`.

- [ ] **Step 3: List the router as a feature**

In `docs/user-docs/features.md` and in the "Features" list of `README.md`, add this bullet after the bullet that starts with `- Mass transfer of large volumes`:

```markdown
- A DICOM router that receives the studies a PACS forwards and sends the series that staff-defined rules select to other DICOM servers, optionally pseudonymized and filed into XNAT projects
```

- [ ] **Step 4: Update `AGENTS.md`, the architecture docs and the spec status**

In `AGENTS.md`, in the `- **router/**:` entry, replace the sentence `Senders and rules are managed in the Django admin, where batches, jobs and tasks are read-only.` with:

```markdown
Rules are managed on the staff-only Router pages (`/router/`, `adit/router/views.py`): the rule list with deliveries by status, the rule form (`RoutingRuleForm`, shared with the Django admin; pseudonymization is fixed once a rule has a job), a rule's deliveries with "retry failed deliveries", and router jobs and tasks with Cancel, Retry, Restart, Reset and Kill (no Delete, Verify or Resume; Retry, Restart and Reset are refused once the batch's images are deleted). Senders are managed only in the Django admin, where batches, jobs and tasks are read-only.
```

In `docs/dev-docs/architecture.md`, in the "DICOM Router (adit.router)" section, add this bullet after the "Router inbox and routing" bullet:

```markdown
- **Staff pages**: `/router/` (staff only, `RouterStaffRequiredMixin`) lists the rules with their deliveries by status, edits them with `RoutingRuleForm` (shared with the Django admin, where senders are managed), and shows router jobs and tasks on subclasses of the generic core job and task views. `RouterJob` and `RouterTask` are never deleted or resumed, and refuse Retry, Restart and Reset once `RouterBatch.files_deleted_at` is set.
```

In `docs/superpowers/specs/2026-09-30-dicom-router-design.md`, change the `Status:` line to:

```markdown
Status: approved; stages 1 to 3 implemented (feat/dicom-router-filters, feat/dicom-router-inbox, feat/dicom-router-rules), stage 4 on feat/dicom-router-pages
```

- [ ] **Step 5: Check the docs**

Run: `uv run mkdocs build --strict --site-dir "$(mktemp -d)"`
Expected: the build succeeds without warnings. Strict mode fails on broken anchors such as `#dicom-router`, `#registering-senders`, `#router-security` and `#job-overview`.

Run: `grep -n "configured in the Django admin under Router\|can't be retried from ADIT yet" docs/user-docs/admin-guide.md`
Expected: no output.

- [ ] **Step 6: Commit**

```bash
git add docs/user-docs/admin-guide.md docs/user-docs/features.md README.md AGENTS.md \
  docs/dev-docs/architecture.md docs/superpowers/specs/2026-09-30-dicom-router-design.md
git commit -m "Document the router pages, senders, rules, retention and security"
```

---

### Task 8: Browser test of the rule form, and the final checks

**Files:**
- Create: `adit/router/tests/acceptance/test_router_pages.py`

**Interfaces:**
- Consumes: the whole stage. The "Router" menu link and the "New Rule" link (Tasks 4 and 6), the "Help" dialog, the inputs `#id_name`, `#id_destination` and `#id_trial_protocol_id`, the CodeMirror editor and the "Save Rule" button (Tasks 2 and 6), and the rule page with "Disable Rule" (Task 4). Also `login_user` (`adit_radis_shared.common.utils.testing_helpers`) and the `live_server` and `page` fixtures. The existing `adit/router/tests/acceptance/conftest.py` sets `DJANGO_ALLOW_ASYNC_UNSAFE`.
- Produces: no code.

- [ ] **Step 1: Write the browser test**

Create `adit/router/tests/acceptance/test_router_pages.py`:

```python
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
    expect(page.get_by_text("Routing Rule Help")).to_be_visible()
    page.locator("#htmx-modal .btn-close").click()
    expect(page.get_by_text("Routing Rule Help")).to_be_hidden()

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
```

The labels of required fields end with `*`, so the test finds the inputs by ID. The editor is set through CodeMirror's API, like the mass transfer acceptance test does.

- [ ] **Step 2: Run the browser test**

Run: `uv run cli test -- adit/router/tests/acceptance/test_router_pages.py -m acceptance -v`
Expected: PASS. Every feature it drives exists since Task 6. If it fails, fix the page code, not the test, unless the test itself is wrong about a locator.

- [ ] **Step 3: Run the full suite and lint**

Run: `uv run cli test` (it includes the acceptance tests), then `uv run cli lint`.
Expected: all tests pass, and lint reports no errors.

- [ ] **Step 4: Commit**

```bash
git add adit/router/tests/acceptance/test_router_pages.py
git commit -m "Drive the routing rule form in a browser"
```
