# Mass Transfer Resumable Automatic Retries Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Automatic Procrastinate retries of a mass transfer task resume from persisted `MassTransferVolume` rows instead of wiping the partition and re-fetching everything, so one dead series costs only its own retries.

**Architecture:** The partition wipe becomes conditional on a fresh queue cycle (`DicomTask.attempts <= 1`); resumed runs reload volume rows, reset retriably-failed ones to `PENDING`, and re-transfer only those. A per-volume `RetriableDicomError` never aborts the loop; one `RetriableDicomError` is raised at the end when retriable failures remain and attempts remain. The runner computes `is_final_attempt` from Procrastinate's per-cycle counter and passes it into the processor subprocess, replacing the stop-gap's `DicomTask.attempts`-based check (and its cancel→resume edge case).

**Tech Stack:** Django 5.1, Procrastinate, pytest (pytest-django, pytest-mock), factory-boy.

**Spec:** `docs/superpowers/specs/2026-07-16-mass-transfer-resumable-retries-design.md`

## Global Constraints

- Line length 100 (Ruff); Google Python Style Guide.
- Use `assert` for internal invariants (never run with `python -O`).
- Booleans: `default=False` is enough; no `blank`/`null` (non-string, but has a default).
- All test commands run through the dev containers: `uv run cli test -- <pytest args>`. Containers must be up (`uv run cli compose-up -- --watch`).
- Lint gate: `uv run cli lint` must pass at the end.
- Commit after every task. Current branch: `fix/mass-transfer-final-attempt-continue`.
- `settings.DICOM_TASK_MAX_ATTEMPTS` is 3 in `adit/settings/base.py:473` — never hardcode 3 in tests; reference the setting.

---

### Task 1: Add `retriable` field to `MassTransferVolume`

**Files:**
- Modify: `adit/mass_transfer/models.py` (class `MassTransferVolume`, around line 169)
- Create: `adit/mass_transfer/migrations/0006_masstransfervolume_retriable.py` (via makemigrations)

**Interfaces:**
- Produces: `MassTransferVolume.retriable: bool` (model field, default `False`). Later tasks set it `True` alongside `status=Status.ERROR` when the failure was a `RetriableDicomError`, and reset it to `False` when the volume is re-queued.

- [ ] **Step 1: Add the field**

In `adit/mass_transfer/models.py`, `MassTransferVolume`, directly below the `status` field (line 169):

```python
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    # Only meaningful with status=ERROR: the failure was a RetriableDicomError,
    # so a later task attempt resets this volume to PENDING and re-transfers it.
    retriable = models.BooleanField(default=False)
    log = models.TextField(blank=True, default="")
```

- [ ] **Step 2: Generate the migration**

Run: `uv run ./manage.py makemigrations mass_transfer`
Expected: creates `adit/mass_transfer/migrations/0006_masstransfervolume_retriable.py` containing exactly:

```python
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("mass_transfer", "0005_add_partition_constraint"),
    ]

    operations = [
        migrations.AddField(
            model_name="masstransfervolume",
            name="retriable",
            field=models.BooleanField(default=False),
        ),
    ]
```

(If the command must run in the container instead, use `uv run cli shell` conventions or run it via the web container; the generated file content is what matters.)

- [ ] **Step 3: Sanity-check migrations apply in the test run**

Run: `uv run cli test -- adit/mass_transfer/tests/test_processor.py -k "test_process_creates_volume_records_on_success" -v`
Expected: PASS (pytest-django builds the schema from migrations; a broken migration fails here).

- [ ] **Step 4: Commit**

```bash
git add adit/mass_transfer/models.py adit/mass_transfer/migrations/0006_masstransfervolume_retriable.py
git commit -m "feat(mass_transfer): add retriable flag to MassTransferVolume"
```

---

### Task 2: Runner passes `is_final_attempt` into the processor

**Files:**
- Modify: `adit/core/processors.py` (class `DicomTaskProcessor`, around line 27-35)
- Modify: `adit/core/tasks.py:83-146` (`_run_dicom_task`)
- Test: `adit/core/tests/test_tasks.py`

**Interfaces:**
- Consumes: nothing from other tasks.
- Produces: `DicomTaskProcessor.is_final_attempt: bool` (class attribute, default `False`), set by the runner before `process()` runs. `True` iff the current run is the last Procrastinate attempt of this queued job (`context.job.attempts + 1 >= settings.DICOM_TASK_MAX_ATTEMPTS`). Task 4 reads `self.is_final_attempt` in the mass transfer processor.

- [ ] **Step 1: Write the failing test**

Append to `adit/core/tests/test_tasks.py` (the file already defines `_FakeFuture`, `_make_context`, `ExampleProcessor`, and the factories; add `from django.conf import settings` to the imports at the top):

```python
@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(
    "procrastinate_attempts,expected_final",
    [
        (0, False),
        (settings.DICOM_TASK_MAX_ATTEMPTS - 1, True),
    ],
)
def test_run_dicom_task_passes_is_final_attempt_to_subprocess(
    mocker: MockerFixture, procrastinate_attempts: int, expected_final: bool
):
    """The runner computes is_final_attempt from Procrastinate's 0-indexed
    per-job attempt counter and passes it into the processor subprocess."""
    dicom_job = ExampleTransferJobFactory.create(status=DicomJob.Status.PENDING)
    dicom_task = ExampleTransferTaskFactory.create(status=DicomTask.Status.PENDING, job=dicom_job)
    model_label = get_model_label(ExampleTransferTask)

    result: ProcessingResult = {
        "status": DicomTask.Status.SUCCESS,
        "message": "ok",
        "log": "",
    }
    captured: dict[str, tuple] = {}

    def fake_process(*p_args, **p_kwargs):
        def decorator(func):
            def wrapper(*args, **kwargs):
                captured["args"] = args
                return _FakeFuture(result=result)

            return wrapper

        return decorator

    def fake_thread(*t_args, **t_kwargs):
        def decorator(func):
            def wrapper(*args, **kwargs):
                return None

            return wrapper

        return decorator

    mocker.patch.object(tasks_module.concurrent, "process", side_effect=fake_process)
    mocker.patch.object(tasks_module.concurrent, "thread", side_effect=fake_thread)

    tasks_module._run_dicom_task(
        _make_context(attempts=procrastinate_attempts), model_label, dicom_task.pk
    )

    assert captured["args"] == (model_label, dicom_task.pk, expected_final)


def test_dicom_task_processor_is_final_attempt_defaults_to_false():
    assert DicomTaskProcessor.is_final_attempt is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run cli test -- adit/core/tests/test_tasks.py -k "is_final_attempt" -v`
Expected: FAIL — the parametrized test with `captured["args"] == (..., expected_final)` fails because the subprocess is called with only 2 args; the default-attribute test fails with `AttributeError: ... has no attribute 'is_final_attempt'`.

- [ ] **Step 3: Implement**

In `adit/core/processors.py`, add to `DicomTaskProcessor` directly below the `logs` class attribute (line 30):

```python
class DicomTaskProcessor(abc.ABC):
    app_name: str
    dicom_task_class: type[DicomTask]
    app_settings_class: type[DicomAppSettings]
    logs: list[DicomLogEntry] = []
    # Set by the task runner before process() runs: True when the current run
    # is the last Procrastinate attempt of this queued job, i.e. no automatic
    # retry will follow a RetriableDicomError.
    is_final_attempt: bool = False
```

In `adit/core/tasks.py`, `_run_dicom_task`: after `dicom_task.save()` / the "Processing ... started" log (line 88), compute the flag and thread it through the subprocess; simplify the `except RetriableDicomError` handler to use it. The affected region (lines 83-146) becomes:

```python
    dicom_task.status = DicomTask.Status.IN_PROGRESS
    dicom_task.start = timezone.now()
    dicom_task.attempts += 1
    dicom_task.save()

    logger.info(f"Processing of {dicom_task} started.")

    # Cave, the attempts of the Procrastinate job must not be the same number
    # as the attempts of the DicomTask. The DicomTask could be started by multiple
    # Procrastinate jobs (e.g. if the user canceled and resumed the same task).
    # Procrastinate's attempts is 0-indexed (counts previous attempts).
    # On attempt N, attempts = N-1, so the final attempt is when
    # attempts + 1 >= max_attempts.
    is_final_attempt = context.job.attempts + 1 >= settings.DICOM_TASK_MAX_ATTEMPTS

    @concurrent.process(timeout=process_timeout, daemon=True)
    def _process_dicom_task(
        model_label: str, task_id: int, is_final_attempt: bool
    ) -> ProcessingResult:
        dicom_task = get_dicom_task(model_label, task_id)
        processor = get_dicom_processor(dicom_task)
        processor.is_final_attempt = is_final_attempt

        logger.info(f"Start processing of {dicom_task}.")
        return processor.process()

    @concurrent.thread()
    def _monitor_task(context: JobContext, future: ProcessFuture) -> None:
        while not future.done():
            if context.should_abort():
                future.cancel()
                sleep(settings.DICOM_TASK_CANCELED_MONITOR_INTERVAL)
        db.close_old_connections()

    try:
        future = cast(
            ProcessFuture, _process_dicom_task(model_label, task_id, is_final_attempt)
        )
        _monitor_task(context, future)
        result: ProcessingResult = future.result()
        dicom_task.status = result["status"]
        dicom_task.message = result["message"]
        dicom_task.log = result["log"]
        ensure_db_connection()
```

and the retriable handler (previously the `context.job.attempts + 1 < ...` check at line 134):

```python
    except RetriableDicomError as err:
        logger.exception("Retriable error occurred during %s.", dicom_task)

        if not is_final_attempt:
            dicom_task.status = DicomTask.Status.PENDING
            dicom_task.message = "Task failed, but will be retried."
            if dicom_task.log:
                dicom_task.log += "\n"
            dicom_task.log += str(err)
        else:
            dicom_task.status = DicomTask.Status.FAILURE
            dicom_task.message = str(err)

        ensure_db_connection()

        raise err
```

Everything else in the function is unchanged.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run cli test -- adit/core/tests/test_tasks.py -v`
Expected: PASS — the two new tests plus all existing runner tests (especially `test_process_dicom_task_that_should_be_retried` and `test_process_dicom_task_transitions_to_failure_after_max_retries`, which exercise the refactored handler).

- [ ] **Step 5: Commit**

```bash
git add adit/core/processors.py adit/core/tasks.py adit/core/tests/test_tasks.py
git commit -m "feat(core): pass is_final_attempt from task runner into processors"
```

---

### Task 3: `_transfer_single_series` — mark retriable and continue; per-series cleanup

**Files:**
- Modify: `adit/mass_transfer/processors.py:517-639` (`_is_final_attempt`, `_transfer_single_series`)
- Test: `adit/mass_transfer/tests/test_processor.py` (replaces `test_transfer_single_series_final_attempt_boundary`, lines 2331-2369)

**Interfaces:**
- Consumes: `MassTransferVolume.retriable` (Task 1).
- Produces: `_transfer_single_series(operator, volume, job, pseudonymizer, subject_id, output_base, dest_operator)` never raises. On `RetriableDicomError` it sets `volume.status = ERROR`, `volume.retriable = True`, `volume.log = str(err)` and returns. It deletes a pre-existing series output folder before exporting (folder destinations). Task 4's loop and end-of-loop raise rely on exactly this contract.

- [ ] **Step 1: Write the failing tests**

In `adit/mass_transfer/tests/test_processor.py`, replace the whole "final-attempt-continue tests" section (the comment banner at lines 2325-2328 and `test_transfer_single_series_final_attempt_boundary` at lines 2331-2369; keep `test_process_continues_past_dead_series_on_final_attempt` and `test_process_final_attempt_all_dead_is_failure` for now — Task 4 updates them) with:

```python
# ---------------------------------------------------------------------------
# resumable-retries tests (see
# docs/superpowers/specs/2026-07-16-mass-transfer-resumable-retries-design.md)
# ---------------------------------------------------------------------------


def test_transfer_single_series_marks_retriable_and_continues(
    mocker: MockerFixture, tmp_path: Path
):
    """A per-volume RetriableDicomError no longer propagates: the volume is
    marked ERROR + retriable so a later attempt re-transfers it, and the
    partition loop can continue."""
    processor = _make_processor(mocker)
    processor.mass_task.partition_key = "20240101"
    job = processor.mass_task.job
    job.convert_to_nifti = False
    mocker.patch.object(processor, "_export_series", side_effect=RetriableDicomError("boom"))
    mocker.patch.object(MassTransferVolume, "save")
    volume = MassTransferVolume(
        series_instance_uid="s-1", study_datetime=timezone.now(), number_of_images=5
    )

    # Must not raise
    processor._transfer_single_series(
        mocker.MagicMock(), volume, job, None, "subj", tmp_path, None
    )

    assert volume.status == MassTransferVolume.Status.ERROR
    assert volume.retriable is True
    assert "boom" in volume.log


def test_transfer_single_series_permanent_error_not_retriable(
    mocker: MockerFixture, tmp_path: Path
):
    processor = _make_processor(mocker)
    processor.mass_task.partition_key = "20240101"
    job = processor.mass_task.job
    job.convert_to_nifti = False
    mocker.patch.object(processor, "_export_series", side_effect=DicomError("bad series"))
    mocker.patch.object(MassTransferVolume, "save")
    volume = MassTransferVolume(
        series_instance_uid="s-1", study_datetime=timezone.now(), number_of_images=5
    )

    processor._transfer_single_series(
        mocker.MagicMock(), volume, job, None, "subj", tmp_path, None
    )

    assert volume.status == MassTransferVolume.Status.ERROR
    assert volume.retriable is False


def test_transfer_single_series_cleans_stale_series_folder(
    mocker: MockerFixture, tmp_path: Path
):
    """A partially written series folder from a previous attempt is removed
    before re-export (folder exports are not atomic)."""
    processor = _make_processor(mocker)
    processor.mass_task.partition_key = "20240101"
    job = processor.mass_task.job
    job.convert_to_nifti = False
    mocker.patch.object(MassTransferVolume, "save")
    volume = MassTransferVolume(
        series_instance_uid="s-1",
        study_description="Brain CT",
        series_description="Axial",
        series_number=1,
        study_datetime=timezone.now(),
        number_of_images=5,
    )
    output_path = (
        tmp_path
        / "20240101"
        / "subj"
        / _study_folder_name(volume.study_description, volume.study_datetime)
        / _series_folder_name(
            volume.series_description, volume.series_number, volume.series_instance_uid
        )
    )
    output_path.mkdir(parents=True)
    stale_file = output_path / "stale.dcm"
    stale_file.write_bytes(b"partial")

    mocker.patch.object(processor, "_export_series", side_effect=_fake_export_success)

    processor._transfer_single_series(
        mocker.MagicMock(), volume, job, None, "subj", tmp_path, None
    )

    assert not stale_file.exists()
    assert volume.status == MassTransferVolume.Status.EXPORTED
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run cli test -- adit/mass_transfer/tests/test_processor.py -k "transfer_single_series" -v`
Expected: `test_transfer_single_series_marks_retriable_and_continues` FAILS (the RetriableDicomError propagates — the current code re-raises on non-final attempts, and `_make_processor`'s MagicMock task has a MagicMock `attempts` so `_is_final_attempt()` comparison is unreliable); `test_transfer_single_series_cleans_stale_series_folder` FAILS (stale file survives). The permanent-error test may already pass (`retriable` defaults to `False`).

- [ ] **Step 3: Implement**

In `adit/mass_transfer/processors.py`:

a) Delete `_is_final_attempt()` entirely (lines 517-524).

b) In `_transfer_single_series`, update the docstring and add the pre-export cleanup right after `output_path` is computed (currently lines 561-567), and replace the `except RetriableDicomError` branch (lines 593-608). The method becomes:

```python
    def _transfer_single_series(
        self,
        operator: DicomOperator,
        volume: MassTransferVolume,
        job: MassTransferJob,
        pseudonymizer: Pseudonymizer | None,
        subject_id: str,
        output_base: Path | None,
        dest_operator: DicomOperator | None = None,
    ) -> None:
        """Export (and optionally convert) a single series.

        Updates volume fields in place and saves. Never raises: a retriable
        failure is recorded on the volume (status=ERROR, retriable=True) so
        that process() can schedule a task retry after the whole partition
        was attempted.
        """
        try:
            if dest_operator:
                self._export_series_to_server(
                    operator,
                    volume,
                    pseudonymizer,
                    subject_id,
                    dest_operator,
                )
            else:
                assert output_base is not None
                study_folder = _study_folder_name(
                    volume.study_description,
                    volume.study_datetime,
                )
                series_folder = _series_folder_name(
                    volume.series_description,
                    volume.series_number,
                    volume.series_instance_uid,
                )
                output_path = (
                    output_base
                    / self.mass_task.partition_key
                    / subject_id
                    / study_folder
                    / series_folder
                )

                if output_path.exists():
                    # A previous attempt may have written a partial series
                    # (folder exports are not atomic) — start clean.
                    shutil.rmtree(output_path)

                if job.convert_to_nifti:
                    if volume.modality in settings.MODALITIES_EXCLUDED_FROM_NIFTI_CONVERSION:
                        logger.debug(
                            f"Skipping series {volume.series_instance_uid} "
                            f"(modality {volume.modality} excluded from NIfTI conversion)"
                        )
                        volume.status = MassTransferVolume.Status.SKIPPED
                        volume.log = f"Modality {volume.modality} excluded from NIfTI conversion"
                    else:
                        self._export_and_convert_series(
                            operator,
                            volume,
                            pseudonymizer,
                            subject_id,
                            output_path,
                        )
                else:
                    self._export_series_to_folder(
                        operator,
                        volume,
                        pseudonymizer,
                        subject_id,
                        output_path,
                    )
        except RetriableDicomError as err:
            # Don't abort the partition for one dead series. process() checks
            # for retriable volumes after the loop and raises once if a task
            # retry should re-transfer them.
            volume.status = MassTransferVolume.Status.ERROR
            volume.retriable = True
            volume.log = str(err)
        except Exception as err:
            logger.exception(
                "Mass transfer failed for series %s",
                volume.series_instance_uid,
            )
            volume.status = MassTransferVolume.Status.ERROR
            volume.log = str(err)
        finally:
            if volume.status == MassTransferVolume.Status.PENDING:
                logger.error(
                    "Volume %s still PENDING after transfer — setting to ERROR.",
                    volume.series_instance_uid,
                )
                volume.status = MassTransferVolume.Status.ERROR
                volume.log = "Internal error: volume status was not updated after transfer."
            try:
                volume.save(
                    update_fields=[
                        "status",
                        "retriable",
                        "log",
                        "study_instance_uid_pseudonymized",
                        "series_instance_uid_pseudonymized",
                        "converted_file",
                        "updated",
                    ]
                )
            except Exception:
                logger.exception(
                    "Failed to save volume %s status to database",
                    volume.series_instance_uid,
                )
```

Note: `"retriable"` was added to `update_fields`; the cleanup block is new; the retriable branch no longer raises and no longer consults the attempt number.

- [ ] **Step 4: Run tests to verify the new ones pass**

Run: `uv run cli test -- adit/mass_transfer/tests/test_processor.py -k "transfer_single_series" -v`
Expected: all three new tests PASS. Do NOT run the whole file yet — `process()`-level tests that expect the old abort behavior (`test_process_reraises_retriable_dicom_error`, the two remaining final-attempt tests, `test_server_destination_upload_retriable_error_propagates`) are now red; Task 4 fixes `process()` and those tests together.

- [ ] **Step 5: Commit**

```bash
git add adit/mass_transfer/processors.py adit/mass_transfer/tests/test_processor.py
git commit -m "feat(mass_transfer): mark retriable volume failures and clean stale series folders"
```

---

### Task 4: Resumable `process()` — conditional wipe, retriable reset, whole-partition summary, end-of-loop raise

**Files:**
- Modify: `adit/mass_transfer/processors.py:301-374` (`process`), `448-515` (`_transfer_grouped_series`), `768-816` (`_build_task_summary`)
- Test: `adit/mass_transfer/tests/test_processor.py` (helpers `_make_process_env`/`_make_process_env_server_dest`, several existing `process()` tests, new DB-integration tests)

**Interfaces:**
- Consumes: `MassTransferVolume.retriable` (Task 1), `self.is_final_attempt` (Task 2), the never-raises `_transfer_single_series` contract (Task 3).
- Produces:
  - `process()` — wipes folder + volume rows only when `self.mass_task.attempts <= 1`; skips discovery when volume rows exist for the partition; raises `RetriableDicomError(f"{n} of {total} volumes failed retriably and will be retried.")` when retriable failures remain and `not self.is_final_attempt`.
  - `_transfer_grouped_series(operator, volumes: list[MassTransferVolume], job, pseudonymizer, output_base, dest_operator=None) -> dict` — new signature: takes ALL partition volumes, transfers only the `PENDING` ones, raises at the end or returns the summary.
  - `_build_task_summary(volumes: list[MassTransferVolume]) -> dict` — new signature: computes counts from the volume objects (whole partition), not loop counters.
  - `_reset_retriable_volumes(volumes: list[MassTransferVolume]) -> None` — static method, resets ERROR+retriable volumes to PENDING in memory and in the DB.

- [ ] **Step 1: Update the mocked-test helpers**

In `adit/mass_transfer/tests/test_processor.py`, in BOTH `_make_process_env` (line 693) and `_make_process_env_server_dest` (line 743), replace:

```python
    # Default to a non-final attempt so per-volume retriable errors re-raise.
    # Tests that exercise the final-attempt-continue path opt in explicitly.
    processor.mass_task.attempts = settings.DICOM_TASK_MAX_ATTEMPTS - 1
```

with:

```python
    # Default to the first attempt of a queue cycle (fresh run: wipe +
    # discovery). Resume behavior (attempts >= 2) is covered by the DB
    # integration tests, which need real querysets.
    processor.mass_task.attempts = 1
```

This matters: with a MagicMock `attempts >= 2` the new `process()` would take the resume path and call `list()` on a mocked queryset, which breaks.

- [ ] **Step 2: Rewrite the stale mocked tests to the new contract (failing against current code)**

a) Replace `test_process_reraises_retriable_dicom_error` (line 772) with:

```python
def test_process_transfers_all_volumes_then_raises_retriable(
    mocker: MockerFixture, tmp_path: Path
):
    """A retriable failure no longer aborts the partition: the remaining
    volumes still transfer, and one RetriableDicomError is raised at the end
    so Procrastinate retries only the failed volumes."""
    processor = _make_process_env(mocker, tmp_path)
    series = [
        _make_discovered(series_uid="s-1"),
        _make_discovered(series_uid="s-2"),
    ]
    mocker.patch.object(processor, "_discover_series", return_value=series)

    captured: dict[str, MassTransferVolume] = {}

    def fake_export(*args, **kwargs):
        volume = args[1]
        captured[volume.series_instance_uid] = volume
        if volume.series_instance_uid == "s-1":
            raise RetriableDicomError("PACS connection lost")
        return (1, "", "")

    mocker.patch.object(processor, "_export_series", side_effect=fake_export)

    with pytest.raises(RetriableDicomError, match="1 of 2 volumes"):
        processor.process()

    # The healthy volume was still transferred before the raise
    assert captured["s-2"].status == MassTransferVolume.Status.EXPORTED
    assert captured["s-1"].status == MassTransferVolume.Status.ERROR
    assert captured["s-1"].retriable is True
```

b) Replace `test_process_continues_past_dead_series_on_final_attempt` (line 2371) with (same body, but drive the behavior via `is_final_attempt` instead of `attempts`):

```python
def test_process_continues_past_dead_series_on_final_attempt(
    mocker: MockerFixture, tmp_path: Path
):
    """On the final attempt, one dead series among healthy ones yields WARNING:
    the dead volume stays ERROR and no exception propagates."""
    processor = _make_process_env(mocker, tmp_path)
    processor.is_final_attempt = True
    series = [
        _make_discovered(series_uid="s-1"),
        _make_discovered(series_uid="s-2"),
    ]
    mocker.patch.object(processor, "_discover_series", return_value=series)

    captured: dict[str, MassTransferVolume] = {}

    def fake_export(*args, **kwargs):
        volume = args[1]
        captured[volume.series_instance_uid] = volume
        if volume.series_instance_uid == "s-1":
            raise RetriableDicomError("PACS connection lost")
        return (1, "", "")

    mocker.patch.object(processor, "_export_series", side_effect=fake_export)

    result = processor.process()  # must not raise

    assert result["status"] == MassTransferTask.Status.WARNING
    assert "Processed: 1" in result["log"]
    assert "Failed: 1" in result["log"]
    assert captured["s-1"].status == MassTransferVolume.Status.ERROR
    assert "PACS connection lost" in captured["s-1"].log
    assert captured["s-2"].status == MassTransferVolume.Status.EXPORTED
```

c) Replace `test_process_final_attempt_all_dead_is_failure` (line 2404) with:

```python
def test_process_final_attempt_all_dead_is_failure(mocker: MockerFixture, tmp_path: Path):
    """On the final attempt where every series is dead, the task is FAILURE."""
    processor = _make_process_env(mocker, tmp_path)
    processor.is_final_attempt = True
    series = [
        _make_discovered(series_uid="s-1"),
        _make_discovered(series_uid="s-2"),
    ]
    mocker.patch.object(processor, "_discover_series", return_value=series)
    mocker.patch.object(processor, "_export_series", side_effect=RetriableDicomError("PACS down"))

    result = processor.process()  # must not raise

    assert result["status"] == MassTransferTask.Status.FAILURE
    assert "Failed: 2" in result["log"]
```

d) Rename `test_process_cleans_partition_on_retry` (line 868) to `test_process_cleans_partition_on_fresh_cycle` and update its docstring — behavior is unchanged for `attempts = 1` (the helper's new default):

```python
def test_process_cleans_partition_on_fresh_cycle(mocker: MockerFixture, tmp_path: Path):
    """On the first attempt of a queue cycle, ALL pre-existing volumes for the
    partition are deleted and rediscovered (user Retry/Restart semantics)."""
```

(body unchanged). Apply the same rename/docstring treatment to `test_process_server_destination_cleans_volumes_on_retry` (line 923) → `test_process_server_destination_cleans_volumes_on_fresh_cycle`.

e) Replace `test_server_destination_upload_retriable_error_propagates` (line 1013) with:

```python
def test_server_destination_upload_retriable_error_marks_volume_and_raises_at_end(
    mocker: MockerFixture,
):
    """When upload_images raises RetriableDicomError, the volume is marked
    retriable and the aggregated end-of-loop error is raised."""
    processor, mock_dest_operator = _make_process_env_server_dest(mocker)
    series = [_make_discovered(series_uid="s-1")]

    mocker.patch.object(processor, "_discover_series", return_value=series)

    def fake_export(op, s, path, subject_id, pseudonymizer):
        return (1, "pseudo-study-uid", "pseudo-series-uid")

    mocker.patch.object(processor, "_export_series", side_effect=fake_export)
    mock_dest_operator.upload_images.side_effect = RetriableDicomError("Connection reset")

    with pytest.raises(RetriableDicomError, match="1 of 1 volumes"):
        processor.process()
```

f) Add a new mocked test right after it, pinning the spec's "retriable error outside the per-volume loop still propagates as-is" clause:

```python
def test_process_retriable_error_during_discovery_propagates(
    mocker: MockerFixture, tmp_path: Path
):
    """A RetriableDicomError raised before any volumes exist (discovery)
    still aborts and retries the whole task unchanged."""
    processor = _make_process_env(mocker, tmp_path)
    mocker.patch.object(
        processor, "_discover_series", side_effect=RetriableDicomError("PACS down")
    )

    with pytest.raises(RetriableDicomError, match="PACS down"):
        processor.process()
```

- [ ] **Step 3: Write the new DB-integration tests (failing)**

Append after the tests from Task 3 in the resumable-retries section:

```python
@pytest.mark.django_db
def test_process_resumes_without_wipe_or_rediscovery(
    mocker: MockerFixture, mass_transfer_env
):
    """An automatic retry (attempts >= 2) keeps completed volumes and their
    files, skips discovery, and re-transfers only retriable volumes."""
    env = mass_transfer_env
    env.task.attempts = 2
    now = timezone.now()

    exported = MassTransferVolume.objects.create(
        job=env.job,
        task=env.task,
        partition_key=env.task.partition_key,
        patient_id="PAT1",
        study_instance_uid="study-1",
        series_instance_uid="s-1",
        study_datetime=now,
        number_of_images=5,
        status=MassTransferVolume.Status.EXPORTED,
    )
    retriable = MassTransferVolume.objects.create(
        job=env.job,
        task=env.task,
        partition_key=env.task.partition_key,
        patient_id="PAT1",
        study_instance_uid="study-1",
        series_instance_uid="s-2",
        study_datetime=now,
        number_of_images=5,
        status=MassTransferVolume.Status.ERROR,
        retriable=True,
        log="old retriable error",
    )
    permanent = MassTransferVolume.objects.create(
        job=env.job,
        task=env.task,
        partition_key=env.task.partition_key,
        patient_id="PAT1",
        study_instance_uid="study-1",
        series_instance_uid="s-3",
        study_datetime=now,
        number_of_images=5,
        status=MassTransferVolume.Status.ERROR,
        retriable=False,
        log="unreadable series",
    )

    # A file written by the previous attempt must survive the resumed run
    base_dir = _destination_base_dir(env.destination, env.job)
    prior_file = base_dir / env.task.partition_key / "done.dcm"
    prior_file.parent.mkdir(parents=True, exist_ok=True)
    prior_file.write_bytes(b"already transferred")

    processor = MassTransferTaskProcessor(env.task)
    mocker.patch("adit.mass_transfer.processors.DicomOperator")
    discover_mock = mocker.patch.object(processor, "_discover_series")
    exported_uids: list[str] = []

    def fake_export(op, volume, *args, **kwargs):
        exported_uids.append(volume.series_instance_uid)
        return (1, "", "")

    mocker.patch.object(processor, "_export_series", side_effect=fake_export)

    result = processor.process()

    discover_mock.assert_not_called()
    assert exported_uids == ["s-2"]
    assert prior_file.exists()

    exported.refresh_from_db()
    retriable.refresh_from_db()
    permanent.refresh_from_db()
    assert exported.status == MassTransferVolume.Status.EXPORTED
    assert retriable.status == MassTransferVolume.Status.EXPORTED
    assert retriable.retriable is False
    assert permanent.status == MassTransferVolume.Status.ERROR

    # Summary covers the whole partition, not just the resumed volumes
    assert result["status"] == MassTransferTask.Status.WARNING
    assert "Series found: 3" in result["log"]
    assert "Processed: 2" in result["log"]
    assert "Failed: 1" in result["log"]


@pytest.mark.django_db
def test_process_fresh_cycle_wipes_stale_volumes_and_rediscovers(
    mocker: MockerFixture, mass_transfer_env
):
    """attempts <= 1 (fresh job or user Retry/Restart) keeps today's
    clean-slate semantics: rows and folder are wiped, discovery runs."""
    env = mass_transfer_env
    env.task.attempts = 1

    MassTransferVolume.objects.create(
        job=env.job,
        task=env.task,
        partition_key=env.task.partition_key,
        patient_id="PAT1",
        study_instance_uid="study-old",
        series_instance_uid="stale-1",
        study_datetime=timezone.now(),
        status=MassTransferVolume.Status.EXPORTED,
    )

    processor = MassTransferTaskProcessor(env.task)
    mocker.patch("adit.mass_transfer.processors.DicomOperator")
    mocker.patch.object(
        processor, "_discover_series", return_value=[_make_discovered(series_uid="s-new")]
    )
    mocker.patch.object(processor, "_export_series", side_effect=_fake_export_success)

    result = processor.process()

    assert not MassTransferVolume.objects.filter(series_instance_uid="stale-1").exists()
    new_volume = MassTransferVolume.objects.get(job=env.job, series_instance_uid="s-new")
    assert new_volume.status == MassTransferVolume.Status.EXPORTED
    assert result["status"] == MassTransferTask.Status.SUCCESS


@pytest.mark.django_db
def test_process_persists_retriable_flag_for_next_attempt(
    mocker: MockerFixture, mass_transfer_env
):
    """The retriable flag round-trips through the DB so the NEXT attempt can
    find and reset the volume."""
    env = mass_transfer_env
    env.task.attempts = 1

    processor = MassTransferTaskProcessor(env.task)
    mocker.patch("adit.mass_transfer.processors.DicomOperator")
    mocker.patch.object(
        processor,
        "_discover_series",
        return_value=[
            _make_discovered(series_uid="s-1"),
            _make_discovered(series_uid="s-2"),
        ],
    )

    def fake_export(op, volume, *args, **kwargs):
        if volume.series_instance_uid == "s-1":
            raise RetriableDicomError("PACS connection lost")
        return (1, "", "")

    mocker.patch.object(processor, "_export_series", side_effect=fake_export)

    with pytest.raises(RetriableDicomError, match="1 of 2 volumes"):
        processor.process()

    dead = MassTransferVolume.objects.get(job=env.job, series_instance_uid="s-1")
    healthy = MassTransferVolume.objects.get(job=env.job, series_instance_uid="s-2")
    assert dead.status == MassTransferVolume.Status.ERROR
    assert dead.retriable is True
    assert "PACS connection lost" in dead.log
    assert healthy.status == MassTransferVolume.Status.EXPORTED
    assert healthy.retriable is False
```

Note for the implementer: `mass_transfer_env.destination` is a `DicomFolder` (a `DicomNode` subclass); existing tests in this file pass it directly to `_destination_base_dir(destination, job)` (see line 2118), which is already imported at the top of the file.

- [ ] **Step 4: Run the new/updated tests to verify they fail**

Run: `uv run cli test -- adit/mass_transfer/tests/test_processor.py -k "resumes or fresh_cycle or persists_retriable or transfers_all_volumes or final_attempt" -v`
Expected: FAIL — current `process()` wipes unconditionally, aborts on the first retriable error (via the old re-raise... which Task 3 already removed, so instead: no end-of-loop raise happens and dead volumes silently count as plain failures).

- [ ] **Step 5: Implement the new `process()` and helpers**

In `adit/mass_transfer/processors.py`:

a) Replace the body of `process()` from the `try:` (line 326) down to the `_transfer_grouped_series` call (line 371) with:

```python
        try:
            filters = job.get_filters()

            if not filters:
                return {
                    "status": MassTransferTask.Status.FAILURE,
                    "message": "No filters configured for this job.",
                    "log": "Mass transfer requires at least one filter.",
                }

            # A fresh queue cycle starts from a clean slate. Automatic
            # Procrastinate retries (attempts >= 2) resume from the volumes
            # persisted by the previous attempt. User-initiated Retry/Restart
            # reset attempts to 0 via reset_tasks(), so they wipe again.
            is_fresh_cycle = self.mass_task.attempts <= 1
            if is_fresh_cycle:
                if output_base:
                    partition_path = output_base / self.mass_task.partition_key
                    if partition_path.exists():
                        shutil.rmtree(partition_path)

                MassTransferVolume.objects.filter(
                    job=job,
                    partition_key=self.mass_task.partition_key,
                ).delete()

            pseudonymizer: Pseudonymizer | None = None
            if job.pseudonymize and job.pseudonym_salt:
                pseudonymizer = Pseudonymizer(seed=job.pseudonym_salt)
            elif job.pseudonymize:
                pseudonymizer = Pseudonymizer()

            operator = DicomOperator(source_node.dicomserver, persistent=True)

            volumes: list[MassTransferVolume] = []
            if not is_fresh_cycle:
                volumes = list(
                    MassTransferVolume.objects.filter(
                        job=job,
                        partition_key=self.mass_task.partition_key,
                    )
                )

            if volumes:
                # Resumed run: re-queue only the volumes that failed retriably.
                self._reset_retriable_volumes(volumes)
            else:
                # Discovery: query the source server for all matching series.
                # Also reached on a resumed run that was interrupted before
                # any volumes were created.
                discovered = self._discover_series(operator, filters)
                operator.close()

                # Create PENDING volumes so they appear in the UI immediately
                volumes = self._create_pending_volumes(discovered, job, pseudonymizer)

            # Transfer: fetch pending series grouped by study
            return self._transfer_grouped_series(
                operator,
                volumes,
                job,
                pseudonymizer,
                output_base,
                dest_operator,
            )
        finally:
            if dest_operator:
                dest_operator.close()
```

b) Add `_reset_retriable_volumes` below `_group_volumes`:

```python
    @staticmethod
    def _reset_retriable_volumes(volumes: list[MassTransferVolume]) -> None:
        """Reset volumes that failed retriably in a previous attempt to PENDING."""
        retriable_volumes = [
            volume
            for volume in volumes
            if volume.status == MassTransferVolume.Status.ERROR and volume.retriable
        ]
        for volume in retriable_volumes:
            volume.status = MassTransferVolume.Status.PENDING
            volume.retriable = False
            volume.log = ""
            volume.converted_file = ""
        MassTransferVolume.objects.bulk_update(
            retriable_volumes, ["status", "retriable", "log", "converted_file"]
        )
```

c) Replace `_transfer_grouped_series` (lines 448-515) with:

```python
    def _transfer_grouped_series(
        self,
        operator: DicomOperator,
        volumes: list[MassTransferVolume],
        job: MassTransferJob,
        pseudonymizer: Pseudonymizer | None,
        output_base: Path | None,
        dest_operator: DicomOperator | None = None,
    ) -> dict:
        """Transfer all pending volumes and summarize the whole partition.

        Iterates patients -> studies -> volumes, updating each volume in
        place. Volumes already completed by a previous attempt are left
        untouched. Raises RetriableDicomError at the end when retriable
        failures remain and this is not the final task attempt.
        """
        pending = [v for v in volumes if v.status == MassTransferVolume.Status.PENDING]
        grouped_volumes = self._group_volumes(pending)

        study_count = 0
        for patient_id, studies in grouped_volumes.items():
            for study_uid, volumes_list in studies.items():
                study_count += 1

                if study_count > 1:
                    # Pacing delay between consecutive studies. Each study opens a
                    # fresh association and switches patient/study context, which is
                    # where a busy PACS is most likely to reject or drop requests.
                    # Series inside the same study fetch back-to-back over the already
                    # open association.
                    # TODO: Investigate if this is still necessary.
                    time.sleep(_DELAY_BETWEEN_STUDIES)

                # One fetch association per study
                try:
                    for volume in volumes_list:
                        subject_id = volume.pseudonym or sanitize_filename(volume.patient_id)
                        self._transfer_single_series(
                            operator,
                            volume,
                            job,
                            pseudonymizer,
                            subject_id,
                            output_base,
                            dest_operator,
                        )
                finally:
                    operator.close()

        retriable_failures = sum(
            1
            for v in volumes
            if v.status == MassTransferVolume.Status.ERROR and v.retriable
        )
        if retriable_failures and not self.is_final_attempt:
            raise RetriableDicomError(
                f"{retriable_failures} of {len(volumes)} volumes failed retriably "
                "and will be retried."
            )

        return self._build_task_summary(volumes)
```

d) Replace `_build_task_summary` (lines 768-816) with:

```python
    def _build_task_summary(self, volumes: list[MassTransferVolume]) -> dict:
        """Build the final status dict from the state of all partition volumes.

        Counts cover the whole partition (including volumes completed by
        earlier attempts), not just the volumes processed in this run.
        """
        total_volumes = len(volumes)
        study_count = len({v.study_instance_uid for v in volumes})
        total_processed = sum(
            1
            for v in volumes
            if v.status
            in (MassTransferVolume.Status.EXPORTED, MassTransferVolume.Status.CONVERTED)
        )
        total_skipped = sum(
            1 for v in volumes if v.status == MassTransferVolume.Status.SKIPPED
        )
        failed_volumes = [v for v in volumes if v.status == MassTransferVolume.Status.ERROR]
        total_failed = len(failed_volumes)
        failed_reasons: dict[str, int] = {}
        for volume in failed_volumes:
            reason = _short_error_reason(volume.log) if volume.log else "Unknown"
            failed_reasons[reason] = failed_reasons.get(reason, 0) + 1

        log_lines = [
            f"Partition {self.mass_task.partition_key}",
            f"Studies found: {study_count}",
            f"Series found: {total_volumes}",
            f"Processed: {total_processed}",
        ]
        if total_skipped:
            log_lines.append(f"Skipped: {total_skipped}")
        if total_failed:
            log_lines.append(f"Failed: {total_failed}")
        if failed_reasons:
            log_lines.append("Failure reasons:")
            for reason, count in failed_reasons.items():
                log_lines.append(f"  {count}x {reason}")

        if total_volumes == 0:
            status = MassTransferTask.Status.SUCCESS
            message = "No series found for this partition."
        elif total_failed and not total_processed:
            status = MassTransferTask.Status.FAILURE
            message = f"All {total_failed} series failed during mass transfer."
        else:
            total_series = total_processed + total_failed + total_skipped
            parts = [f"{total_processed} downloaded"]
            if total_failed:
                parts.append(f"{total_failed} failed")
            if total_skipped:
                parts.append(f"{total_skipped} skipped")

            status = (
                MassTransferTask.Status.WARNING if total_failed else MassTransferTask.Status.SUCCESS
            )
            message = f"{study_count} studies, {total_series} series ({', '.join(parts)})."

        return {
            "status": status,
            "message": message,
            "log": "\n".join(log_lines),
        }
```

- [ ] **Step 6: Run the full processor test file**

Run: `uv run cli test -- adit/mass_transfer/tests/test_processor.py -v`
Expected: ALL PASS. Failures to watch for: mocked tests where `MassTransferVolume.objects.filter` is patched — with `attempts = 1` the resume branch is never entered so the patched `filter(...).delete()` still covers the wipe; pseudonym-mode tests (lines 1030-1146) rely on `bulk_create` returning the in-memory objects, which the new flow still uses on the fresh path.

- [ ] **Step 7: Run the whole mass_transfer + core suites**

Run: `uv run cli test -- adit/mass_transfer/ adit/core/ -v`
Expected: ALL PASS (acceptance tests are excluded by default marker config; if any run and fail on unrelated infrastructure, note it, don't chase it).

- [ ] **Step 8: Commit**

```bash
git add adit/mass_transfer/processors.py adit/mass_transfer/tests/test_processor.py
git commit -m "feat(mass_transfer): resume automatic retries from persisted volume progress"
```

---

### Task 5: Final verification and spec cross-check

**Files:**
- Modify: none expected (fixups only)

**Interfaces:** none.

- [ ] **Step 1: Lint**

Run: `uv run cli lint`
Expected: clean. If Ruff flags the unused `patient_id`/`study_uid` loop variables in `_transfer_grouped_series` (they were already unused before this change), rename to `_patient_id`/`_study_uid` only if the linter complains — otherwise leave as-is.

- [ ] **Step 2: Full test suite**

Run: `uv run cli test`
Expected: PASS (same set of skips/exclusions as on the base branch — compare against `git stash`-free baseline only if something unrelated fails).

- [ ] **Step 3: Spec conformance check**

Re-read `docs/superpowers/specs/2026-07-16-mass-transfer-resumable-retries-design.md` section by section and confirm:
- Wipe keyed on `attempts <= 1` ✓ (Task 4)
- Discovery guarded by row existence, not attempt number ✓ (Task 4)
- Retriable reset clears `status`/`retriable`/`log`/`converted_file` ✓ (Task 4)
- Per-series cleanup before re-export, folder destinations only ✓ (Task 3)
- Continue past retriable errors on every attempt; `_is_final_attempt()` deleted ✓ (Task 3)
- Single end-of-loop raise gated on `is_final_attempt` from the runner ✓ (Tasks 2+4)
- Summary computed from whole-partition volume state ✓ (Task 4)

- [ ] **Step 4: Commit any fixups**

```bash
git add -A ':!.claude'
git commit -m "chore(mass_transfer): lint/test fixups for resumable retries"
```

(Skip the commit if there is nothing to fix.)
