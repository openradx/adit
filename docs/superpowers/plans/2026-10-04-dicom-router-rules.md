# DICOM Router Stage 3: Rules and Delivery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the spooled images into deliveries:
- Close quiet studies into batches.
- Decide each batch against staff-defined routing rules.
- Send the selected series, optionally pseudonymized, to each matching rule's destination.
- Clean the spool up afterwards.

**Architecture:** The router container keeps writing images to `incoming/<sender id>/<study>/`.

- **Closing and deciding.** A periodic task on the default worker, `close_router_batches`, does this:
  - It renames quiet study folders to `batches/<sender id>/<batch id>/`.
  - It reads their headers and selects series per enabled `RoutingRule`, with the mass transfer filter semantics now shared from core.
  - In one transaction, it creates a `RouterBatch` plus one `RouterJob`/`RouterTask` per matching rule, then queues them.
- **Delivery.** DICOM workers run `RouterTaskProcessor`. It reads the task's series from the batch folder and pseudonymizes with the rule's salt (XNAT project in Patient Comments). It sends over one association that requests exactly the batch's (SOP class, transfer syntax) pairs, and records the sent SOP Instance UIDs.
- **Clean-up and reports.** Finished batches are deleted. A daily task mails failed deliveries.

**Tech Stack:** Django 6.1, Procrastinate 3.9 (periodic tasks with `lock`/`queueing_lock`), pydicom 3, pynetdicom 3, dicognito (via `Pseudonymizer`), pytest with pytest-django and factory_boy.

**Spec:** `docs/superpowers/specs/2026-09-30-dicom-router-design.md`
- Stage 3 in §10.
- §3.2 close/decide/clean up, and §3.3 deliver.
- §4 rule semantics.
- §5 data model and rule editing.
- §7 settings and compose.
- §8 races, §9 accepted risks, and §12 tests.

## Global Constraints

- **Code style:**
  - Google Python style, ruff line length 100, pyright in basic mode (django-stubs are installed, so Django APIs are typed).
  - Comments only where the code can't speak for itself, and they explain why.
  - No history in comments or docstrings.
- **Django fields:** a CharField uses `blank=True` (never `null=True`), plus `default=""` when it has no initial value. Other fields use `blank=True, null=True`.
- **Invariants:** use `assert` for internal invariants. ADIT never runs with `python -O`.
- **Spool layout** under `ROUTER_SPOOL_PATH` (default `/spool`), all on one filesystem:
  - `tmp/`
  - `incoming/<sender id>/<StudyInstanceUID>/<SOPInstanceUID>.dcm`
  - `batches/<sender id>/<batch id>/<SOPInstanceUID>.dcm`, where `<batch id>` is a UUID and is also `RouterBatch.batch_id`
  - `quarantine/<YYYYMMDD>/<file>`
  - `<sender id>` is the `RouterSender` primary key.
- **Closing:**
  - A study folder closes when its modification time is `ROUTER_QUIET_PERIOD_SECONDS` old, or its oldest file `ROUTER_MAX_OPEN_SECONDS` old.
  - Closing is one `os.rename` into `batches/<sender id>/<new uuid>/`, followed by an fsync of both parent folders.
  - `incoming/<sender id>/` is never removed.
- **Deciding:**
  - Every batch folder without a `RouterBatch` row is decided. Every step is safe to repeat after a crash.
  - A batch no enabled rule matches is deleted, and no row is written.
  - The unique constraints on `RouterBatch.batch_id` and `RouterJob(rule, batch)` make a second decision fail with `IntegrityError`, which is logged and skipped.
- **Selection:**
  - Series are selected exactly as mass transfer discovers them (`select_study_series` in core, pinned by a parity test against mass transfer's discovery).
  - `EXCLUDE_MODALITIES` does not apply.
  - SOP instances already in `sent_instance_uids` of the rule's `SUCCESS`/`WARNING` tasks for the same study and destination are left out. A rule matches only if at least one image is left.
- **Jobs:**
  - One `RouterJob` per (rule, batch) with one `RouterTask`.
  - The job has owner `rule.created_by`, status `PENDING`, `send_finished_mail=False`, and `trial_protocol_id`/`trial_protocol_name` copied from the rule. Priorities are 3 (default) and 7 (urgent).
  - The tasks are queued inside the deciding transaction, so their queue rows appear only at commit.
- **Pseudonyms:**
  - The pseudonym is `deterministic_pseudonym(rule.pseudonym_salt, PatientID)` when the rule pseudonymizes, otherwise empty.
  - A batch without a Patient ID keys the pseudonym with its StudyInstanceUID, so unrelated patients never share one.
  - Images are pseudonymized with `Pseudonymizer(seed=rule.pseudonym_salt)` through `DicomManipulator.manipulate(ds, pseudonym, trial_protocol_id, trial_protocol_name)`.
- **Delivery:**
  - One association per delivery, requesting one presentation context per (SOP class, transfer syntax) pair present.
  - `sent_instance_uids` holds the original SOP Instance UIDs and is written only after a successful upload.
  - A task with nothing left to send ends `SUCCESS` with "Nothing new to send."
  - A batch whose `files_deleted_at` is set fails with a `DicomError` telling to have the PACS forward the study again.
  - `RouterSettings.suspended` pauses intake only; deliveries continue.
- **Clean-up:**
  - A batch whose jobs all ended `SUCCESS`, `WARNING` or `CANCELED` has its folder deleted and `files_deleted_at` set.
  - A batch with a `FAILURE` job is cleaned up the same way once every job has finished and it closed more than `ROUTER_FAILED_RETENTION_DAYS` ago.
  - `quarantine/` days older than `ROUTER_QUARANTINE_RETENTION_DAYS` and `tmp/` files older than one hour are deleted.
  - Low space mails the admins at most once per `ROUTER_LOW_SPACE_MAIL_HOURS`.
- **Settings and defaults** (env-overridable unless noted):

  | Setting | Default |
  |---|---|
  | `ROUTER_QUIET_PERIOD_SECONDS` | 300 |
  | `ROUTER_MAX_OPEN_SECONDS` | 3600 |
  | `ROUTER_CLOSE_CRON` | `* * * * *` |
  | `ROUTER_LOW_SPACE_MAIL_HOURS` | 6 |
  | `ROUTER_FAILED_RETENTION_DAYS` | 7 |
  | `ROUTER_QUARANTINE_RETENTION_DAYS` | 7 |
  | `ROUTER_SENT_LIST_RETENTION_DAYS` | 30 |
  | `ROUTER_PROCESS_TIMEOUT` | 3600 |
  | `ROUTER_DEFAULT_PRIORITY` / `ROUTER_URGENT_PRIORITY` | 3 / 7 (constants, like the other apps' priorities) |
- **Rule editing:**
  - `pseudonymize` and `pseudonym_salt` can't change once a rule has a job.
  - Switching pseudonymization off needs `router.can_transfer_unpseudonymized`.
  - Rules are managed in the Django admin in this stage. Batches, jobs and tasks are visible there, read-only.
- **Unchanged behaviour:** the receiver's behaviour and mass transfer's selection don't change.
- **Docs in this PR:** keep `AGENTS.md` (which `CLAUDE.md` links to), `example.env`, `docs/user-docs/admin-guide.md` and `docs/dev-docs/architecture.md` in sync.
- **Branch:** `feat/dicom-router-rules`, stacked on `feat/dicom-router-inbox` (stage 2).
- **Running tests and lint:**
  - Tests run in the web container: `uv run cli test -- <paths>`. Use `-m "not acceptance"` for everything but the acceptance tests.
  - Lint runs on the host: `uv run cli lint`.
  - Migrations are generated in the container and copied out.
  - `$COMPOSE` means `docker compose -f docker-compose.base.yml -f docker-compose.dev.yml -p adit_dev`.
- **Commits:** every commit message ends with the attribution trailer lines that the executing session's harness specifies.

## Review Focus

These are the inputs most likely to bite a person running the router, and the test that pins each one:

1. **A study whose images keep arriving after its first batch was delivered.** The late batch must reach the destination as the same pseudonymized patient and study, with the same pseudonym and replacement UIDs. Task 5: `test_late_batch_gets_the_same_pseudonym_and_uids`.
2. **The PACS forwards a study again.** Images sent before are left out. When nothing is left, no delivery is created (Task 6: `test_images_sent_before_are_not_routed_again`), and a delivery that finds everything sent ends with "Nothing new to send." (Task 5).
3. **A study stored compressed (JPEG-LS) or in a SOP class outside ADIT's C-STORE list.** The delivery requests the pair it holds instead of failing on a missing presentation context. Task 4: `test_c_store_requests_the_given_contexts`; Task 5: `test_delivery_requests_the_stored_transfer_syntax`.
4. **A delivery whose batch folder is gone** (retention ran, or the folder was deleted by hand). It fails with a message that tells staff to have the PACS forward the study again, not with a traceback about a missing file. Task 5: `test_delivery_of_a_deleted_batch_fails_clearly`, `test_delivery_of_a_missing_batch_folder_fails_clearly`.
5. **A worker that runs `close_router_batches` without the spool mounted.** This covers the web container, where tests run workers and the periodic deferrer fires. The task must skip with a warning instead of creating `/spool`. Task 7: `test_closing_skips_when_the_spool_is_not_mounted`.

---

### Task 1: Shared series selection and filter validation in core

**Files:**
- Modify: `adit/core/utils/series_filters.py`
- Modify: `adit/mass_transfer/forms.py` (`clean_filters_json`, imports)
- Test: `adit/core/tests/utils/test_series_filters.py`
- Test: `adit/mass_transfer/tests/test_processor.py`

**Interfaces:**
- Consumes: the existing `FilterSchema`, `FilterSpec`, `DiscoveredSeries`, `dicom_match`, `study_matches_filter` and `series_matches_filter`.
- Produces:
  - `parse_filters(data: object) -> list[dict]`, which raises `ValueError` with a message for the user.
  - `class StudyFacts(Protocol)` with read-only `ModalitiesInStudy: list[str]`, `StudyDescription: str`, `PatientBirthDate: date | None` and `StudyDate: date | None`.
  - `study_matches_filter(mf: FilterSpec, study: StudyFacts, has_institution: Callable[[str], bool]) -> bool`.
  - `select_study_series(study: StudyFacts, series: Sequence[DiscoveredSeries], filters: Sequence[FilterSpec]) -> list[DiscoveredSeries]`.

- [ ] **Step 1: Write the failing tests for selection and validation**

Append to `adit/core/tests/utils/test_series_filters.py`. Extend the existing import of `adit.core.utils.series_filters` to `DiscoveredSeries, FilterSpec, parse_filters, select_study_series, study_matches_filter`, and add `from dataclasses import dataclass, field` and `from datetime import date, datetime` at the top:

```python
@dataclass(frozen=True)
class _Facts:
    ModalitiesInStudy: list[str] = field(default_factory=lambda: ["CT", "SR"])
    StudyDescription: str = "CT Kopf nativ"
    PatientBirthDate: date | None = date(1999, 6, 1)
    StudyDate: date | None = date(2024, 6, 1)


def _series(
    uid: str,
    modality: str = "CT",
    description: str = "Axial",
    institution: str = "Radiology",
    birth_date: date | None = date(1999, 6, 1),
) -> DiscoveredSeries:
    return DiscoveredSeries(
        patient_id="PAT1",
        accession_number="",
        study_instance_uid="1.2.3",
        series_instance_uid=uid,
        modality=modality,
        study_description="CT Kopf nativ",
        series_description=description,
        series_number=1,
        study_datetime=datetime(2024, 6, 1, 12, 0),
        institution_name=institution,
        number_of_images=10,
        patient_birth_date=birth_date,
    )


def _uids(selected: list[DiscoveredSeries]) -> set[str]:
    return {s.series_instance_uid for s in selected}


def test_filter_without_series_conditions_selects_the_whole_study():
    series = [_series("1"), _series("2", modality="SR", description="Dose report")]

    selected = select_study_series(_Facts(), series, [FilterSpec(study_description="CT*")])

    assert _uids(selected) == {"1", "2"}


def test_modality_selects_series_not_studies():
    series = [_series("1"), _series("2", modality="SR")]

    assert _uids(select_study_series(_Facts(), series, [FilterSpec(modality="CT")])) == {"1"}


def test_structured_reports_are_sent_when_a_filter_selects_them():
    series = [_series("1"), _series("2", modality="SR")]
    filters = [FilterSpec(modality="CT"), FilterSpec(modality="SR")]

    assert _uids(select_study_series(_Facts(), series, filters)) == {"1", "2"}


def test_institution_on_study_admits_every_series():
    series = [_series("1", institution="Radiology"), _series("2", institution="External")]

    selected = select_study_series(_Facts(), series, [FilterSpec(institution_name="Radio*")])

    assert _uids(selected) == {"1", "2"}


def test_institution_on_series_selects_matching_series():
    series = [_series("1", institution="Radiology"), _series("2", institution="External")]
    mf = FilterSpec(institution_name="Radio*", apply_institution_on_study=False)

    assert _uids(select_study_series(_Facts(), series, [mf])) == {"1"}


def test_unknown_birth_date_fails_an_age_bounded_include():
    facts = _Facts(PatientBirthDate=None)

    selected = select_study_series(
        facts, [_series("1", birth_date=None)], [FilterSpec(min_age=20, max_age=30)]
    )

    assert selected == []


def test_age_bounded_exclude_drops_series_with_unknown_birth_date():
    facts = _Facts(PatientBirthDate=None)
    filters = [FilterSpec(), FilterSpec(mode="exclude", max_age=18)]

    assert select_study_series(facts, [_series("1", birth_date=None)], filters) == []


def test_exclude_filters_match_case_insensitively():
    series = [_series("1", description="Axial"), _series("2", description="CORONAL")]
    filters = [FilterSpec(modality="CT"), FilterSpec(mode="exclude", series_description="cor*")]

    assert _uids(select_study_series(_Facts(), series, filters)) == {"1"}


def test_study_failing_the_study_conditions_selects_nothing():
    selected = select_study_series(
        _Facts(), [_series("1")], [FilterSpec(study_description="MR*")]
    )

    assert selected == []


@pytest.mark.parametrize("data", [None, {}, [], "CT"])
def test_parse_filters_needs_a_non_empty_list(data):
    with pytest.raises(ValueError, match="non-empty JSON array"):
        parse_filters(data)


def test_parse_filters_needs_objects():
    with pytest.raises(ValueError, match="Filter #2 must be a JSON object"):
        parse_filters([{"modality": "CT"}, "MR"])


def test_parse_filters_reports_invalid_fields():
    with pytest.raises(ValueError, match="Filter #1: "):
        parse_filters([{"modality": "CT", "unknown": 1}])


def test_parse_filters_needs_an_include_filter():
    with pytest.raises(ValueError, match="mode=include"):
        parse_filters([{"mode": "exclude", "modality": "SR"}])


def test_parse_filters_normalizes_valid_filters():
    [parsed] = parse_filters([{"modality": "CT"}])

    assert parsed["mode"] == "include"
    assert parsed["modality"] == "CT"
```

- [ ] **Step 2: Write the parity test against mass transfer**

Append to `adit/mass_transfer/tests/test_processor.py`, and add `select_study_series` to its existing import from `adit.core.utils.series_filters`:

```python
_PARITY_SERIES = [
    # SeriesInstanceUID, Modality, SeriesDescription, InstitutionName, images
    ("1.2.3.201", "CT", "Axial", "Radiology", 10),
    ("1.2.3.202", "CT", "Coronal", "External", 3),
    ("1.2.3.203", "MR", "Ax T1", "Radiology", 20),
    ("1.2.3.204", "SR", "Dose report", "Radiology", 1),
]


@pytest.mark.parametrize(
    "filters",
    [
        [FilterSpec(modality="CT")],
        [FilterSpec(modality="MR")],
        [FilterSpec(series_description="Ax*")],
        [FilterSpec(institution_name="Radio*")],
        [FilterSpec(institution_name="Radio*", apply_institution_on_study=False)],
        [FilterSpec(study_description="Head*"), FilterSpec(modality="SR")],
        [FilterSpec(min_age=20, max_age=30)],
        [FilterSpec(min_age=40)],
        [FilterSpec(min_number_of_series_related_instances=5)],
        [FilterSpec(modality="CT"), FilterSpec(mode="exclude", series_description="cor*")],
        [FilterSpec(), FilterSpec(mode="exclude", max_age=30)],
        [FilterSpec(), FilterSpec(mode="exclude", modality="SR")],
    ],
)
def test_router_selection_matches_mass_transfer_discovery(mocker: MockerFixture, filters):
    """The DICOM router selects series with select_study_series. For the same study and
    filters it must select exactly what mass transfer discovers."""
    processor = _make_processor(mocker)
    processor.mass_task.partition_start = datetime(2024, 1, 1, 0, 0)
    processor.mass_task.partition_end = datetime(2024, 1, 1, 23, 59, 59)
    operator = mocker.create_autospec(DicomOperator)
    operator.server = mocker.MagicMock(max_search_results=200)

    study = _make_study("1.2.3.100")
    study.dataset.ModalitiesInStudy = ["CT", "MR", "SR"]
    study.dataset.StudyDescription = "Head routine"
    study.dataset.PatientBirthDate = "19990101"
    operator.find_studies.return_value = [study]
    operator.find_series.return_value = [
        _make_series_result(
            uid,
            modality=modality,
            series_description=description,
            institution_name=institution,
            num_images=images,
        )
        for uid, modality, description, institution, images in _PARITY_SERIES
    ]

    discovered = processor._discover_series(operator, filters)

    batch_series = [
        DiscoveredSeries(
            patient_id="PAT1",
            accession_number="",
            study_instance_uid="1.2.3.100",
            series_instance_uid=uid,
            modality=modality,
            study_description="Head routine",
            series_description=description,
            series_number=1,
            study_datetime=datetime(2024, 1, 1, 12, 0),
            institution_name=institution,
            number_of_images=images,
            patient_birth_date=date(1999, 1, 1),
        )
        for uid, modality, description, institution, images in _PARITY_SERIES
    ]
    selected = select_study_series(study, batch_series, filters)

    assert {s.series_instance_uid for s in selected} == {
        s.series_instance_uid for s in discovered
    }
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `uv run cli test -- adit/core/tests/utils/test_series_filters.py adit/mass_transfer/tests/test_processor.py`
Expected: FAIL while collecting, with `ImportError: cannot import name 'parse_filters'` (and `select_study_series`).

- [ ] **Step 4: Implement `parse_filters`, `StudyFacts` and `select_study_series`**

In `adit/core/utils/series_filters.py`:

- Change the imports at the top to:

```python
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Annotated, Literal, Protocol

from pydantic import BaseModel, ValidationError, model_validator

from ..errors import DicomError
from .dicom_utils import convert_to_python_regex
```

(The `ResultDataset` import is no longer needed. `study_matches_filter` takes a `StudyFacts`, which `ResultDataset` satisfies.)

- Directly after the `FilterSchema` class, add:

```python
def parse_filters(data: object) -> list[dict]:
    """Validate a filters_json value and return it normalized.

    Raises ValueError, with a message meant for the user, unless *data* is a non-empty
    list of filter objects with at least one include filter.
    """
    if not isinstance(data, list) or not data:
        raise ValueError("Filters must be a non-empty JSON array.")

    validated: list[dict] = []
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            raise ValueError(f"Filter #{i + 1} must be a JSON object.")
        try:
            validated.append(FilterSchema(**item).model_dump(exclude_none=True))
        except ValidationError as err:
            errors = "; ".join(e["msg"] for e in err.errors())
            raise ValueError(f"Filter #{i + 1}: {errors}") from err

    if not any(f.get("mode", "include") == "include" for f in validated):
        raise ValueError("At least one filter must have mode=include.")

    return validated
```

- Directly after the `DiscoveredSeries` class, add:

```python
class StudyFacts(Protocol):
    """What study_matches_filter reads about a study.

    A ResultDataset of a study found on a PACS provides it, and the DICOM router builds
    it from the headers of the images it received.
    """

    @property
    def ModalitiesInStudy(self) -> list[str]: ...

    @property
    def StudyDescription(self) -> str: ...

    @property
    def PatientBirthDate(self) -> date | None: ...

    @property
    def StudyDate(self) -> date | None: ...
```

- Change the signature of `study_matches_filter`. Its body stays as it is:

```python
def study_matches_filter(
    mf: FilterSpec, study: StudyFacts, has_institution: Callable[[str], bool]
) -> bool:
```

- Append at the end of the module:

```python
def select_study_series(
    study: StudyFacts, series: Sequence[DiscoveredSeries], filters: Sequence[FilterSpec]
) -> list[DiscoveredSeries]:
    """Select the series of one study the way mass transfer discovers them.

    A series is selected when an include filter matches it, its study-level conditions
    first, and no exclude filter does. *series* must hold every series of *study*,
    because the study-level institution condition looks at all of them.
    """
    selected: dict[str, DiscoveredSeries] = {}
    for mf in filters:
        if mf.mode != "include":
            continue
        if not study_matches_filter(
            mf,
            study,
            lambda pattern: any(dicom_match(pattern, s.institution_name) for s in series),
        ):
            continue
        for s in series:
            if s.series_instance_uid not in selected and series_matches_filter(
                s, mf, check_institution=not mf.apply_institution_on_study
            ):
                selected[s.series_instance_uid] = s

    excludes = [mf for mf in filters if mf.mode == "exclude"]
    return [
        s
        for s in selected.values()
        if not any(series_matches_filter(s, mf, age_permissive=True) for mf in excludes)
    ]
```

- [ ] **Step 5: Use `parse_filters` in the mass transfer form**

In `adit/mass_transfer/forms.py`:
- Replace `from adit.core.utils.series_filters import FilterSchema` with `from adit.core.utils.series_filters import parse_filters`.
- Delete `from pydantic import ValidationError as PydanticValidationError`.
- Replace the body of `clean_filters_json` with:

```python
    def clean_filters_json(self):
        raw = self.cleaned_data["filters_json"].strip()
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            raise ValidationError(f"Invalid JSON: {e}")

        try:
            return parse_filters(data)
        except ValueError as e:
            raise ValidationError(str(e))
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `uv run cli test -- adit/core/tests/utils/test_series_filters.py adit/mass_transfer/tests/`
Expected: PASS, including the 12 parity cases and the existing mass transfer form tests.

- [ ] **Step 7: Commit**

```bash
git add adit/core/utils/series_filters.py adit/mass_transfer/forms.py \
  adit/core/tests/utils/test_series_filters.py adit/mass_transfer/tests/test_processor.py
git commit -m "Share series selection and filter validation for the DICOM router"
```

---

### Task 2: Routing rules, batches, router jobs and settings

**Files:**
- Modify: `adit/settings/base.py` (the router settings block after `ROUTER_SPOOL_MIN_FREE_GB`, and the priorities block)
- Modify: `adit/router/models.py`
- Create: `adit/router/migrations/0002_rules_and_deliveries.py` (generated)
- Modify: `adit/router/admin.py`
- Modify: `adit/router/factories.py`
- Test: `adit/router/tests/test_models.py`, `adit/router/tests/test_admin.py` (new)

**Interfaces:**
- Consumes: `parse_filters` and `FilterSpec` (Task 1); `TransferJob`, `TransferTask`, `DicomTask`, `DicomAppSettings`, `DicomServer` (core); `DicomJobAdmin` and `DicomTaskAdmin` (`adit/core/admin.py`); `AbstractTransferJobFactory`, `AbstractTransferTaskFactory` and `DicomServerFactory` (`adit/core/factories.py`); `UserFactory` (`adit_radis_shared.accounts.factories`).
- Produces:
  - `RouterSettings.low_space_mailed_at`.
  - `RoutingRule` with `get_filters() -> list[FilterSpec]`.
  - `RouterBatch`.
  - `RouterJob` (`rule`, `batch`, priorities 3/7).
  - `RouterTask` (`sent_instance_uids`, and the classmethod `already_sent(rule_id: int, study_uid: str, destination_id: int) -> set[str]`).
  - The factories `RoutingRuleFactory`, `RouterBatchFactory`, `RouterJobFactory` and `RouterTaskFactory`.
  - The settings `ROUTER_QUIET_PERIOD_SECONDS`, `ROUTER_MAX_OPEN_SECONDS`, `ROUTER_CLOSE_CRON`, `ROUTER_LOW_SPACE_MAIL_HOURS`, `ROUTER_FAILED_RETENTION_DAYS`, `ROUTER_QUARANTINE_RETENTION_DAYS`, `ROUTER_SENT_LIST_RETENTION_DAYS`, `ROUTER_PROCESS_TIMEOUT`, `ROUTER_DEFAULT_PRIORITY` and `ROUTER_URGENT_PRIORITY`.

- [ ] **Step 1: Add the settings**

In `adit/settings/base.py`, directly after the `ROUTER_SPOOL_MIN_FREE_GB` line, add:

```python

# A spooled study closes after this long without a new image.
ROUTER_QUIET_PERIOD_SECONDS = env.int("ROUTER_QUIET_PERIOD_SECONDS", default=300)

# A spooled study closes at the latest this long after its first image.
ROUTER_MAX_OPEN_SECONDS = env.int("ROUTER_MAX_OPEN_SECONDS", default=3600)

# The schedule of close_router_batches, which closes, decides and cleans up batches.
ROUTER_CLOSE_CRON = env.str("ROUTER_CLOSE_CRON", default="* * * * *")

# The admins get at most one mail about a low router spool per this many hours.
ROUTER_LOW_SPACE_MAIL_HOURS = env.int("ROUTER_LOW_SPACE_MAIL_HOURS", default=6)

# How long the images of a batch with a failed delivery stay in the spool.
ROUTER_FAILED_RETENTION_DAYS = env.int("ROUTER_FAILED_RETENTION_DAYS", default=7)

# How long unreadable files stay in the spool's quarantine.
ROUTER_QUARANTINE_RETENTION_DAYS = env.int("ROUTER_QUARANTINE_RETENTION_DAYS", default=7)

# How long a delivery's sent SOP Instance UIDs are kept to leave out images sent again.
ROUTER_SENT_LIST_RETENTION_DAYS = env.int("ROUTER_SENT_LIST_RETENTION_DAYS", default=30)

# The process timeout of one router delivery, in seconds.
ROUTER_PROCESS_TIMEOUT = env.int("ROUTER_PROCESS_TIMEOUT", default=3600)
```

In the `# Priorities of dicom tasks` block, after `MASS_TRANSFER_URGENT_PRIORITY = 5`, add:

```python
ROUTER_DEFAULT_PRIORITY = 3
ROUTER_URGENT_PRIORITY = 7
```

- [ ] **Step 2: Write the failing model tests**

Append to `adit/router/tests/test_models.py`. Add these imports at the top:

```python
from adit_radis_shared.accounts.factories import UserFactory
from django.db.models import ProtectedError

from adit.core.models import DicomTask
from adit.router.factories import RouterJobFactory, RouterTaskFactory, RoutingRuleFactory
from adit.router.models import RouterJob, RouterTask, RoutingRule
```

```python
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
    assert task.job.get_absolute_url() == (
        f"/django-admin/router/routerjob/{task.job.pk}/change/"
    )
    assert isinstance(task.job, RouterJob)
```

- [ ] **Step 3: Write the failing admin tests**

Create `adit/router/tests/test_admin.py`:

```python
import pytest
from adit_radis_shared.accounts.factories import UserFactory
from django.contrib.admin.sites import AdminSite
from django.test import RequestFactory

from adit.router.admin import RouterBatchAdmin, RoutingRuleAdmin
from adit.router.factories import RouterBatchFactory, RouterJobFactory, RoutingRuleFactory
from adit.router.models import RouterBatch, RoutingRule


def _request(user):
    request = RequestFactory().get("/")
    request.user = user
    return request


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
    request = _request(UserFactory.create(is_staff=True))
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
def test_batches_are_read_only_in_the_admin():
    admin = RouterBatchAdmin(RouterBatch, AdminSite())
    request = _request(UserFactory.create(is_staff=True, is_superuser=True))

    assert not admin.has_add_permission(request)
    assert not admin.has_change_permission(request, RouterBatchFactory.create())
    assert not admin.has_delete_permission(request)
```

- [ ] **Step 4: Run the tests to verify they fail**

Run: `uv run cli test -- adit/router/tests/test_models.py adit/router/tests/test_admin.py`
Expected: FAIL with `ImportError` (`RouterBatchFactory`, `RoutingRuleAdmin`, ...).

- [ ] **Step 5: Implement the models**

In `adit/router/models.py`:
- Keep `RouterSender` exactly as it is.
- Replace the imports and the `RouterSettings` class at the top with:

```python
import secrets

from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse

from adit.core.models import DicomAppSettings, DicomServer, DicomTask, TransferJob, TransferTask
from adit.core.utils.series_filters import FilterSpec, parse_filters
from adit.core.validators import ae_title_chars_validator, no_backslash_char_validator


class RouterSettings(DicomAppSettings):
    low_space_mailed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name_plural = "Router settings"
```

Then append after `RouterSender`:

```python
class RoutingRule(models.Model):
    name = models.CharField(max_length=100, unique=True)
    enabled = models.BooleanField(default=True)
    filters_json = models.JSONField(
        help_text="The filters that select the series to send, in the mass transfer format."
    )
    destination_id: int
    destination = models.ForeignKey(DicomServer, on_delete=models.PROTECT, related_name="+")
    pseudonymize = models.BooleanField(default=True)
    pseudonym_salt = models.CharField(max_length=64, blank=True, default=secrets.token_hex)
    trial_protocol_id = models.CharField(
        blank=True,
        default="",
        max_length=64,
        validators=[no_backslash_char_validator],
        help_text="XNAT files the images under this project ID.",
    )
    trial_protocol_name = models.CharField(
        blank=True, default="", max_length=64, validators=[no_backslash_char_validator]
    )
    created_by_id: int
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="router_rules"
    )
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    jobs: models.QuerySet["RouterJob"]

    class Meta:
        ordering = ("name",)

    def __str__(self) -> str:
        return self.name

    def clean(self) -> None:
        try:
            self.filters_json = parse_filters(self.filters_json)
        except ValueError as err:
            raise ValidationError({"filters_json": str(err)}) from err

        if not self.pseudonymize:
            self.pseudonym_salt = ""
        elif not self.pseudonym_salt:
            self.pseudonym_salt = secrets.token_hex()

        if self.pk is not None and self.jobs.exists():
            saved = RoutingRule.objects.get(pk=self.pk)
            if (saved.pseudonymize, saved.pseudonym_salt) != (
                self.pseudonymize,
                self.pseudonym_salt,
            ):
                # A patient must keep the same pseudonym under a rule.
                raise ValidationError(
                    "Pseudonymization can't change once the rule has sent studies. "
                    "Create a new rule instead."
                )

        if self.destination_id is not None:
            destination = self.destination
            if not (destination.store_scp_support or destination.dicomweb_stow_support):
                raise ValidationError(
                    {"destination": "The destination must support C-STORE or STOW-RS."}
                )

    def get_filters(self) -> list[FilterSpec]:
        return [FilterSpec.from_dict(d) for d in self.filters_json]


class RouterBatch(models.Model):
    batch_id = models.UUIDField(unique=True)
    sender_id: int
    sender = models.ForeignKey(RouterSender, on_delete=models.PROTECT, related_name="batches")
    study_instance_uid = models.CharField(max_length=64)
    number_of_images = models.PositiveIntegerField()
    closed_at = models.DateTimeField(auto_now_add=True)
    files_deleted_at = models.DateTimeField(null=True, blank=True)

    jobs: models.QuerySet["RouterJob"]

    class Meta:
        ordering = ("-closed_at",)
        verbose_name_plural = "Router batches"

    def __str__(self) -> str:
        return f"Router batch {self.batch_id}"


class RouterJob(TransferJob):
    default_priority = settings.ROUTER_DEFAULT_PRIORITY
    urgent_priority = settings.ROUTER_URGENT_PRIORITY

    rule_id: int
    rule = models.ForeignKey(RoutingRule, on_delete=models.PROTECT, related_name="jobs")
    batch = models.ForeignKey(RouterBatch, on_delete=models.PROTECT, related_name="jobs")

    tasks: models.QuerySet["RouterTask"]

    class Meta(TransferJob.Meta):
        constraints = [
            models.UniqueConstraint(fields=["rule", "batch"], name="router_unique_rule_batch")
        ]

    def get_absolute_url(self) -> str:
        return reverse("admin:router_routerjob_change", args=[self.pk])


class RouterTask(TransferTask):
    job = models.ForeignKey(RouterJob, on_delete=models.CASCADE, related_name="tasks")
    sent_instance_uids = ArrayField(models.CharField(max_length=64), blank=True, default=list)

    class Meta(TransferTask.Meta):
        indexes = [models.Index(fields=["study_uid"])]

    def get_absolute_url(self) -> str:
        return reverse("admin:router_routertask_change", args=[self.pk])

    @classmethod
    def already_sent(cls, rule_id: int, study_uid: str, destination_id: int) -> set[str]:
        """The SOP Instance UIDs a rule's finished deliveries sent of a study to a destination."""
        sent: set[str] = set()
        tasks = cls.objects.filter(
            job__rule_id=rule_id,
            study_uid=study_uid,
            destination_id=destination_id,
            status__in=[DicomTask.Status.SUCCESS, DicomTask.Status.WARNING],
        )
        for uids in tasks.values_list("sent_instance_uids", flat=True):
            sent.update(uids)
        return sent
```

`class Meta(TransferJob.Meta)` and `class Meta(TransferTask.Meta)` keep the inherited owner/status index, the permissions (`router.can_transfer_unpseudonymized`) and the task ordering. A bare `class Meta:` would silently drop them.

- [ ] **Step 6: Implement the admin**

Replace `adit/router/admin.py` with:

```python
from typing import Any, cast

from django import forms
from django.contrib import admin
from django.http import HttpRequest

from adit.core.admin import DicomJobAdmin, DicomTaskAdmin

from .models import RouterBatch, RouterJob, RouterSender, RouterSettings, RouterTask, RoutingRule


class RouterSenderAdmin(admin.ModelAdmin):
    list_display = ("calling_ae_title", "server", "enabled")
    list_filter = ("enabled",)


class RoutingRuleAdminForm(forms.ModelForm):
    # Set by RoutingRuleAdmin.get_form to the user editing the rule.
    request_user: Any = None

    class Meta:
        model = RoutingRule
        fields = "__all__"

    def clean(self) -> dict[str, Any]:
        cleaned_data = super().clean()
        user = self.request_user
        if (
            cleaned_data.get("pseudonymize") is False
            and user is not None
            and not user.has_perm("router.can_transfer_unpseudonymized")
        ):
            self.add_error(
                "pseudonymize", "You are not allowed to send studies without pseudonymization."
            )
        return cleaned_data


class RoutingRuleAdmin(admin.ModelAdmin):
    form = RoutingRuleAdminForm
    list_display = ("name", "enabled", "destination", "pseudonymize", "created_by")
    list_filter = ("enabled",)

    def get_readonly_fields(self, request: HttpRequest, obj: Any = None) -> list[str]:
        fields = ["created_by", "created", "updated"]
        if obj is not None and obj.jobs.exists():
            # A patient must keep the same pseudonym under a rule.
            fields += ["pseudonymize", "pseudonym_salt"]
        return fields

    def get_form(
        self, request: HttpRequest, obj: Any = None, change: bool = False, **kwargs: Any
    ) -> Any:
        form = cast(
            type[RoutingRuleAdminForm], super().get_form(request, obj, change, **kwargs)
        )
        form.request_user = request.user
        return form

    def save_model(self, request: HttpRequest, obj: Any, form: Any, change: bool) -> None:
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


class ReadOnlyAdmin(admin.ModelAdmin):
    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False


class RouterBatchAdmin(ReadOnlyAdmin):
    list_display = (
        "batch_id",
        "sender",
        "study_instance_uid",
        "number_of_images",
        "closed_at",
        "files_deleted_at",
    )


class RouterJobAdmin(ReadOnlyAdmin, DicomJobAdmin):
    list_display = (*DicomJobAdmin.list_display, "rule", "batch")


class RouterTaskAdmin(ReadOnlyAdmin, DicomTaskAdmin):
    pass


admin.site.register(RouterSender, RouterSenderAdmin)
admin.site.register(RouterSettings, admin.ModelAdmin)
admin.site.register(RoutingRule, RoutingRuleAdmin)
admin.site.register(RouterBatch, RouterBatchAdmin)
admin.site.register(RouterJob, RouterJobAdmin)
admin.site.register(RouterTask, RouterTaskAdmin)
```

- [ ] **Step 7: Add the factories**

In `adit/router/factories.py`:
- Keep `RouterSenderFactory`.
- Change the imports to:

```python
import uuid

import factory
from adit_radis_shared.accounts.factories import UserFactory
from adit_radis_shared.common.factories import BaseDjangoModelFactory
from pydicom.uid import generate_uid

from adit.core.factories import (
    AbstractTransferJobFactory,
    AbstractTransferTaskFactory,
    DicomServerFactory,
)

from .models import RouterBatch, RouterJob, RouterSender, RouterTask, RoutingRule
```

and append:

```python
class RoutingRuleFactory(BaseDjangoModelFactory[RoutingRule]):
    class Meta:
        model = RoutingRule

    name = factory.Sequence(lambda n: f"Rule {n}")
    filters_json = factory.LazyFunction(lambda: [{"mode": "include", "modality": "CT"}])
    destination = factory.SubFactory(DicomServerFactory)
    created_by = factory.SubFactory(UserFactory)


class RouterBatchFactory(BaseDjangoModelFactory[RouterBatch]):
    class Meta:
        model = RouterBatch

    batch_id = factory.LazyFunction(uuid.uuid4)
    sender = factory.SubFactory(RouterSenderFactory)
    study_instance_uid = factory.LazyFunction(generate_uid)
    number_of_images = 1


class RouterJobFactory(AbstractTransferJobFactory[RouterJob]):
    class Meta:
        model = RouterJob

    status = RouterJob.Status.PENDING
    urgent = False
    rule = factory.SubFactory(RoutingRuleFactory)
    batch = factory.SubFactory(RouterBatchFactory)


class RouterTaskFactory(AbstractTransferTaskFactory[RouterTask]):
    class Meta:
        model = RouterTask

    job = factory.SubFactory(RouterJobFactory)
    status = RouterTask.Status.PENDING
    series_uids = factory.LazyFunction(list)
    pseudonym = ""
```

- [ ] **Step 8: Generate the migration**

Run: `$COMPOSE exec web ./manage.py makemigrations router --name rules_and_deliveries`, then copy it out: `$COMPOSE cp web:/app/adit/router/migrations/0002_rules_and_deliveries.py adit/router/migrations/`.
Then run `$COMPOSE exec web ./manage.py makemigrations --check --dry-run`.
Expected: `0002_rules_and_deliveries.py` with `AddField(low_space_mailed_at)`, `CreateModel` for `RoutingRule`, `RouterBatch`, `RouterJob` and `RouterTask`, the index on `study_uid` and the `router_unique_rule_batch` constraint. Then "No changes detected".

- [ ] **Step 9: Run the tests to verify they pass**

Run: `uv run cli test -- adit/router/`
Expected: PASS.

- [ ] **Step 10: Commit**

```bash
git add adit/settings/base.py adit/router/models.py adit/router/migrations/0002_rules_and_deliveries.py \
  adit/router/admin.py adit/router/factories.py adit/router/tests/test_models.py adit/router/tests/test_admin.py
git commit -m "Add routing rules, router batches and router jobs"
```

---

### Task 3: Closing, listing and reading batches in the spool

**Files:**
- Modify: `adit/router/utils/spool.py`
- Create: `adit/router/utils/batches.py`
- Test: `adit/router/tests/test_spool.py`, `adit/router/tests/test_batches.py` (new)

**Interfaces:**
- Consumes:
  - `spool.TMP`, `INCOMING`, `BATCHES`, `QUARANTINE`, `_ensure_dir`, `_fsync_dir` and `store_dataset` (stage 2).
  - `DiscoveredSeries` (core), `convert_to_python_date` and `convert_to_python_time` (`adit/core/utils/dicom_utils.py`).
- Produces in `spool`:
  - `class BatchDir(NamedTuple): sender_id: int; batch_id: uuid.UUID; path: Path`
  - `batch_dir(spool_root: Path, sender_id: int, batch_id: uuid.UUID) -> Path`
  - `close_due_studies(spool_root: Path, now: float, quiet_seconds: int, max_open_seconds: int) -> list[BatchDir]`
  - `list_batches(spool_root: Path) -> list[BatchDir]`
  - `delete_batch(path: Path) -> None`
  - `quarantine_file(spool_root: Path, path: Path, today: date) -> Path`
  - `clean_quarantine(spool_root: Path, today: date, retention_days: int) -> int`
  - `clean_old_tmp(spool_root: Path, now: float, max_age_seconds: int) -> int`
- Produces in `batches`:
  - `SpooledImage(path, sop_instance_uid, series_instance_uid)`
  - `BatchStudy(ModalitiesInStudy, StudyDescription, PatientBirthDate, StudyDate)`, a `StudyFacts`
  - `BatchContents(patient_id, study_instance_uid, study, series, images)`
  - `read_batch(spool_root: Path, batch_path: Path, today: date) -> BatchContents`
  - `read_series_images(batch_path: Path, series_uids: set[str]) -> list[SpooledImage]`

- [ ] **Step 1: Write the failing spool tests**

Append to `adit/router/tests/test_spool.py`. The module already has `_dataset()` and the `spool_root` fixture. Add `from datetime import date` and `import uuid` to the imports if the module doesn't have them yet:

```python
def _age(path, seconds_ago: float, now: float) -> None:
    os.utime(path, (now - seconds_ago, now - seconds_ago))


def _open_study(spool_root, sender_id=7, images=1):
    paths = [spool.store_dataset(spool_root, sender_id, _dataset(study_uid="1.2.3")) for _ in range(images)]
    return paths[0].parent


def test_quiet_study_closes_into_a_batch(spool_root):
    study_dir = _open_study(spool_root, images=2)
    now = study_dir.stat().st_mtime + 301

    [batch] = spool.close_due_studies(spool_root, now, quiet_seconds=300, max_open_seconds=3600)

    assert batch.sender_id == 7
    assert batch.path == spool.batch_dir(spool_root, 7, batch.batch_id)
    assert len(list(batch.path.iterdir())) == 2
    assert not study_dir.exists()
    assert (spool_root / spool.INCOMING / "7").is_dir()


def test_study_that_got_an_image_recently_stays_open(spool_root):
    study_dir = _open_study(spool_root)
    now = study_dir.stat().st_mtime + 10

    assert spool.close_due_studies(spool_root, now, quiet_seconds=300, max_open_seconds=3600) == []
    assert study_dir.is_dir()


def test_study_open_too_long_closes_even_while_images_arrive(spool_root):
    study_dir = _open_study(spool_root)
    now = study_dir.stat().st_mtime + 10
    for path in study_dir.iterdir():
        _age(path, 4000, now)

    [batch] = spool.close_due_studies(spool_root, now, quiet_seconds=300, max_open_seconds=3600)

    assert batch.path.is_dir()


def test_quiet_empty_study_folder_is_removed(spool_root):
    study_dir = spool_root / spool.INCOMING / "7" / "1.2.3"
    study_dir.mkdir(parents=True)
    now = study_dir.stat().st_mtime + 301

    assert spool.close_due_studies(spool_root, now, quiet_seconds=300, max_open_seconds=3600) == []
    assert not study_dir.exists()


def test_image_arriving_after_closing_starts_the_next_batch(spool_root):
    study_dir = _open_study(spool_root)
    spool.close_due_studies(
        spool_root, study_dir.stat().st_mtime + 301, quiet_seconds=300, max_open_seconds=3600
    )

    path = spool.store_dataset(spool_root, 7, _dataset(study_uid="1.2.3"))

    assert path.parent == study_dir
    assert len(spool.list_batches(spool_root)) == 1


def test_list_batches_ignores_foreign_folders(spool_root):
    batch_id = uuid.uuid4()
    spool.batch_dir(spool_root, 7, batch_id).mkdir(parents=True)
    (spool_root / spool.BATCHES / "7" / "not-a-uuid").mkdir()
    (spool_root / spool.BATCHES / "lost+found").mkdir()

    assert spool.list_batches(spool_root) == [
        spool.BatchDir(7, batch_id, spool.batch_dir(spool_root, 7, batch_id))
    ]


def test_delete_batch_tolerates_a_folder_that_is_already_gone(spool_root):
    path = spool.batch_dir(spool_root, 7, uuid.uuid4())

    spool.delete_batch(path)

    assert not path.exists()


def test_quarantine_keeps_files_until_their_retention_ends(spool_root):
    bad = spool_root / spool.TMP / "bad.dcm"
    bad.write_bytes(b"not dicom")

    moved = spool.quarantine_file(spool_root, bad, date(2026, 10, 1))

    assert moved.parent == spool_root / spool.QUARANTINE / "20261001"
    assert moved.read_bytes() == b"not dicom"
    assert spool.clean_quarantine(spool_root, date(2026, 10, 8), retention_days=7) == 0
    assert spool.clean_quarantine(spool_root, date(2026, 10, 9), retention_days=7) == 1
    assert not moved.parent.exists()


def test_clean_old_tmp_spares_files_being_written(spool_root):
    old = spool_root / spool.TMP / "old.dcm"
    new = spool_root / spool.TMP / "new.dcm"
    old.write_bytes(b"x")
    new.write_bytes(b"x")
    now = new.stat().st_mtime + 10
    _age(old, 3700, now)

    assert spool.clean_old_tmp(spool_root, now, max_age_seconds=3600) == 1
    assert not old.exists()
    assert new.exists()
```

- [ ] **Step 2: Write the failing batch reading tests**

Create `adit/router/tests/test_batches.py`:

```python
import uuid
from datetime import date
from pathlib import Path

import pytest
from pydicom import Dataset

from adit.core.utils.dicom_utils import write_dataset
from adit.core.utils.testing_helpers import load_sample_dicoms
from adit.router.utils import spool
from adit.router.utils.batches import read_batch, read_series_images

TODAY = date(2026, 10, 4)


@pytest.fixture
def spool_root(tmp_path: Path) -> Path:
    spool.ensure_spool_dirs(tmp_path)
    return tmp_path


def _batch(spool_root: Path, datasets: list[Dataset]) -> Path:
    path = spool.batch_dir(spool_root, 7, uuid.uuid4())
    path.mkdir(parents=True)
    for ds in datasets:
        write_dataset(ds, path / f"{ds.SOPInstanceUID}.dcm")
    return path


def test_batch_contents_describe_the_study(spool_root):
    datasets = list(load_sample_dicoms("1001"))  # three CT series (2, 4, 4 images), one SR
    path = _batch(spool_root, datasets)

    contents = read_batch(spool_root, path, TODAY)

    assert contents.patient_id == "1001"
    assert contents.study_instance_uid == str(datasets[0].StudyInstanceUID)
    assert len(contents.images) == len(datasets)
    assert contents.study.ModalitiesInStudy == ["CT", "SR"]
    assert contents.study.PatientBirthDate == date(1945, 4, 27)
    assert sorted((s.modality, s.number_of_images) for s in contents.series) == [
        ("CT", 2),
        ("CT", 4),
        ("CT", 4),
        ("SR", 1),
    ]


def test_unreadable_files_go_to_the_quarantine(spool_root):
    datasets = list(load_sample_dicoms("1004"))[:2]
    path = _batch(spool_root, datasets)
    (path / "broken.dcm").write_bytes(b"not dicom")
    no_uid = datasets[0].copy()
    del no_uid.SOPInstanceUID
    write_dataset(no_uid, path / "no-uid.dcm")

    contents = read_batch(spool_root, path, TODAY)

    assert len(contents.images) == 2
    quarantined = sorted(p.name.split("_", 1)[1] for p in (spool_root / spool.QUARANTINE / "20261004").iterdir())
    assert quarantined == ["broken.dcm", "no-uid.dcm"]


def test_missing_birth_date_leaves_the_age_unknown(spool_root):
    datasets = list(load_sample_dicoms("1004"))[:1]
    del datasets[0].PatientBirthDate
    path = _batch(spool_root, datasets)

    contents = read_batch(spool_root, path, TODAY)

    assert contents.study.PatientBirthDate is None
    assert contents.series[0].patient_birth_date is None


def test_missing_study_date_leaves_the_age_unknown(spool_root):
    datasets = list(load_sample_dicoms("1004"))[:1]
    datasets[0].StudyDate = ""
    path = _batch(spool_root, datasets)

    contents = read_batch(spool_root, path, TODAY)

    assert contents.study.StudyDate is None
    assert contents.series[0].patient_birth_date is None


def test_read_series_images_lists_only_the_requested_series(spool_root):
    datasets = list(load_sample_dicoms("1001"))
    path = _batch(spool_root, datasets)
    ct_series = {str(ds.SeriesInstanceUID) for ds in datasets if ds.Modality == "CT"}

    images = read_series_images(path, ct_series)

    assert len(images) == 10
    assert {image.series_instance_uid for image in images} == ct_series
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `uv run cli test -- adit/router/tests/test_spool.py adit/router/tests/test_batches.py`
Expected: FAIL with `AttributeError: module 'adit.router.utils.spool' has no attribute 'close_due_studies'` and `ModuleNotFoundError: adit.router.utils.batches`.

- [ ] **Step 4: Implement the spool functions**

In `adit/router/utils/spool.py`, change the imports to:

```python
import logging
import os
import re
import shutil
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import NamedTuple

from pydicom import Dataset

from adit.core.utils.dicom_utils import write_dataset

logger = logging.getLogger(__name__)
```

and append:

```python
class BatchDir(NamedTuple):
    sender_id: int
    batch_id: uuid.UUID
    path: Path


def batch_dir(spool_root: Path, sender_id: int, batch_id: uuid.UUID) -> Path:
    return spool_root / BATCHES / str(sender_id) / str(batch_id)


def close_due_studies(
    spool_root: Path, now: float, quiet_seconds: int, max_open_seconds: int
) -> list[BatchDir]:
    """Close every study folder that is due and return the batches made from them.

    A folder is due when its modification time, which every image moved in updates, is
    *quiet_seconds* old, or when its oldest file is *max_open_seconds* old. Closing
    renames it into batches/<sender id>/<new uuid>/, so an image moved in at the same
    time lands either in the batch or, retried by the store, in a new study folder.
    Empty study folders, left by a store whose move failed, are removed once quiet.
    """
    closed: list[BatchDir] = []
    for sender_id, sender_dir in _sender_dirs(spool_root / INCOMING):
        for study_dir in _subdirs(sender_dir):
            batch = _close_if_due(
                spool_root, sender_id, study_dir, now, quiet_seconds, max_open_seconds
            )
            if batch is not None:
                closed.append(batch)
    return closed


def list_batches(spool_root: Path) -> list[BatchDir]:
    batches: list[BatchDir] = []
    for sender_id, sender_dir in _sender_dirs(spool_root / BATCHES):
        for path in _subdirs(sender_dir):
            try:
                batch_id = uuid.UUID(path.name)
            except ValueError:
                logger.warning("Ignoring %s: not a router batch folder.", path)
                continue
            batches.append(BatchDir(sender_id, batch_id, path))
    return batches


def delete_batch(path: Path) -> None:
    try:
        shutil.rmtree(path)
    except FileNotFoundError:
        pass


def quarantine_file(spool_root: Path, path: Path, today: date) -> Path:
    """Move an unreadable file to quarantine/<YYYYMMDD>/ and return its new path."""
    target_dir = spool_root / QUARANTINE / today.strftime("%Y%m%d")
    _ensure_dir(target_dir)
    target = target_dir / f"{uuid.uuid4().hex}_{path.name}"
    os.replace(path, target)
    return target


def clean_quarantine(spool_root: Path, today: date, retention_days: int) -> int:
    """Delete the quarantine days older than *retention_days*; returns how many."""
    oldest_kept = today - timedelta(days=retention_days)
    removed = 0
    for day_dir in _subdirs(spool_root / QUARANTINE):
        try:
            day = datetime.strptime(day_dir.name, "%Y%m%d").date()
        except ValueError:
            continue
        if day < oldest_kept:
            shutil.rmtree(day_dir)
            removed += 1
    return removed


def clean_old_tmp(spool_root: Path, now: float, max_age_seconds: int) -> int:
    """Delete files in tmp/ older than *max_age_seconds*; returns how many.

    The router empties tmp/ when it starts. This catches files left behind while it
    runs, without touching the ones it is writing.
    """
    removed = 0
    for path in (spool_root / TMP).iterdir():
        try:
            if now - path.stat().st_mtime >= max_age_seconds:
                path.unlink()
                removed += 1
        except FileNotFoundError:
            continue
    return removed


def _close_if_due(
    spool_root: Path,
    sender_id: int,
    study_dir: Path,
    now: float,
    quiet_seconds: int,
    max_open_seconds: int,
) -> BatchDir | None:
    try:
        quiet = now - study_dir.stat().st_mtime >= quiet_seconds
        file_times = [p.stat().st_mtime for p in study_dir.iterdir() if p.is_file()]
    except FileNotFoundError:
        return None

    if not file_times:
        if quiet:
            try:
                study_dir.rmdir()
            except OSError:
                pass  # an image was moved in meanwhile
        return None

    if not quiet and now - min(file_times) < max_open_seconds:
        return None

    batch_id = uuid.uuid4()
    target = batch_dir(spool_root, sender_id, batch_id)
    _ensure_dir(target.parent)
    os.rename(study_dir, target)
    _fsync_dir(study_dir.parent)
    _fsync_dir(target.parent)
    return BatchDir(sender_id, batch_id, target)


def _sender_dirs(path: Path) -> list[tuple[int, Path]]:
    sender_dirs: list[tuple[int, Path]] = []
    for sender_dir in _subdirs(path):
        try:
            sender_dirs.append((int(sender_dir.name), sender_dir))
        except ValueError:
            logger.warning("Ignoring %s: not a router sender folder.", sender_dir)
    return sender_dirs


def _subdirs(path: Path) -> list[Path]:
    return sorted(p for p in path.iterdir() if p.is_dir())
```

- [ ] **Step 5: Implement batch reading**

Create `adit/router/utils/batches.py`:

```python
"""Reads the headers of the images in a closed router batch."""

import logging
from dataclasses import dataclass
from datetime import date, datetime, time
from pathlib import Path

from pydicom import Dataset, dcmread

from adit.core.utils.dicom_utils import convert_to_python_date, convert_to_python_time
from adit.core.utils.series_filters import DiscoveredSeries

from . import spool

logger = logging.getLogger(__name__)

_REQUIRED_UIDS = ("SOPInstanceUID", "SeriesInstanceUID", "StudyInstanceUID")


@dataclass(frozen=True)
class SpooledImage:
    path: Path
    sop_instance_uid: str
    series_instance_uid: str


@dataclass(frozen=True)
class BatchStudy:
    """The study-level facts of a batch (a StudyFacts), read from its headers."""

    ModalitiesInStudy: list[str]
    StudyDescription: str
    PatientBirthDate: date | None
    StudyDate: date | None


@dataclass(frozen=True)
class BatchContents:
    patient_id: str
    study_instance_uid: str
    study: BatchStudy
    series: list[DiscoveredSeries]
    images: list[SpooledImage]


def read_batch(spool_root: Path, batch_path: Path, today: date) -> BatchContents:
    """Read the headers of a batch. Files that can't be read move to the quarantine."""
    headers: list[tuple[Path, Dataset]] = []
    for path in sorted(p for p in batch_path.iterdir() if p.is_file()):
        try:
            headers.append((path, _read_header(path)))
        except Exception:
            logger.warning("Moving unreadable file %s to the router quarantine.", path, exc_info=True)
            spool.quarantine_file(spool_root, path, today)

    if not headers:
        return BatchContents("", "", BatchStudy([], "", None, None), [], [])

    first = headers[0][1]
    birth_date = _parse_date(first.get("PatientBirthDate"), "PatientBirthDate", batch_path)
    study_date = _parse_date(first.get("StudyDate"), "StudyDate", batch_path)
    study_time = _parse_time(first.get("StudyTime"))
    # The age needs both dates; without a study date it counts as unknown.
    series_birth_date = birth_date if study_date else None
    study_datetime = datetime.combine(study_date or date.min, study_time or time())

    by_series: dict[str, list[Dataset]] = {}
    for _, ds in headers:
        by_series.setdefault(str(ds.SeriesInstanceUID), []).append(ds)

    series: list[DiscoveredSeries] = []
    for series_uid, datasets in by_series.items():
        ds = datasets[0]
        series.append(
            DiscoveredSeries(
                patient_id=str(first.get("PatientID", "")),
                accession_number=str(first.get("AccessionNumber", "")),
                study_instance_uid=str(first.StudyInstanceUID),
                series_instance_uid=series_uid,
                modality=str(ds.get("Modality", "")),
                study_description=str(first.get("StudyDescription", "")),
                series_description=str(ds.get("SeriesDescription", "")),
                series_number=_parse_int(ds.get("SeriesNumber")),
                study_datetime=study_datetime,
                institution_name=str(ds.get("InstitutionName", "")),
                number_of_images=len(datasets),
                patient_birth_date=series_birth_date,
            )
        )

    return BatchContents(
        patient_id=str(first.get("PatientID", "")),
        study_instance_uid=str(first.StudyInstanceUID),
        study=BatchStudy(
            ModalitiesInStudy=sorted({s.modality for s in series if s.modality}),
            StudyDescription=str(first.get("StudyDescription", "")),
            PatientBirthDate=birth_date,
            StudyDate=study_date,
        ),
        series=series,
        images=[
            SpooledImage(path, str(ds.SOPInstanceUID), str(ds.SeriesInstanceUID))
            for path, ds in headers
        ],
    )


def read_series_images(batch_path: Path, series_uids: set[str]) -> list[SpooledImage]:
    images: list[SpooledImage] = []
    for path in sorted(p for p in batch_path.iterdir() if p.is_file()):
        ds = dcmread(path, stop_before_pixels=True)
        if str(ds.SeriesInstanceUID) in series_uids:
            images.append(SpooledImage(path, str(ds.SOPInstanceUID), str(ds.SeriesInstanceUID)))
    return images


def _read_header(path: Path) -> Dataset:
    ds = dcmread(path, stop_before_pixels=True)
    for keyword in _REQUIRED_UIDS:
        if not ds.get(keyword):
            raise ValueError(f"{keyword} is missing.")
    return ds


def _parse_date(value: object, keyword: str, batch_path: Path) -> date | None:
    if not value:
        return None
    try:
        return convert_to_python_date(str(value))
    except ValueError:
        logger.warning("Ignoring the invalid %s %r of router batch %s.", keyword, value, batch_path)
        return None


def _parse_time(value: object) -> time | None:
    if not value:
        return None
    try:
        return convert_to_python_time(str(value))
    except ValueError:
        return None


def _parse_int(value: object) -> int | None:
    try:
        return int(str(value))
    except ValueError:
        return None
```

`_parse_int(None)` gives `int("None")`, which raises `ValueError` and so returns `None`.

- [ ] **Step 6: Run the tests to verify they pass**

Run: `uv run cli test -- adit/router/tests/test_spool.py adit/router/tests/test_batches.py`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add adit/router/utils/spool.py adit/router/utils/batches.py \
  adit/router/tests/test_spool.py adit/router/tests/test_batches.py
git commit -m "Close quiet router studies into batches and read their headers"
```

---

### Task 4: Core support for deliveries

**Files:**
- Modify: `adit/core/utils/presentation_contexts.py` (`storage_scp_contexts`, new `requested_store_contexts`)
- Modify: `adit/core/utils/dimse_connector.py` (`DimseConnector.__init__`, `_associate`)
- Modify: `adit/core/utils/dicom_operator.py` (`DicomOperator.__init__`)
- Modify: `adit/core/tasks.py` (the final save in `_run_dicom_task`)
- Test: `adit/core/tests/utils/test_presentation_contexts.py`, `adit/core/tests/utils/test_dimse_connector.py`, `adit/core/tests/test_tasks.py`

**Interfaces:**
- Consumes: the existing `StoragePresentationContexts`, `DEFAULT_TRANSFER_SYNTAXES` and `_compressed_transfer_syntaxes`.
- Produces:
  - `requested_store_contexts(pairs: Iterable[tuple[str, str]]) -> list[PresentationContext]`, raising `DicomError` above 128 contexts.
  - `DimseConnector(..., store_contexts: list[PresentationContext] | None = None)`.
  - `DicomOperator(server, persistent=False, dimse_timeout=60, store_contexts: list[PresentationContext] | None = None)`.
  - `_run_dicom_task` saves only the fields it owns, so a processor can save fields of its task.
  - `storage_scp_contexts()` accepts the compressed transfer syntaxes for every storage class.

- [ ] **Step 1: Write the failing tests**

In `adit/core/tests/utils/test_presentation_contexts.py`, delete the three tests `test_image_classes_accept_compressed_and_uncompressed_syntaxes`, `test_non_image_classes_accept_only_uncompressed_syntaxes` and `test_newer_image_classes_accept_compressed_syntaxes`. Add `import pytest`, add `from adit.core.errors import DicomError`, and change the import to `from adit.core.utils.presentation_contexts import requested_store_contexts, storage_scp_contexts`. Then append:

```python
def test_every_storage_class_accepts_default_and_compressed_syntaxes():
    for syntaxes in _syntaxes_by_class().values():
        assert ImplicitVRLittleEndian in syntaxes
        assert ExplicitVRLittleEndian in syntaxes
        assert JPEGLosslessSV1 in syntaxes


def test_pixel_data_classes_without_image_in_their_name_accept_compressed_syntaxes():
    syntaxes = _syntaxes_by_class()

    assert JPEGLosslessSV1 in syntaxes["1.2.840.10008.5.1.4.1.1.481.2"]  # RT Dose Storage
    assert JPEGLosslessSV1 in syntaxes["1.2.840.10008.5.1.4.1.1.66.4"]  # Segmentation Storage


def test_requested_store_contexts_has_one_context_per_pair():
    contexts = requested_store_contexts(
        [
            (CTImageStorage, JPEGLosslessSV1),
            (CTImageStorage, ExplicitVRLittleEndian),
            (CTImageStorage, JPEGLosslessSV1),
        ]
    )

    assert [
        (str(cx.abstract_syntax), [str(ts) for ts in cx.transfer_syntax]) for cx in contexts
    ] == [
        (CTImageStorage, [ExplicitVRLittleEndian]),
        (CTImageStorage, [JPEGLosslessSV1]),
    ]


def test_requested_store_contexts_refuses_more_than_one_association_carries():
    pairs = [(f"1.2.3.{i}", ExplicitVRLittleEndian) for i in range(129)]

    with pytest.raises(DicomError, match="128"):
        requested_store_contexts(pairs)
```

Append to `adit/core/tests/utils/test_dimse_connector.py`. Add the imports it lacks: `from pydicom import Dataset`, `from pydicom.uid import CTImageStorage, JPEGLosslessSV1, generate_uid`, `from adit.core.factories import DicomServerFactory`, `from adit.core.utils.dimse_connector import DimseConnector`, `from adit.core.utils.presentation_contexts import requested_store_contexts` and `from adit.core.utils.testing_helpers import create_association_mock`.

```python
@pytest.mark.django_db
def test_c_store_requests_the_given_contexts(mocker):
    server = DicomServerFactory.create(store_scp_support=True)
    contexts = requested_store_contexts([(CTImageStorage, JPEGLosslessSV1)])
    association = create_association_mock()
    association.is_alive.return_value = True
    status = Dataset()
    status.Status = 0x0000
    association.send_c_store.return_value = status
    associate = mocker.patch(
        "adit.core.utils.dimse_connector.AE.associate", autospec=True, return_value=association
    )
    ds = Dataset()
    ds.SOPClassUID = CTImageStorage
    ds.SOPInstanceUID = generate_uid()
    ds.StudyInstanceUID = generate_uid()

    DimseConnector(server, store_contexts=contexts).send_c_store([ds])

    ae = associate.call_args.args[0]
    assert [
        (str(cx.abstract_syntax), [str(ts) for ts in cx.transfer_syntax])
        for cx in ae.requested_contexts
    ] == [(CTImageStorage, [JPEGLosslessSV1])]
```

Append to `adit/core/tests/test_tasks.py`:

```python
@pytest.mark.django_db(transaction=True)
def test_run_dicom_task_keeps_fields_the_processor_saved(mocker: MockerFixture):
    """The processor runs in a child process and may save fields of its task; the runner
    must not write them back from its older copy when it saves the result."""
    dicom_job = ExampleTransferJobFactory.create(status=DicomJob.Status.PENDING)
    dicom_task = ExampleTransferTaskFactory.create(
        status=DicomTask.Status.PENDING, job=dicom_job, pseudonym="BEFORE"
    )
    result: ProcessingResult = {"status": DicomTask.Status.SUCCESS, "message": "ok", "log": ""}

    def process_that_saves_a_field(*p_args, **p_kwargs):
        def decorator(func):
            def wrapper(*args, **kwargs):
                ExampleTransferTask.objects.filter(pk=dicom_task.pk).update(pseudonym="CHILD")
                return _FakeFuture(result=result)

            return wrapper

        return decorator

    _install_pebble_stubs(mocker, future=_FakeFuture(result=result))
    mocker.patch.object(tasks_module.concurrent, "process", side_effect=process_that_saves_a_field)

    tasks_module._run_dicom_task(
        _make_context(), get_model_label(ExampleTransferTask), dicom_task.pk
    )

    dicom_task.refresh_from_db()
    assert dicom_task.status == DicomTask.Status.SUCCESS
    assert dicom_task.pseudonym == "CHILD"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run cli test -- adit/core/tests/utils/test_presentation_contexts.py adit/core/tests/utils/test_dimse_connector.py adit/core/tests/test_tasks.py -k "contexts or syntaxes or keeps_fields"`
Expected: FAIL. The import of `requested_store_contexts` fails, `DimseConnector` rejects `store_contexts`, and `pseudonym` is "BEFORE".

- [ ] **Step 3: Implement the contexts**

In `adit/core/utils/presentation_contexts.py`:
- Replace `from pydicom.uid import UID` with `from collections.abc import Iterable`.
- Add `from ..errors import DicomError` after the pynetdicom imports.
- Replace `storage_scp_contexts()` with:

```python
def storage_scp_contexts() -> list[PresentationContext]:
    """Presentation contexts for a Storage SCP that keeps datasets as received.

    Covers every storage SOP class pynetdicom knows plus the ones listed above, each
    with pynetdicom's default and the compressed transfer syntaxes. The SCP stores data
    without decoding it, and whoever forwards it later requests exactly the pairs it
    holds (requested_store_contexts).
    """
    syntaxes = [str(ts) for ts in DEFAULT_TRANSFER_SYNTAXES] + _compressed_transfer_syntaxes
    uids = {str(cx.abstract_syntax) for cx in AllStoragePresentationContexts}
    uids |= set(_image_storage) | set(_non_image_storage)
    return [build_context(uid, syntaxes) for uid in sorted(uids)]


def requested_store_contexts(pairs: Iterable[tuple[str, str]]) -> list[PresentationContext]:
    """One requested presentation context per (SOP class, transfer syntax) pair.

    Lets a C-STORE send datasets exactly as they are stored, whatever their SOP class
    and transfer syntax.
    """
    contexts = [build_context(sop_class, syntax) for sop_class, syntax in sorted(set(pairs))]
    if len(contexts) > 128:
        raise DicomError(
            f"The images need {len(contexts)} presentation contexts, more than one "
            "association can request (128)."
        )
    return contexts
```

- [ ] **Step 4: Let the connector and operator request given contexts**

In `adit/core/utils/dimse_connector.py`:
- Add `PresentationContext,` to the `from pynetdicom.presentation import (...)` list.
- Add the parameter `store_contexts: list[PresentationContext] | None = None,` after `network_timeout` in `DimseConnector.__init__`, with `self.store_contexts = store_contexts` in the body.
- In `_associate`, replace the C-STORE branch with:

```python
        elif service == "C-STORE":
            ae.requested_contexts = self.store_contexts or StoragePresentationContexts
```

In `adit/core/utils/dicom_operator.py`:
- Add `from pynetdicom.presentation import PresentationContext` to the imports.
- Change `DicomOperator.__init__` to:

```python
    def __init__(
        self,
        server: DicomServer,
        persistent: bool = False,
        dimse_timeout: int | None = 60,
        store_contexts: list[PresentationContext] | None = None,
    ):
        self.server = server
        self.dimse_connector = DimseConnector(
            server,
            auto_close=not persistent,
            dimse_timeout=dimse_timeout,
            store_contexts=store_contexts,
        )
```

Keep the rest of `__init__` as it is.

- [ ] **Step 5: Save only the runner's fields**

In `adit/core/tasks.py`, in the `finally:` of `_run_dicom_task`, replace `dicom_task.save()` with:

```python
        # Only the fields this runner owns: the processor ran in a child process and may
        # have saved fields of its own, which this older copy would overwrite.
        dicom_task.save(update_fields=["status", "message", "log", "end"])
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `uv run cli test -- adit/core/ adit/router/ -m "not acceptance"`
Expected: PASS. That includes the existing receiver, router SCP and task tests.

- [ ] **Step 7: Commit**

```bash
git add adit/core/utils/presentation_contexts.py adit/core/utils/dimse_connector.py \
  adit/core/utils/dicom_operator.py adit/core/tasks.py adit/core/tests/utils/test_presentation_contexts.py \
  adit/core/tests/utils/test_dimse_connector.py adit/core/tests/test_tasks.py
git commit -m "Let C-STORE request the stored contexts and processors save task fields"
```

---

### Task 5: Router deliveries

**Files:**
- Create: `adit/router/processors.py`
- Create: `adit/router/tasks.py`
- Modify: `adit/router/models.py` (`RouterJob.queue_pending_tasks`, `RouterTask.queue_pending_task`)
- Modify: `adit/router/apps.py` (register the processor)
- Test: `adit/router/tests/test_processors.py` (new)

**Interfaces:**
- Consumes:
  - `requested_store_contexts` and `DicomOperator(store_contexts=...)` (Task 4).
  - `spool.batch_dir` and `batches.read_series_images` (Task 3).
  - `RouterTask.already_sent` (Task 2).
  - `DicomManipulator`, `Pseudonymizer`, `read_dataset` and `write_dataset` (core).
  - `DICOM_TASK_RETRY_STRATEGY`, `_run_dicom_task` (`adit/core/tasks.py`).
  - `register_dicom_processor` (`adit/core/site.py`).
- Produces:
  - `RouterTaskProcessor`.
  - The Procrastinate task `adit.router.tasks.process_router_task` (queue `dicom`).
  - `RouterTask.queue_pending_task()` and `RouterJob.queue_pending_tasks()`, which queue on it.

- [ ] **Step 1: Write the failing tests**

Create `adit/router/tests/test_processors.py`:

```python
from pathlib import Path

import pytest
from django.conf import settings
from django.utils import timezone
from procrastinate.contrib.django.models import ProcrastinateJob
from pydicom import Dataset
from pydicom.data import get_testdata_file
from pydicom.uid import JPEGLSLossless, MRImageStorage
from pytest_mock import MockerFixture

from adit.core.errors import DicomError
from adit.core.models import DicomTask
from adit.core.utils.dicom_utils import read_dataset, write_dataset
from adit.core.utils.pseudonymizer import deterministic_pseudonym
from adit.core.utils.recovery import dicom_task_models
from adit.core.utils.testing_helpers import load_sample_dicoms
from adit.router.factories import (
    RouterBatchFactory,
    RouterJobFactory,
    RouterTaskFactory,
    RoutingRuleFactory,
)
from adit.router.models import RouterTask, RoutingRule
from adit.router.processors import RouterTaskProcessor
from adit.router.utils import spool


@pytest.fixture
def spool_root(tmp_path: Path, settings) -> Path:
    settings.ROUTER_SPOOL_PATH = str(tmp_path)
    spool.ensure_spool_dirs(tmp_path)
    return tmp_path


class _Uploads:
    """Stands in for DicomOperator and keeps what upload_images would have sent."""

    def __init__(self, mocker: MockerFixture):
        self.datasets: list[Dataset] = []
        self.store_contexts = None

        def make_operator(server, store_contexts=None, **kwargs):
            self.store_contexts = store_contexts
            operator = mocker.MagicMock()
            operator.upload_images.side_effect = lambda folder: self.datasets.extend(
                read_dataset(path) for path in sorted(Path(folder).iterdir())
            )
            return operator

        mocker.patch("adit.router.processors.DicomOperator", side_effect=make_operator)


def _ct_images() -> list[Dataset]:
    return [ds for ds in load_sample_dicoms("1004") if ds.Modality == "CT"]


def _task(spool_root: Path, datasets: list[Dataset], rule: RoutingRule) -> RouterTask:
    batch = RouterBatchFactory.create(study_instance_uid=str(datasets[0].StudyInstanceUID))
    path = spool.batch_dir(spool_root, batch.sender_id, batch.batch_id)
    path.mkdir(parents=True)
    for ds in datasets:
        write_dataset(ds, path / f"{ds.SOPInstanceUID}.dcm")
    job = RouterJobFactory.create(
        rule=rule,
        batch=batch,
        trial_protocol_id=rule.trial_protocol_id,
        trial_protocol_name="",
    )
    patient_id = str(datasets[0].PatientID)
    return RouterTaskFactory.create(
        job=job,
        source=batch.sender.server,
        destination=rule.destination,
        patient_id=patient_id,
        study_uid=str(datasets[0].StudyInstanceUID),
        series_uids=sorted({str(ds.SeriesInstanceUID) for ds in datasets}),
        pseudonym=deterministic_pseudonym(rule.pseudonym_salt, patient_id)
        if rule.pseudonymize
        else "",
    )


@pytest.mark.django_db
def test_delivery_sends_the_series_pseudonymized_with_the_xnat_project(spool_root, mocker):
    uploads = _Uploads(mocker)
    images = _ct_images()
    task = _task(spool_root, images, RoutingRuleFactory.create(trial_protocol_id="XNATPROJ"))

    result = RouterTaskProcessor(task).process()

    assert result["status"] == DicomTask.Status.SUCCESS
    assert result["message"] == f"Sent {len(images)} images to {task.destination.name}."
    assert len(uploads.datasets) == len(images)
    sent = uploads.datasets[0]
    assert sent.PatientID == task.pseudonym
    assert sent.PatientComments.startswith(f"Project:XNATPROJ Subject:{task.pseudonym} ")
    task.refresh_from_db()
    assert sorted(task.sent_instance_uids) == sorted(str(ds.SOPInstanceUID) for ds in images)


@pytest.mark.django_db
def test_late_batch_gets_the_same_pseudonym_and_uids(spool_root, mocker):
    uploads = _Uploads(mocker)
    images = _ct_images()
    rule = RoutingRuleFactory.create()
    first = _task(spool_root, images[:5], rule)
    late = _task(spool_root, images[5:], rule)

    RouterTaskProcessor(first).process()
    first_sent = list(uploads.datasets)
    uploads.datasets.clear()
    RouterTaskProcessor(late).process()

    assert {ds.PatientID for ds in first_sent + uploads.datasets} == {first.pseudonym}
    assert {ds.StudyInstanceUID for ds in first_sent} == {
        ds.StudyInstanceUID for ds in uploads.datasets
    }
    assert first_sent[0].StudyInstanceUID != images[0].StudyInstanceUID


@pytest.mark.django_db
def test_images_sent_before_are_left_out(spool_root, mocker):
    uploads = _Uploads(mocker)
    images = _ct_images()
    rule = RoutingRuleFactory.create()
    earlier = _task(spool_root, images, rule)
    RouterTask.objects.filter(pk=earlier.pk).update(
        status=DicomTask.Status.SUCCESS,
        sent_instance_uids=[str(ds.SOPInstanceUID) for ds in images[:4]],
    )

    RouterTaskProcessor(_task(spool_root, images, rule)).process()

    assert len(uploads.datasets) == len(images) - 4


@pytest.mark.django_db
def test_nothing_is_sent_when_every_image_was_sent_before(spool_root, mocker):
    uploads = _Uploads(mocker)
    images = _ct_images()
    rule = RoutingRuleFactory.create()
    earlier = _task(spool_root, images, rule)
    RouterTask.objects.filter(pk=earlier.pk).update(
        status=DicomTask.Status.SUCCESS,
        sent_instance_uids=[str(ds.SOPInstanceUID) for ds in images],
    )

    result = RouterTaskProcessor(_task(spool_root, images, rule)).process()

    assert result["status"] == DicomTask.Status.SUCCESS
    assert result["message"] == "Nothing new to send."
    assert uploads.datasets == []


@pytest.mark.django_db
def test_delivery_of_a_deleted_batch_fails_clearly(spool_root, mocker):
    _Uploads(mocker)
    task = _task(spool_root, _ct_images()[:1], RoutingRuleFactory.create())
    batch = task.job.batch
    batch.files_deleted_at = timezone.now()
    batch.save()

    with pytest.raises(DicomError, match="forward the study again"):
        RouterTaskProcessor(task).process()


@pytest.mark.django_db
def test_delivery_of_a_missing_batch_folder_fails_clearly(spool_root, mocker):
    _Uploads(mocker)
    task = _task(spool_root, _ct_images()[:1], RoutingRuleFactory.create())
    batch = task.job.batch
    spool.delete_batch(spool.batch_dir(spool_root, batch.sender_id, batch.batch_id))

    with pytest.raises(DicomError, match="forward the study again"):
        RouterTaskProcessor(task).process()


@pytest.mark.django_db
def test_delivery_requests_the_stored_transfer_syntax(spool_root, mocker):
    uploads = _Uploads(mocker)
    path = get_testdata_file("MR_small_jpeg_ls_lossless.dcm")
    assert path is not None
    task = _task(spool_root, [read_dataset(path)], RoutingRuleFactory.create(pseudonymize=False))

    RouterTaskProcessor(task).process()

    assert uploads.store_contexts is not None
    assert [
        (str(cx.abstract_syntax), [str(ts) for ts in cx.transfer_syntax])
        for cx in uploads.store_contexts
    ] == [(MRImageStorage, [JPEGLSLossless])]
    assert uploads.datasets[0].file_meta.TransferSyntaxUID == JPEGLSLossless


@pytest.mark.django_db
def test_router_tasks_queue_on_the_dicom_queue():
    task = RouterTaskFactory.create()

    task.queue_pending_task()

    row = ProcrastinateJob.objects.get(pk=task.queued_job_id)
    assert row.task_name == "adit.router.tasks.process_router_task"
    assert row.queue_name == "dicom"
    assert row.priority == settings.ROUTER_DEFAULT_PRIORITY


@pytest.mark.django_db
def test_router_job_queues_its_pending_tasks():
    task = RouterTaskFactory.create()

    task.job.queue_pending_tasks()

    task.refresh_from_db()
    assert task.queued_job is not None


def test_stale_task_sweep_covers_router_tasks():
    assert RouterTask in dicom_task_models()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run cli test -- adit/router/tests/test_processors.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'adit.router.processors'`.

- [ ] **Step 3: Queue router tasks on their own Procrastinate task**

In `adit/router/models.py`:
- Add the imports `from procrastinate.contrib.django import app`, `from adit.core.models import DicomJob` (merge it into the existing `adit.core.models` import) and `from adit.core.utils.model_utils import get_model_label`.
- Add to `RouterJob`:

```python
    def queue_pending_tasks(self) -> None:
        assert self.status == DicomJob.Status.PENDING
        for task in self.tasks.filter(status=DicomTask.Status.PENDING):
            task.queue_pending_task()
```

- Add to `RouterTask`:

```python
    def queue_pending_task(self) -> None:
        assert self.status == DicomTask.Status.PENDING
        assert self.queued_job is None

        priority = self.job.urgent_priority if self.job.urgent else self.job.default_priority
        queued_job_id = app.configure_task(
            "adit.router.tasks.process_router_task", allow_unknown=False, priority=priority
        ).defer(model_label=get_model_label(self.__class__), task_id=self.pk)
        self.queued_job_id = queued_job_id
        self.save()
```

- [ ] **Step 4: Add the Procrastinate task**

Create `adit/router/tasks.py`:

```python
import logging

from django.conf import settings
from procrastinate import JobContext
from procrastinate.contrib.django import app

from adit.core.tasks import DICOM_TASK_RETRY_STRATEGY, _run_dicom_task

logger = logging.getLogger(__name__)


@app.task(queue="dicom", pass_context=True, retry=DICOM_TASK_RETRY_STRATEGY)
def process_router_task(context: JobContext, model_label: str, task_id: int):
    _run_dicom_task(context, model_label, task_id, process_timeout=settings.ROUTER_PROCESS_TIMEOUT)
```

- [ ] **Step 5: Implement the processor**

Create `adit/router/processors.py`:

```python
"""Delivers the series a routing rule selected from a router batch."""

import tempfile
from pathlib import Path

from django.conf import settings

from adit.core.errors import DicomError
from adit.core.models import DicomNode, DicomTask
from adit.core.processors import DicomTaskProcessor
from adit.core.types import ProcessingResult
from adit.core.utils.dicom_manipulator import DicomManipulator
from adit.core.utils.dicom_operator import DicomOperator
from adit.core.utils.dicom_utils import read_dataset, write_dataset
from adit.core.utils.presentation_contexts import requested_store_contexts
from adit.core.utils.pseudonymizer import Pseudonymizer

from .models import RouterSettings, RouterTask
from .utils import spool
from .utils.batches import read_series_images

_FORWARD_AGAIN = "The PACS has to forward the study again."


class RouterTaskProcessor(DicomTaskProcessor):
    app_name = "router"
    dicom_task_class = RouterTask
    app_settings_class = RouterSettings

    def __init__(self, dicom_task: DicomTask) -> None:
        assert isinstance(dicom_task, RouterTask)
        super().__init__(dicom_task)
        self.router_task = dicom_task

    def process(self) -> ProcessingResult:
        task = self.router_task
        job = task.job
        batch = job.batch
        if batch.files_deleted_at:
            raise DicomError(f"The images were deleted from the router spool. {_FORWARD_AGAIN}")

        batch_path = spool.batch_dir(
            Path(settings.ROUTER_SPOOL_PATH), batch.sender_id, batch.batch_id
        )
        if not batch_path.is_dir():
            raise DicomError(f"The batch folder {batch_path} is missing. {_FORWARD_AGAIN}")

        already_sent = RouterTask.already_sent(job.rule_id, task.study_uid, task.destination_id)
        images = [
            image
            for image in read_series_images(batch_path, set(task.series_uids))
            if image.sop_instance_uid not in already_sent
        ]
        if not images:
            return {"status": RouterTask.Status.SUCCESS, "message": "Nothing new to send.", "log": ""}

        destination = task.destination
        assert destination.node_type == DicomNode.NodeType.SERVER
        if task.pseudonym:
            manipulator = DicomManipulator(Pseudonymizer(seed=job.rule.pseudonym_salt))
        else:
            manipulator = DicomManipulator()

        with tempfile.TemporaryDirectory(prefix="adit_router_") as tmpdir:
            pairs: set[tuple[str, str]] = set()
            for image in images:
                ds = read_dataset(image.path)
                manipulator.manipulate(
                    ds,
                    pseudonym=task.pseudonym or None,
                    trial_protocol_id=job.trial_protocol_id or None,
                    trial_protocol_name=job.trial_protocol_name or None,
                )
                pairs.add((str(ds.SOPClassUID), str(ds.file_meta.TransferSyntaxUID)))
                write_dataset(ds, Path(tmpdir) / f"{image.sop_instance_uid}.dcm")

            operator = DicomOperator(
                destination.dicomserver, store_contexts=requested_store_contexts(pairs)
            )
            operator.upload_images(tmpdir)

        sent = sorted(image.sop_instance_uid for image in images)
        # The runner saves only the fields it owns, so this survives the end of the task.
        RouterTask.objects.filter(pk=task.pk).update(sent_instance_uids=sent)
        return {
            "status": RouterTask.Status.SUCCESS,
            "message": f"Sent {len(sent)} images to {destination.name}.",
            "log": "",
        }
```

- [ ] **Step 6: Register the processor**

Replace `adit/router/apps.py` with:

```python
from django.apps import AppConfig
from django.db.models.signals import post_migrate

from adit.core.utils.model_utils import get_model_label


class RouterConfig(AppConfig):
    name = "adit.router"

    def ready(self):
        register_app()

        # Put calls to db stuff in this signal handler
        post_migrate.connect(init_db, sender=self)


def register_app():
    from adit.core.site import register_dicom_processor

    from .models import RouterTask
    from .processors import RouterTaskProcessor

    register_dicom_processor(get_model_label(RouterTask), RouterTaskProcessor)


def init_db(**kwargs):
    from .models import RouterSettings

    if not RouterSettings.objects.exists():
        RouterSettings.objects.create()
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `uv run cli test -- adit/router/ adit/core/tests/test_tasks.py -m "not acceptance"`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add adit/router/processors.py adit/router/tasks.py adit/router/models.py adit/router/apps.py \
  adit/router/tests/test_processors.py
git commit -m "Deliver router tasks to the destination of their rule"
```

---

### Task 6: Deciding batches

**Files:**
- Create: `adit/router/utils/routing.py`
- Test: `adit/router/tests/test_routing.py` (new)

**Interfaces:**
- Consumes:
  - `select_study_series` (Task 1).
  - `RoutingRule.get_filters`, `RouterTask.already_sent`, `RouterBatch` and `RouterJob` (Task 2).
  - `spool.BatchDir`, `spool.delete_batch` and `batches.read_batch` / `BatchContents` (Task 3).
  - `RouterJob.queue_pending_tasks` (Task 5).
  - `deterministic_pseudonym` (core).
- Produces: `decide_batch(spool_root: Path, batch: spool.BatchDir, today: date) -> list[RouterJob]`.

- [ ] **Step 1: Write the failing tests**

Create `adit/router/tests/test_routing.py`:

```python
import uuid
from datetime import date
from pathlib import Path

import pytest
from pydicom import Dataset

from adit.core.models import DicomTask
from adit.core.utils.dicom_utils import write_dataset
from adit.core.utils.pseudonymizer import deterministic_pseudonym
from adit.core.utils.testing_helpers import load_sample_dicoms
from adit.router.factories import (
    RouterJobFactory,
    RouterSenderFactory,
    RouterTaskFactory,
    RoutingRuleFactory,
)
from adit.router.models import RouterBatch, RouterJob, RouterSender, RouterTask
from adit.router.utils import spool
from adit.router.utils.routing import decide_batch

TODAY = date(2026, 10, 4)


@pytest.fixture
def spool_root(tmp_path: Path) -> Path:
    spool.ensure_spool_dirs(tmp_path)
    return tmp_path


def _closed_batch(spool_root: Path, sender: RouterSender, datasets: list[Dataset]) -> spool.BatchDir:
    batch_id = uuid.uuid4()
    path = spool.batch_dir(spool_root, sender.pk, batch_id)
    path.mkdir(parents=True)
    for ds in datasets:
        write_dataset(ds, path / f"{ds.SOPInstanceUID}.dcm")
    return spool.BatchDir(sender.pk, batch_id, path)


def _study() -> list[Dataset]:
    return list(load_sample_dicoms("1001"))  # CT x10 and one SR


@pytest.mark.django_db
def test_matching_rule_creates_a_queued_delivery(spool_root):
    sender = RouterSenderFactory.create()
    rule = RoutingRuleFactory.create(trial_protocol_id="XNATPROJ")  # CT only
    datasets = _study()
    batch = _closed_batch(spool_root, sender, datasets)

    [job] = decide_batch(spool_root, batch, TODAY)

    assert job.rule == rule
    assert job.owner == rule.created_by
    assert job.status == RouterJob.Status.PENDING
    assert job.trial_protocol_id == "XNATPROJ"
    task = job.tasks.get()
    assert set(task.series_uids) == {
        str(ds.SeriesInstanceUID) for ds in datasets if ds.Modality == "CT"
    }
    assert task.pseudonym == deterministic_pseudonym(rule.pseudonym_salt, "1001")
    assert task.source_id == sender.server.pk
    assert task.destination_id == rule.destination.pk
    assert task.queued_job is not None
    assert task.queued_job.task_name == "adit.router.tasks.process_router_task"
    assert RouterBatch.objects.get(batch_id=batch.batch_id).number_of_images == len(datasets)
    assert batch.path.is_dir()


@pytest.mark.django_db
def test_batch_no_rule_matches_is_deleted(spool_root):
    RoutingRuleFactory.create(filters_json=[{"modality": "MR"}])
    batch = _closed_batch(spool_root, RouterSenderFactory.create(), _study())

    assert decide_batch(spool_root, batch, TODAY) == []
    assert not batch.path.exists()
    assert not RouterBatch.objects.exists()


@pytest.mark.django_db
def test_disabled_rules_are_ignored(spool_root):
    RoutingRuleFactory.create(enabled=False)
    batch = _closed_batch(spool_root, RouterSenderFactory.create(), _study())

    assert decide_batch(spool_root, batch, TODAY) == []
    assert not batch.path.exists()


@pytest.mark.django_db
def test_images_sent_before_are_not_routed_again(spool_root):
    rule = RoutingRuleFactory.create()
    datasets = _study()
    RouterTaskFactory.create(
        job=RouterJobFactory.create(rule=rule),
        destination=rule.destination,
        study_uid=str(datasets[0].StudyInstanceUID),
        status=DicomTask.Status.SUCCESS,
        sent_instance_uids=[str(ds.SOPInstanceUID) for ds in datasets if ds.Modality == "CT"],
    )
    batch = _closed_batch(spool_root, RouterSenderFactory.create(), datasets)

    assert decide_batch(spool_root, batch, TODAY) == []
    assert not batch.path.exists()


@pytest.mark.django_db
def test_a_batch_is_decided_only_once(spool_root):
    RoutingRuleFactory.create()
    batch = _closed_batch(spool_root, RouterSenderFactory.create(), _study())
    decide_batch(spool_root, batch, TODAY)

    assert decide_batch(spool_root, batch, TODAY) == []
    assert RouterJob.objects.count() == 1


@pytest.mark.django_db
def test_batch_of_a_removed_sender_is_deleted(spool_root):
    RoutingRuleFactory.create()
    sender = RouterSenderFactory.create()
    batch = _closed_batch(spool_root, sender, _study())
    sender.delete()

    assert decide_batch(spool_root, batch, TODAY) == []
    assert not batch.path.exists()


@pytest.mark.django_db
def test_study_without_patient_id_gets_a_pseudonym_from_its_study_uid(spool_root):
    rule = RoutingRuleFactory.create()
    datasets = _study()
    for ds in datasets:
        ds.PatientID = ""
    batch = _closed_batch(spool_root, RouterSenderFactory.create(), datasets)

    [job] = decide_batch(spool_root, batch, TODAY)

    expected = deterministic_pseudonym(rule.pseudonym_salt, str(datasets[0].StudyInstanceUID))
    assert job.tasks.get().pseudonym == expected


@pytest.mark.django_db
def test_rule_without_pseudonymization_sends_the_patient_as_is(spool_root):
    RoutingRuleFactory.create(pseudonymize=False)
    batch = _closed_batch(spool_root, RouterSenderFactory.create(), _study())

    [job] = decide_batch(spool_root, batch, TODAY)

    assert job.tasks.get().pseudonym == ""


@pytest.mark.django_db
def test_each_matching_rule_gets_its_own_delivery(spool_root):
    RoutingRuleFactory.create()
    RoutingRuleFactory.create(filters_json=[{"modality": "SR"}])
    batch = _closed_batch(spool_root, RouterSenderFactory.create(), _study())

    jobs = decide_batch(spool_root, batch, TODAY)

    assert len(jobs) == 2
    assert RouterTask.objects.count() == 2
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run cli test -- adit/router/tests/test_routing.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'adit.router.utils.routing'`.

- [ ] **Step 3: Implement deciding**

Create `adit/router/utils/routing.py`:

```python
"""Decides which routing rules a closed batch matches and creates their deliveries."""

import logging
from datetime import date
from pathlib import Path

from django.db import IntegrityError, transaction

from adit.core.utils.pseudonymizer import deterministic_pseudonym
from adit.core.utils.series_filters import select_study_series

from ..models import RouterBatch, RouterJob, RouterSender, RouterTask, RoutingRule
from . import spool
from .batches import BatchContents, read_batch

logger = logging.getLogger(__name__)


def decide_batch(spool_root: Path, batch: spool.BatchDir, today: date) -> list[RouterJob]:
    """Decide a closed batch and return the router jobs created for it.

    A batch that matches no enabled rule, or whose images were all sent before, is
    deleted. A batch that was decided before is left alone, and the unique constraints
    keep a concurrent second decision from creating anything.
    """
    if RouterBatch.objects.filter(batch_id=batch.batch_id).exists():
        return []

    sender = RouterSender.objects.select_related("server").filter(pk=batch.sender_id).first()
    if sender is None:
        logger.warning(
            "Deleting router batch %s: its sender %d no longer exists.",
            batch.batch_id,
            batch.sender_id,
        )
        spool.delete_batch(batch.path)
        return []

    contents = read_batch(spool_root, batch.path, today)
    if not contents.images:
        logger.warning("Deleting router batch %s: none of its files could be read.", batch.batch_id)
        spool.delete_batch(batch.path)
        return []

    matches = _match_rules(contents)
    if not matches:
        logger.info(
            "Deleting router batch %s of %s (study %s, %d images): no routing rule matches.",
            batch.batch_id,
            sender.calling_ae_title,
            contents.study_instance_uid,
            len(contents.images),
        )
        spool.delete_batch(batch.path)
        return []

    try:
        with transaction.atomic():
            router_batch = RouterBatch.objects.create(
                batch_id=batch.batch_id,
                sender=sender,
                study_instance_uid=contents.study_instance_uid,
                number_of_images=len(contents.images),
            )
            return [
                _create_job(router_batch, sender, contents, rule, series_uids)
                for rule, series_uids in matches
            ]
    except IntegrityError:
        logger.warning("Router batch %s was decided by another run; skipping it.", batch.batch_id)
        return []


def _match_rules(contents: BatchContents) -> list[tuple[RoutingRule, list[str]]]:
    """The enabled rules with images left to send, each with the series to send."""
    matches: list[tuple[RoutingRule, list[str]]] = []
    rules = RoutingRule.objects.filter(enabled=True).select_related("destination", "created_by")
    for rule in rules.order_by("pk"):
        selected = {
            s.series_instance_uid
            for s in select_study_series(contents.study, contents.series, rule.get_filters())
        }
        already_sent = RouterTask.already_sent(
            rule.pk, contents.study_instance_uid, rule.destination_id
        )
        series_left = sorted(
            {
                image.series_instance_uid
                for image in contents.images
                if image.series_instance_uid in selected
                and image.sop_instance_uid not in already_sent
            }
        )
        if series_left:
            matches.append((rule, series_left))
    return matches


def _create_job(
    router_batch: RouterBatch,
    sender: RouterSender,
    contents: BatchContents,
    rule: RoutingRule,
    series_uids: list[str],
) -> RouterJob:
    job = RouterJob.objects.create(
        rule=rule,
        batch=router_batch,
        owner=rule.created_by,
        status=RouterJob.Status.PENDING,
        send_finished_mail=False,
        trial_protocol_id=rule.trial_protocol_id,
        trial_protocol_name=rule.trial_protocol_name,
    )
    RouterTask.objects.create(
        job=job,
        source=sender.server,
        destination=rule.destination,
        patient_id=contents.patient_id,
        study_uid=contents.study_instance_uid,
        series_uids=series_uids,
        pseudonym=_pseudonym(rule, contents),
    )
    # Queued inside the transaction, so the queue rows appear only with the batch.
    job.queue_pending_tasks()
    return job


def _pseudonym(rule: RoutingRule, contents: BatchContents) -> str:
    if not rule.pseudonymize:
        return ""
    # Without a Patient ID the study UID keys the pseudonym: unrelated patients don't
    # share one, and the late batches of the study still get the same.
    key = contents.patient_id or contents.study_instance_uid
    return deterministic_pseudonym(rule.pseudonym_salt, key)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run cli test -- adit/router/tests/test_routing.py`
Expected: PASS (9 tests).

- [ ] **Step 5: Commit**

```bash
git add adit/router/utils/routing.py adit/router/tests/test_routing.py
git commit -m "Decide closed router batches against the routing rules"
```

---

### Task 7: The periodic closing task, clean-up and failure reports

**Files:**
- Create: `adit/router/utils/closer.py`
- Modify: `adit/router/tasks.py` (two periodic tasks)
- Test: `adit/router/tests/test_closer.py` (new), `adit/router/tests/test_tasks.py` (new)

**Interfaces:**
- Consumes:
  - `spool.close_due_studies`, `list_batches`, `batch_dir`, `delete_batch`, `clean_quarantine`, `clean_old_tmp`, `free_bytes` and `ensure_spool_dirs` (Tasks 3 and stage 2).
  - `decide_batch` (Task 6).
  - `RouterBatch`, `RouterJob`, `RouterTask` and `RouterSettings.low_space_mailed_at` (Task 2).
  - `send_mail_to_admins` (`adit/core/utils/mail.py`).
- Produces:
  - `run_spool_cycle(spool_root: Path, now: datetime) -> None`
  - `delete_finished_batches(spool_root: Path, now: datetime) -> int`
  - `mail_if_low_on_space(spool_root: Path, now: datetime) -> bool`
  - `report_failed_deliveries(now: datetime) -> int`
  - `clear_old_sent_lists(now: datetime) -> int`
  - The periodic tasks `close_router_batches` (`ROUTER_CLOSE_CRON`, default queue, `queueing_lock` plus `lock`) and `report_router_failures` (daily at 07:00).

- [ ] **Step 1: Write the failing tests**

Create `adit/router/tests/test_closer.py`:

```python
import os
from datetime import timedelta
from pathlib import Path

import pytest
from django.utils import timezone

from adit.core.models import DicomJob, DicomTask
from adit.core.utils.testing_helpers import load_sample_dicoms
from adit.router.factories import (
    RouterBatchFactory,
    RouterJobFactory,
    RouterSenderFactory,
    RouterTaskFactory,
    RoutingRuleFactory,
)
from adit.router.models import RouterBatch, RouterJob, RouterSettings, RouterTask
from adit.router.utils import closer, spool


@pytest.fixture
def spool_root(tmp_path: Path) -> Path:
    spool.ensure_spool_dirs(tmp_path)
    return tmp_path


def _batch_with_jobs(spool_root: Path, *statuses: str, days_ago: int = 0) -> RouterBatch:
    batch = RouterBatchFactory.create()
    for status in statuses:
        RouterJobFactory.create(batch=batch, status=status)
    RouterBatch.objects.filter(pk=batch.pk).update(
        closed_at=timezone.now() - timedelta(days=days_ago)
    )
    batch.refresh_from_db()
    spool.batch_dir(spool_root, batch.sender_id, batch.batch_id).mkdir(parents=True)
    return batch


@pytest.mark.django_db
def test_cycle_closes_quiet_studies_and_decides_them(spool_root):
    sender = RouterSenderFactory.create()
    RoutingRuleFactory.create()  # CT
    for ds in load_sample_dicoms("1004"):
        spool.store_dataset(spool_root, sender.pk, ds)

    closer.run_spool_cycle(spool_root, timezone.now() + timedelta(hours=2))

    assert RouterJob.objects.count() == 1
    assert list((spool_root / spool.INCOMING / str(sender.pk)).iterdir()) == []


@pytest.mark.django_db
def test_cycle_leaves_recent_studies_open(spool_root):
    sender = RouterSenderFactory.create()
    RoutingRuleFactory.create()
    for ds in list(load_sample_dicoms("1004"))[:1]:
        spool.store_dataset(spool_root, sender.pk, ds)

    closer.run_spool_cycle(spool_root, timezone.now())

    assert not RouterJob.objects.exists()


@pytest.mark.django_db
def test_cycle_removes_old_tmp_files(spool_root):
    leftover = spool_root / spool.TMP / "leftover.dcm"
    leftover.write_bytes(b"x")
    two_hours_ago = (timezone.now() - timedelta(hours=2)).timestamp()
    os.utime(leftover, (two_hours_ago, two_hours_ago))

    closer.run_spool_cycle(spool_root, timezone.now())

    assert not leftover.exists()


@pytest.mark.django_db
def test_delivered_batches_are_deleted(spool_root):
    batch = _batch_with_jobs(spool_root, DicomJob.Status.SUCCESS, DicomJob.Status.CANCELED)
    now = timezone.now()

    assert closer.delete_finished_batches(spool_root, now) == 1

    batch.refresh_from_db()
    assert batch.files_deleted_at == now
    assert not spool.batch_dir(spool_root, batch.sender_id, batch.batch_id).exists()


@pytest.mark.django_db
def test_batches_with_running_deliveries_are_kept(spool_root):
    _batch_with_jobs(spool_root, DicomJob.Status.SUCCESS, DicomJob.Status.IN_PROGRESS)

    assert closer.delete_finished_batches(spool_root, timezone.now()) == 0


@pytest.mark.django_db
def test_failed_batches_are_kept_until_their_retention_ends(spool_root, settings):
    settings.ROUTER_FAILED_RETENTION_DAYS = 7
    recent = _batch_with_jobs(spool_root, DicomJob.Status.FAILURE, days_ago=6)
    old = _batch_with_jobs(
        spool_root, DicomJob.Status.FAILURE, DicomJob.Status.SUCCESS, days_ago=8
    )

    assert closer.delete_finished_batches(spool_root, timezone.now()) == 1

    recent.refresh_from_db()
    old.refresh_from_db()
    assert recent.files_deleted_at is None
    assert old.files_deleted_at is not None


@pytest.mark.django_db
def test_low_space_mails_the_admins_at_most_once_per_period(spool_root, mocker, settings):
    settings.ROUTER_LOW_SPACE_MAIL_HOURS = 6
    mocker.patch.object(closer.spool, "free_bytes", return_value=0)
    mail = mocker.patch.object(closer, "send_mail_to_admins")
    now = timezone.now()

    assert closer.mail_if_low_on_space(spool_root, now)
    assert not closer.mail_if_low_on_space(spool_root, now + timedelta(hours=5))
    assert closer.mail_if_low_on_space(spool_root, now + timedelta(hours=7))

    assert mail.call_count == 2
    assert RouterSettings.get().low_space_mailed_at == now + timedelta(hours=7)


@pytest.mark.django_db
def test_enough_space_sends_no_mail(spool_root, mocker):
    mocker.patch.object(closer.spool, "free_bytes", return_value=100 * 1024**3)
    mail = mocker.patch.object(closer, "send_mail_to_admins")

    assert not closer.mail_if_low_on_space(spool_root, timezone.now())

    mail.assert_not_called()


@pytest.mark.django_db
def test_failed_deliveries_of_the_last_day_are_reported(mocker, settings):
    settings.ROUTER_FAILED_RETENTION_DAYS = 7
    mail = mocker.patch.object(closer, "send_mail_to_admins")
    now = timezone.now()
    failed = RouterTaskFactory.create(
        status=DicomTask.Status.FAILURE, message="Could not connect to the destination."
    )
    RouterJob.objects.filter(pk=failed.job.pk).update(
        status=DicomJob.Status.FAILURE, end=now - timedelta(hours=2)
    )
    old = RouterTaskFactory.create(status=DicomTask.Status.FAILURE)
    RouterJob.objects.filter(pk=old.job.pk).update(
        status=DicomJob.Status.FAILURE, end=now - timedelta(days=2)
    )

    assert closer.report_failed_deliveries(now) == 1

    subject, text = mail.call_args.args
    assert subject == "1 DICOM router deliveries failed"
    assert f"Job {failed.job.pk}" in text
    assert failed.job.rule.name in text
    assert "Could not connect to the destination." in text
    assert f"Job {old.job.pk}" not in text


@pytest.mark.django_db
def test_no_failures_send_no_report(mocker):
    mail = mocker.patch.object(closer, "send_mail_to_admins")

    assert closer.report_failed_deliveries(timezone.now()) == 0

    mail.assert_not_called()


@pytest.mark.django_db
def test_old_sent_lists_are_cleared(settings):
    settings.ROUTER_SENT_LIST_RETENTION_DAYS = 30
    now = timezone.now()
    old = RouterTaskFactory.create(sent_instance_uids=["1.1"], end=now - timedelta(days=31))
    recent = RouterTaskFactory.create(sent_instance_uids=["1.2"], end=now - timedelta(days=29))

    assert closer.clear_old_sent_lists(now) == 1

    assert RouterTask.objects.get(pk=old.pk).sent_instance_uids == []
    assert RouterTask.objects.get(pk=recent.pk).sent_instance_uids == ["1.2"]
```

Create `adit/router/tests/test_tasks.py`:

```python
from pathlib import Path

from pytest_mock import MockerFixture

from adit.router import tasks


def test_closing_skips_when_the_spool_is_not_mounted(tmp_path, settings, mocker: MockerFixture):
    missing = tmp_path / "spool"
    settings.ROUTER_SPOOL_PATH = str(missing)
    cycle = mocker.patch.object(tasks, "run_spool_cycle")

    tasks.close_router_batches(timestamp=0)

    cycle.assert_not_called()
    assert not missing.exists()


def test_closing_runs_a_cycle_on_the_mounted_spool(tmp_path, settings, mocker: MockerFixture):
    settings.ROUTER_SPOOL_PATH = str(tmp_path)
    cycle = mocker.patch.object(tasks, "run_spool_cycle")

    tasks.close_router_batches(timestamp=0)

    assert cycle.call_args.args[0] == Path(tmp_path)


def test_failure_report_also_clears_old_sent_lists(mocker: MockerFixture):
    report = mocker.patch.object(tasks, "report_failed_deliveries")
    clear = mocker.patch.object(tasks, "clear_old_sent_lists")

    tasks.report_router_failures(timestamp=0)

    report.assert_called_once()
    clear.assert_called_once()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run cli test -- adit/router/tests/test_closer.py adit/router/tests/test_tasks.py`
Expected: FAIL with `ImportError: cannot import name 'closer'` and missing task attributes.

- [ ] **Step 3: Implement the cycle, clean-up and reports**

Create `adit/router/utils/closer.py`:

```python
"""The periodic work on the router spool: close, decide, clean up and report."""

import logging
from datetime import datetime, timedelta
from pathlib import Path

from django.conf import settings
from django.utils import timezone

from adit.core.utils.mail import send_mail_to_admins

from ..models import RouterBatch, RouterJob, RouterSettings, RouterTask
from . import spool
from .routing import decide_batch

logger = logging.getLogger(__name__)

# Files in tmp/ this old were left by a store that failed while writing.
TMP_MAX_AGE_SECONDS = 3600

_FINISHED = (
    RouterJob.Status.SUCCESS,
    RouterJob.Status.WARNING,
    RouterJob.Status.CANCELED,
    RouterJob.Status.FAILURE,
)


def run_spool_cycle(spool_root: Path, now: datetime) -> None:
    """Close the due studies, decide the new batches and clean up the spool."""
    spool.ensure_spool_dirs(spool_root)
    spool.close_due_studies(
        spool_root,
        now.timestamp(),
        settings.ROUTER_QUIET_PERIOD_SECONDS,
        settings.ROUTER_MAX_OPEN_SECONDS,
    )

    today = timezone.localdate(now)
    for batch in spool.list_batches(spool_root):
        try:
            decide_batch(spool_root, batch, today)
        except Exception:
            # One broken batch must not hold up the others; the next run tries it again.
            logger.exception("Could not decide router batch %s.", batch.path)

    delete_finished_batches(spool_root, now)
    spool.clean_quarantine(spool_root, today, settings.ROUTER_QUARANTINE_RETENTION_DAYS)
    spool.clean_old_tmp(spool_root, now.timestamp(), TMP_MAX_AGE_SECONDS)
    mail_if_low_on_space(spool_root, now)


def delete_finished_batches(spool_root: Path, now: datetime) -> int:
    """Delete the folders of batches whose deliveries have all finished.

    A batch with a failed delivery keeps its images for ROUTER_FAILED_RETENTION_DAYS, so
    the delivery can still be retried. Returns how many folders were deleted.
    """
    failed_cutoff = now - timedelta(days=settings.ROUTER_FAILED_RETENTION_DAYS)
    deleted = 0
    batches = RouterBatch.objects.filter(files_deleted_at__isnull=True).prefetch_related("jobs")
    for batch in batches:
        statuses = [job.status for job in batch.jobs.all()]
        if not statuses or any(status not in _FINISHED for status in statuses):
            continue
        if RouterJob.Status.FAILURE in statuses and batch.closed_at > failed_cutoff:
            continue
        spool.delete_batch(spool.batch_dir(spool_root, batch.sender_id, batch.batch_id))
        batch.files_deleted_at = now
        batch.save(update_fields=["files_deleted_at"])
        deleted += 1
    return deleted


def mail_if_low_on_space(spool_root: Path, now: datetime) -> bool:
    """Mail the admins when the spool is low on space, at most once per period."""
    free = spool.free_bytes(spool_root)
    min_free_gb = settings.ROUTER_SPOOL_MIN_FREE_GB
    if free >= min_free_gb * 1024**3:
        return False

    router_settings, _ = RouterSettings.objects.get_or_create()
    last = router_settings.low_space_mailed_at
    if last is not None and now - last < timedelta(hours=settings.ROUTER_LOW_SPACE_MAIL_HOURS):
        return False

    send_mail_to_admins(
        "DICOM router spool low on space",
        f"The DICOM router spool has {free / 1024**3:.1f} GB free, less than "
        f"ROUTER_SPOOL_MIN_FREE_GB ({min_free_gb} GB). The router refuses new images "
        "until space is freed.",
    )
    router_settings.low_space_mailed_at = now
    router_settings.save(update_fields=["low_space_mailed_at"])
    return True


def report_failed_deliveries(now: datetime) -> int:
    """Mail the admins the router deliveries that failed in the last 24 hours."""
    jobs = list(
        RouterJob.objects.filter(status=RouterJob.Status.FAILURE, end__gte=now - timedelta(days=1))
        .select_related("rule", "batch")
        .prefetch_related("tasks")
        .order_by("end")
    )
    if not jobs:
        return 0

    retention = timedelta(days=settings.ROUTER_FAILED_RETENTION_DAYS)
    lines: list[str] = []
    for job in jobs:
        task = next(iter(job.tasks.all()), None)
        reason = task.message if task else job.message
        kept_until = timezone.localdate(job.batch.closed_at + retention)
        lines.append(
            f'- Job {job.pk} of rule "{job.rule.name}", study '
            f"{job.batch.study_instance_uid}: {reason} "
            f"The images stay in the spool until {kept_until}."
        )
    send_mail_to_admins(
        f"{len(jobs)} DICOM router deliveries failed",
        "The DICOM router could not deliver these studies in the last 24 hours:\n\n"
        + "\n".join(lines),
    )
    return len(jobs)


def clear_old_sent_lists(now: datetime) -> int:
    """Forget the images sent by deliveries older than ROUTER_SENT_LIST_RETENTION_DAYS."""
    cutoff = now - timedelta(days=settings.ROUTER_SENT_LIST_RETENTION_DAYS)
    return (
        RouterTask.objects.filter(end__lt=cutoff)
        .exclude(sent_instance_uids=[])
        .update(sent_instance_uids=[])
    )
```

- [ ] **Step 4: Add the periodic tasks**

In `adit/router/tasks.py`:
- Add the imports `from pathlib import Path`, `from django.utils import timezone` and `from .utils.closer import clear_old_sent_lists, report_failed_deliveries, run_spool_cycle`.
- Append:

```python
@app.periodic(cron=settings.ROUTER_CLOSE_CRON)
@app.task(queue="default", queueing_lock="close_router_batches", lock="close_router_batches")
def close_router_batches(timestamp: int) -> None:
    spool_root = Path(settings.ROUTER_SPOOL_PATH)
    # Workers without the spool mounted, like the web container's test workers, skip.
    if not spool_root.is_dir():
        logger.warning("The router spool %s is not mounted here; skipping.", spool_root)
        return
    run_spool_cycle(spool_root, timezone.now())


@app.periodic(cron="0 7 * * *")  # every day at 7am
@app.task(queue="default", queueing_lock="report_router_failures")
def report_router_failures(timestamp: int) -> None:
    now = timezone.now()
    report_failed_deliveries(now)
    clear_old_sent_lists(now)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run cli test -- adit/router/ -m "not acceptance"`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add adit/router/utils/closer.py adit/router/tasks.py adit/router/tests/test_closer.py \
  adit/router/tests/test_tasks.py
git commit -m "Close, decide and clean up router batches periodically"
```

---

### Task 8: Worker spool mounts, docs, example rule and the end-to-end test

**Files:**
- Modify: `docker-compose.base.yml` (`default_worker`, `dicom_worker`)
- Modify: `example.env` (the router block)
- Modify: `adit/core/utils/orthanc_utils.py` (modality helpers)
- Modify: `adit/core/management/commands/populate_example_data.py`
- Modify: `AGENTS.md`, which `CLAUDE.md` is a symlink to
- Modify: `docs/dev-docs/architecture.md`, `docs/user-docs/admin-guide.md`
- Modify: `docs/superpowers/specs/2026-09-30-dicom-router-design.md` (status line)
- Create: `adit/router/tests/acceptance/__init__.py`, `adit/router/tests/acceptance/conftest.py`, `adit/router/tests/acceptance/test_router.py`

**Interfaces:**
- Consumes: `run_spool_cycle` (Task 7), `RouterStoreHandler`, `build_router_scp` and `load_intake_config` (stage 2), `setup_dimse_orthancs`, `free_port`, `wait_until_scp_accepts` and `wait_until_scp_idle` (`adit/core/utils/testing_helpers.py`), and `run_worker_once` (adit-radis-shared).
- Produces:
  - `OrthancRestHandler.add_modality(name, ae_title, host, port)`
  - `OrthancRestHandler.remove_modality(name)`
  - `OrthancRestHandler.send_to_modality(name, resource_ids)`
  - `OrthancRestHandler.instance_tags(instance_id) -> dict`

- [ ] **Step 1: Mount the spool on the workers that close and deliver**

In `docker-compose.base.yml`, give `default_worker` and `dicom_worker` this `volumes:` key. The key replaces the anchor's list, so `/backups` and `/mnt` are listed again:

```yaml
  default_worker:
    <<: *default-app
    hostname: default_worker.local
    volumes:
      - ${BACKUP_DIR:?}:/backups
      - ${MOUNT_DIR:?}:/mnt
      - ${ROUTER_SPOOL_DIR:-router_spool}:/spool

  dicom_worker:
    <<: *default-app
    hostname: dicom_worker.local
    volumes:
      - ${BACKUP_DIR:?}:/backups
      - ${MOUNT_DIR:?}:/mnt
      - ${ROUTER_SPOOL_DIR:-router_spool}:/spool
```

Validate:
- `PROJECT_VERSION=0.0.0 docker compose -f docker-compose.base.yml -f docker-compose.dev.yml -p adit_dev config --quiet && echo dev-ok`
- `PROJECT_VERSION=0.0.0 docker compose -f docker-compose.base.yml -f docker-compose.prod.yml -p adit_prod config --quiet && echo prod-ok`

Expected: `dev-ok` and `prod-ok`.

- [ ] **Step 2: Document the router tunables in `example.env`**

After the commented `ROUTER_SENDER_REFRESH_SECONDS` line, add:

```

# A study the router received is routed this many seconds after its last image, and at
# the latest this many seconds after its first one.
# ROUTER_QUIET_PERIOD_SECONDS=300
# ROUTER_MAX_OPEN_SECONDS=3600

# How many days the router keeps the images of a failed delivery for a retry.
# ROUTER_FAILED_RETENTION_DAYS=7
```

- [ ] **Step 3: Add the Orthanc modality helpers**

In `adit/core/utils/orthanc_utils.py`, add to `OrthancRestHandler`, after `find`:

```python
    def add_modality(self, name: str, ae_title: str, host: str, port: int) -> None:
        r = self.session.put(
            f"http://{self.host}:{self.port}/modalities/{name}",
            json={"AET": ae_title, "Host": host, "Port": port},
        )
        r.raise_for_status()

    def remove_modality(self, name: str) -> None:
        r = self.session.delete(f"http://{self.host}:{self.port}/modalities/{name}")
        r.raise_for_status()

    def send_to_modality(self, name: str, resource_ids: list[str]) -> None:
        r = self.session.post(
            f"http://{self.host}:{self.port}/modalities/{name}/store",
            json={"Resources": resource_ids, "Synchronous": True},
        )
        r.raise_for_status()

    def instance_tags(self, instance_id: str) -> dict:
        r = self.session.get(
            f"http://{self.host}:{self.port}/instances/{instance_id}/simplified-tags"
        )
        r.raise_for_status()
        return r.json()
```

- [ ] **Step 4: Add a disabled example rule**

In `adit/core/management/commands/populate_example_data.py`:
- Change `from adit.router.models import RouterSender` to `from adit.router.models import RouterSender, RoutingRule`.
- Add this function after `create_server_nodes`:

```python
def create_router_example_rule(users: list[User], servers: list[DicomServer]) -> None:
    owner = next((user for user in users if user.is_staff), None)
    destination = next((server for server in servers if server.ae_title == "ORTHANC2"), None)
    if owner is None or destination is None:
        return

    RoutingRule.objects.create(
        name="Example: CT to Orthanc 2",
        enabled=False,
        filters_json=[{"mode": "include", "modality": "CT"}],
        destination=destination,
        trial_protocol_id="EXAMPLE",
        created_by=owner,
    )
```

- In `handle`, after `servers = create_server_nodes(groups)`, add `create_router_example_rule(users, servers)`.

- [ ] **Step 5: Write the end-to-end test**

Create `adit/router/tests/acceptance/__init__.py` (empty) and `adit/router/tests/acceptance/conftest.py`:

```python
import os

# The worker runs in a thread next to Django's sync test code.
os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")
```

Create `adit/router/tests/acceptance/test_router.py`:

```python
import threading
from datetime import timedelta
from pathlib import Path

import pytest
from adit_radis_shared.common.utils.testing_helpers import run_worker_once
from django.utils import timezone

from adit.core.utils.orthanc_utils import OrthancRestHandler
from adit.core.utils.pseudonymizer import deterministic_pseudonym
from adit.core.utils.testing_helpers import (
    free_port,
    setup_dimse_orthancs,
    wait_until_scp_accepts,
    wait_until_scp_idle,
)
from adit.router.factories import RoutingRuleFactory
from adit.router.models import RouterJob, RouterSender
from adit.router.utils import spool
from adit.router.utils.closer import run_spool_cycle
from adit.router.utils.intake import RouterStoreHandler, build_router_scp, load_intake_config

ROUTER_AE = "ROUTERE2E"


@pytest.mark.acceptance
@pytest.mark.order("last")
@pytest.mark.django_db(transaction=True)
def test_router_delivers_matching_studies_pseudonymized(tmp_path: Path, settings):
    orthanc1, orthanc2 = setup_dimse_orthancs()
    sender = RouterSender.objects.create(server=orthanc1)
    rule = RoutingRuleFactory.create(
        filters_json=[{"mode": "include", "modality": "CT"}],
        destination=orthanc2,
        trial_protocol_id="XNATPROJ",
    )
    settings.ROUTER_SPOOL_PATH = str(tmp_path)
    spool.ensure_spool_dirs(tmp_path)

    handler = RouterStoreHandler(tmp_path, min_free_bytes=0)
    handler.update_config(load_intake_config())
    port = free_port()
    scp = build_router_scp(tmp_path, handler, ae_title=ROUTER_AE, host="0.0.0.0", port=port)
    thread = threading.Thread(target=scp.start, daemon=True)
    thread.start()
    wait_until_scp_accepts(port, sender.calling_ae_title, ROUTER_AE)

    orthanc1_api = OrthancRestHandler(settings.ORTHANC1_HOST, settings.ORTHANC1_HTTP_PORT)
    orthanc2_api = OrthancRestHandler(settings.ORTHANC2_HOST, settings.ORTHANC2_HTTP_PORT)
    # The test runs in the web container. Orthanc resolves compose service names, but not
    # the containers' *.local hostnames.
    orthanc1_api.add_modality(ROUTER_AE, ROUTER_AE, "web", port)
    try:
        ct_study = orthanc1_api.find({"Level": "Study", "Query": {"PatientID": "1004"}})
        mr_study = orthanc1_api.find({"Level": "Study", "Query": {"PatientID": "1002"}})
        orthanc1_api.send_to_modality(ROUTER_AE, ct_study + mr_study)
    finally:
        orthanc1_api.remove_modality(ROUTER_AE)
        wait_until_scp_idle(scp)
        scp.stop()
        thread.join(timeout=5)

    run_spool_cycle(tmp_path, timezone.now() + timedelta(hours=2))

    job = RouterJob.objects.get()
    assert len(spool.list_batches(tmp_path)) == 1

    run_worker_once()

    pseudonym = deterministic_pseudonym(rule.pseudonym_salt, "1004")
    instances = orthanc2_api.find({"Level": "Instance", "Query": {"PatientID": pseudonym}})
    assert len(instances) == 10
    tags = orthanc2_api.instance_tags(instances[0])
    assert tags["PatientComments"].startswith(f"Project:XNATPROJ Subject:{pseudonym} ")
    assert orthanc2_api.find({"Level": "Study", "Query": {"PatientID": "1002"}}) == []
    job.refresh_from_db()
    assert job.status == RouterJob.Status.SUCCESS
```

- [ ] **Step 6: Run the end-to-end test**

Run: `uv run cli test -- adit/router/tests/acceptance/ -m acceptance`
Expected: PASS. Patient 1004's CT study arrives on Orthanc 2 under the rule's pseudonym with the XNAT text. Patient 1002's MR study never arrives, and its batch is gone.

- [ ] **Step 7: Update the docs**

In `AGENTS.md`:
- **mass_transfer entry:** change `(`FilterSpec` in `adit/core/utils/series_filters.py`: modality,` to `(`FilterSpec` in `adit/core/utils/series_filters.py`, shared with the DICOM router: modality,`.
- **router/ entry:** replace the whole entry with:

```
- **router/**: DICOM router. `./manage.py router` (the router container) accepts C-STORE (and answers C-ECHO) on `ROUTER_AE_TITLE` from enabled `RouterSender`s (a `DicomServer` plus the AE title it sends from) and writes each image durably to `incoming/<sender id>/<StudyInstanceUID>/` in the spool (`ROUTER_SPOOL_PATH`); unknown senders are rejected, and while `RouterSettings.suspended` is set or the spool is low on space images are answered with `0xA700`. The periodic `close_router_batches` (default queue, `ROUTER_CLOSE_CRON`) closes a study `ROUTER_QUIET_PERIOD_SECONDS` after its last image (at the latest `ROUTER_MAX_OPEN_SECONDS` after its first) into `batches/<sender id>/<batch id>/`, selects series per enabled `RoutingRule` (mass transfer JSON filters, a destination, optional pseudonymization with a per-rule salt, and a trial protocol ID XNAT uses as the project), deletes batches no rule matches and creates one `RouterJob`/`RouterTask` per matching rule; `RouterTaskProcessor` (dicom queue) pseudonymizes and sends the selected series, finished batches are deleted, failed ones kept for `ROUTER_FAILED_RETENTION_DAYS`, and `report_router_failures` mails the admins daily. Senders and rules are managed in the Django admin, where batches, jobs and tasks are read-only. Models: `RouterSettings`, `RouterSender`, `RoutingRule`, `RouterBatch`, `RouterJob`, `RouterTask`.
```

- **Docker Services:** in the `default_worker` and `dicom_worker` lines, append `; mounts the router spool`.
- **Environment Variables:** in the `ROUTER_AE_TITLE` line, after `ROUTER_SENDER_REFRESH_SECONDS` (default 30), add `, ROUTER_QUIET_PERIOD_SECONDS (default 300), ROUTER_MAX_OPEN_SECONDS (default 3600), ROUTER_FAILED_RETENTION_DAYS (default 7), ROUTER_QUARANTINE_RETENTION_DAYS (default 7), ROUTER_SENT_LIST_RETENTION_DAYS (default 30)`.

In `docs/dev-docs/architecture.md`:
- **Default Worker paragraph:** add `close_router_batches` and `report_router_failures` to its task list, and say that it mounts the router spool.
- **DICOM Worker paragraph:** add "and router deliveries (`RouterTask`), with the router spool mounted".
- **`#### **DICOM Router**` section:** replace its bullet with:

```
- **Router inbox and routing**: `./manage.py router` (the router container) accepts the images a PACS forwards from enabled `RouterSender`s and writes each one durably to `incoming/<sender id>/<StudyInstanceUID>/` in the spool. `close_router_batches` closes quiet studies into batches, selects series per enabled `RoutingRule` with the mass transfer filters (`select_study_series`), and creates a `RouterBatch` with one `RouterJob`/`RouterTask` per matching rule in one transaction. `RouterTaskProcessor` pseudonymizes with the rule's salt, sends over one association that requests exactly the stored (SOP class, transfer syntax) pairs, and records the sent SOP Instance UIDs so images forwarded again are left out.
```

In `docs/user-docs/admin-guide.md`, in the "Optional tuning" paragraph, replace the sentence that starts with "The router only receives so far" with:

```
Routing rules (filters, destination, pseudonymization, and the trial protocol ID XNAT uses as the project) are configured in the Django admin under Router; `ROUTER_QUIET_PERIOD_SECONDS`, `ROUTER_MAX_OPEN_SECONDS` and `ROUTER_FAILED_RETENTION_DAYS` tune how long studies wait in the spool.
```

In `docs/superpowers/specs/2026-09-30-dicom-router-design.md`, change the `Status:` line to:
`Status: approved; stages 1 and 2 implemented (feat/dicom-router-filters, feat/dicom-router-inbox), stage 3 on feat/dicom-router-rules`

- [ ] **Step 8: Check the router in the dev stack**

The router container from stage 2 keeps running.

1. Recreate the two workers so they mount the spool: `$COMPOSE up -d --no-deps default_worker dicom_worker`.
2. Create an enabled rule (CT to Orthanc 2) in the web container:

```bash
$COMPOSE exec web python manage.py shell -c "
from adit_radis_shared.accounts.models import User
from adit.core.models import DicomServer
from adit.router.models import RoutingRule
RoutingRule.objects.update_or_create(name='Check: CT to Orthanc 2', defaults=dict(
  enabled=True, filters_json=[{'mode': 'include', 'modality': 'CT'}],
  destination=DicomServer.objects.get(ae_title='ORTHANC2'), trial_protocol_id='CHECK',
  created_by=User.objects.filter(is_superuser=True).first()))
"
```

3. Send patient 1004's study from Orthanc 1 to the router:

```bash
$COMPOSE exec web bash -c 'study=$(curl -s -X POST http://orthanc1.local:6501/tools/find -d "{\"Level\":\"Study\",\"Query\":{\"PatientID\":\"1004\"}}" | python -c "import json,sys; print(json.load(sys.stdin)[0])"); curl -s -X POST http://orthanc1.local:6501/modalities/ROUTER/store -d "$study"'
```

4. Close and decide right away, instead of waiting out the quiet period:

```bash
$COMPOSE exec default_worker python manage.py shell -c "
from datetime import timedelta; from pathlib import Path; from django.utils import timezone
from adit.router.utils.closer import run_spool_cycle
run_spool_cycle(Path('/spool'), timezone.now() + timedelta(hours=2))
"
```

5. Within a minute the dev DICOM worker delivers. Check Orthanc 2:

```bash
$COMPOSE exec web curl -s -X POST http://orthanc2.local:6502/tools/find -d '{"Level":"Instance","Query":{"PatientComments":"Project:CHECK*"}}'
```

Expected: a JSON list of 10 instance IDs. The router job is `SUCCESS` in the Django admin under Router jobs.

6. Clean up: disable or delete the check rule.

- [ ] **Step 9: Run the full suite and lint**

Run: `uv run cli test` (it includes the acceptance tests) and then `uv run cli lint`.
Expected: all tests pass, and lint reports no errors.

- [ ] **Step 10: Commit**

```bash
git add docker-compose.base.yml example.env adit/core/utils/orthanc_utils.py \
  adit/core/management/commands/populate_example_data.py AGENTS.md docs/dev-docs/architecture.md \
  docs/user-docs/admin-guide.md docs/superpowers/specs/2026-09-30-dicom-router-design.md \
  adit/router/tests/acceptance/
git commit -m "Mount the router spool on the workers and route studies end to end"
```
