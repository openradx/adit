# DICOM router — design

Date: 2026-09-30
Status: approved; stages 1 and 2 implemented (feat/dicom-router-filters, feat/dicom-router-inbox), stage 3 on feat/dicom-router-rules
Reference: issue [#143](https://github.com/openradx/adit/issues/143) and its analysis comment of
2026-09-24. Related: #415 (receiver hardening), #406 (AE titles in the Orthanc test configs),
#141 (series-level transfer). In-flight PR #374 also changes `adit/mass_transfer/processors.py`,
but not the filter code that stage 1 moves; #349 touches `docker-compose.dev.yml` and
`example.env`.

## 1. Goal

ADIT gets a DICOM router: a C-STORE listener on its own AE title and port that a PACS (or a
scanner) forwards studies to. Staff-defined rules decide, once per study, which series are sent
where, optionally pseudonymized. The motivating case: every CT head study of a patient aged 20 to
30 that arrives in the PACS is pseudonymized and sent to a research server such as XNAT, filed
under the right XNAT project.

It must work with any PACS that can forward studies by C-STORE. ADIT today only pulls: every
transfer starts with a user's job. The existing receiver
(`adit/core/management/commands/receiver.py`) only accepts the C-STORE sub-operations of C-MOVEs
that ADIT itself started, and drops everything else.

## 2. Decisions taken in the brainstorm

| Decision | Choice | Why |
|---|---|---|
| How studies arrive | The PACS forwards them by C-STORE to a separate router AE title and port | Works with any PACS. Polling the PACS was rejected. Instance Availability Notification (IHE RAD-49) depends on the PACS and is deferred (§11) |
| Where the work runs | A `router` container that only receives and spools, like the receiver; closing, rule checks and delivery run in the existing workers | Reuses the task runner, retries, crash recovery and job/task pages. Rejected: a self-contained router daemon (rebuilds all of that) and Orthanc as the inbox (a third-party container in production, and not "like the receiver") |
| Unit of decision | Per study, once no image of it has arrived for a quiet period | Rules describe studies. XNAT files a session after its own 5-minute quiet period, so one burst per study suits it |
| Late images | A new batch of the same study, sent as a follow-up with the same pseudonym and replacement UIDs | The destination ends up complete. Dropping late images would leave partial studies |
| Partial studies | No study is sent before it closes; a delivery counts only when every image was accepted; the rest is covered by late batches | DICOM has no end-of-study message and no way to take images back |
| Pseudonyms | Deterministic per rule: `compute_pseudonym(rule salt, PatientID)`, dicognito seeded with the same salt | The same patient lands under one XNAT subject, different rules are unlinkable, late batches join the first, and mass transfer with the same salt produces the same output |
| What is sent | The series a rule selects, with mass transfer filter semantics; a rule without series-level conditions sends the whole study; `EXCLUDE_MODALITIES` does not apply, as in mass transfer | One filter language and the same selection as mass transfer; series such as dose screenshots can be left out with exclude filters |
| Several rules | Independent: a batch is sent once per matching rule | Different projects must not interfere |
| Who writes rules | Staff only, as a mass transfer JSON filter list in the same editor; the creator is recorded | A rule is a standing export of patient data. A users-create/staff-approve flow can follow (§11) |
| Job structure | One `RouterJob` per (rule, batch) with one `RouterTask`; owner = the rule's creator | Every job has a clear owner (RADIS gives subscription jobs the subscription's owner), and a rule's page lists its own jobs |
| Senders | A `RouterSender` model with its own calling AE title, managed in the Django admin | Some PACS send under a different AE title than the one they answer queries on |

## 3. Components and data flow

```
PACS ==C-STORE==> router container ---> spool/incoming/<sender id>/<study>/
                                              | quiet for ROUTER_QUIET_PERIOD_SECONDS
default worker: close_router_batches <--------+
  move to spool/batches/<sender id>/<batch id>/
  read headers, check the enabled rules
  no match -> delete the folder
  match ----> RouterBatch + one RouterJob/RouterTask per matching rule
                                              |
DICOM worker: RouterTaskProcessor <-----------+
  read the task's series from the batch folder
  pseudonymize with the rule's salt, write the XNAT project text
  C-STORE (or STOW-RS) to the rule's destination
  record the sent SOP Instance UIDs
default worker: delete the batch folder once all its jobs are done
```

The spool is one directory tree on one filesystem, so every rename inside it is atomic:

```
spool/
  tmp/                                                            images being written
  incoming/<sender id>/<StudyInstanceUID>/<SOPInstanceUID>.dcm    open studies
  batches/<sender id>/<batch id>/<SOPInstanceUID>.dcm             closed batches
  quarantine/<YYYYMMDD>/<file>                                    unreadable files
```

`<sender id>` is the `RouterSender` primary key, not the AE title, because AE titles may contain
`/`. `<batch id>` is a UUID created when the folder is closed and reused as
`RouterBatch.batch_id`. Keeping the sender in the batch path lets a batch be decided again after a
crash without any database row.

### 3.1 Receive: `./manage.py router`

`adit/router/management/commands/router.py` is built like the receiver command
(`AsyncServerCommand`, `StoreScp` in a thread).

- If `ROUTER_AE_TITLE` is empty, the command logs that the router is disabled and idles without
  binding a port. Deployments that don't use the router need no configuration.
- `StoreScp` listens on `ROUTER_AE_TITLE` / `ROUTER_SCP_PORT` and requires the called AE title to
  match.
- It accepts every storage SOP class with uncompressed and common compressed transfer syntaxes and
  stores data as received, without decoding pixel data. The receiver uses pynetdicom's
  `AllStoragePresentationContexts`, which is uncompressed only (`adit/core/utils/store_scp.py:49`);
  the compressed syntaxes ADIT already uses are listed in
  `adit/core/utils/presentation_contexts.py`.
- **Senders:** the calling AE title must belong to an enabled `RouterSender`. The command reloads
  the senders (and `RouterSettings.suspended`) every `ROUTER_SENDER_REFRESH_SECONDS` and rejects
  unknown AE titles during association negotiation. pynetdicom treats an empty
  `require_calling_aet` as "accept anyone", so with no enabled sender the command must reject every
  association explicitly.
- **Per C-STORE:**
  1. Answer `0xA700` (Refused: Out of Resources) if the router is suspended or free space on the
     spool is below `ROUTER_SPOOL_MIN_FREE_GB`. The PACS keeps the image and retries later.
  2. Answer `0xC000` (Cannot understand) if `StudyInstanceUID` or `SOPInstanceUID` is missing or
     contains characters outside the UID character set, because both become path components.
  3. Write the dataset to `tmp/<uuid>.dcm` and `fsync` it. Create the study folder and `os.replace`
     the file into it. If the folder was moved to `batches/` between those two calls, the replace
     fails with `FileNotFoundError`: create the folder again and retry, so the image starts the
     next batch. `fsync` the folder.
  4. Answer `0x0000` (Success). A success reply is a promise that the image is on disk.
- There is no database access per image.
- At start the command deletes leftovers in `tmp/`. A crash while writing sent no success, so the
  PACS sends that image again.
- The sender allow-list and a store hook that returns the C-STORE status are added to `StoreScp`
  itself, so #415 can use the same allow-list for the receiver.

### 3.2 Close, decide, clean up: periodic task `close_router_batches`

`@app.periodic(cron=settings.ROUTER_CLOSE_CRON)` on the `default` queue, with a `queueing_lock`
and a `lock` so runs neither pile up nor overlap (compare `sweep_stale_tasks_periodic`,
`adit/core/tasks.py:50-54`). Every step is safe to repeat after a crash.

**Close.** An open study folder closes when its modification time (updated whenever an image is
moved in) is older than `ROUTER_QUIET_PERIOD_SECONDS`, or when its oldest file is older than
`ROUTER_MAX_OPEN_SECONDS`. Closing is one `os.rename` to `batches/<sender id>/<new uuid>/`.

**Decide.** Every batch folder without a `RouterBatch` row is decided. That includes folders left
behind by a crash between closing and deciding.

1. Read the headers of every file (`stop_before_pixels`). Unreadable files move to `quarantine/`.
   Build one `DiscoveredSeries` per series (`adit/core/utils/series_filters.py`) with
   `number_of_images` counted from the files, plus a map from series to SOP Instance UIDs.
2. For each enabled rule, select series as in §4. Drop the SOP instances already listed in
   `sent_instance_uids` of this rule's earlier `SUCCESS`/`WARNING` tasks for the same study and
   destination. The rule matches if at least one image is left.
3. If no rule matches, delete the folder and log the sender, study and image count. No database
   row is written.
4. Otherwise, in one transaction:
   - create the `RouterBatch`;
   - for each matching rule, create a `RouterJob` (status `PENDING`, owner = `rule.created_by`,
     `trial_protocol_id`/`trial_protocol_name` copied from the rule) with one `RouterTask`
     (`source` = the sender's server, `destination` = the rule's destination, `patient_id`,
     `study_uid`, `series_uids` = the selected series, `pseudonym` = the rule's deterministic
     pseudonym, or empty if the rule doesn't pseudonymize);
   - queue the tasks, so their queue rows appear only at commit. RADIS does the same in
     `_build_subscription_job` (openradx/radis, `radis/subscriptions/tasks.py`).
5. The unique constraints on `RouterBatch.batch_id` and on `RouterJob(rule, batch)` make a second
   decision of the same folder fail with `IntegrityError`. It is logged and skipped.

**Clean up.**
- A batch whose jobs all ended `SUCCESS`, `WARNING` or `CANCELED`: delete its folder and set
  `files_deleted_at`.
- A batch with a `FAILURE` job that closed more than `ROUTER_FAILED_RETENTION_DAYS` ago: delete its
  folder and set `files_deleted_at`.
- `quarantine/` entries older than `ROUTER_QUARANTINE_RETENTION_DAYS` and `tmp/` files older than
  one hour: delete.
- Free space below `ROUTER_SPOOL_MIN_FREE_GB`: mail the admins (`send_mail_to_admins`), at most
  once per `ROUTER_LOW_SPACE_MAIL_HOURS`.

A second periodic task, `report_router_failures`, runs daily at 07:00 like `check_disk_space`
(`adit/core/tasks.py:29-31`). It mails the admins the router jobs that failed in the last 24 hours,
with the date their images will be deleted, and clears `sent_instance_uids` on tasks older than
`ROUTER_SENT_LIST_RETENTION_DAYS`.

### 3.3 Deliver: `RouterTaskProcessor`

The processor is registered for `RouterTask` in `adit/router/apps.py`, as
`adit/mass_transfer/apps.py` does for its task. `RouterTask.queue_pending_task` defers
`adit.router.tasks.process_router_task`, which runs `_run_dicom_task` on the `dicom` queue with
`ROUTER_PROCESS_TIMEOUT` (the pattern of `process_mass_transfer_task`).

1. If the batch's `files_deleted_at` is set, fail with a `DicomError` saying the images were
   deleted from the spool and the PACS has to forward the study again.
2. Collect the files of `series_uids` from the batch folder and drop the SOP instances already
   sent under this rule for this study and destination. This is checked again here, because
   another batch may have finished in the meantime. If nothing is left, end with `SUCCESS` and
   "Nothing new to send."
3. If the rule pseudonymizes, use `Pseudonymizer(seed=rule.pseudonym_salt)` through
   `DicomManipulator.manipulate(ds, pseudonym, trial_protocol_id, trial_protocol_name)`. With a
   trial protocol ID this writes XNAT's `Project:… Subject:… Session:…` text into Patient Comments
   (`adit/core/utils/dicom_manipulator.py:35-39`). Write the results to a temporary folder.
4. `DicomOperator(destination).upload_images(folder)` sends them by C-STORE over one association,
   or by STOW-RS (`adit/core/utils/dicom_operator.py:469-477`).
5. On success, store the original SOP Instance UIDs in `sent_instance_uids` and report "Sent N
   images to <destination>".

Errors follow the existing task semantics. A `RetriableDicomError` (connection failure, rejected
images) is retried up to `DICOM_TASK_MAX_ATTEMPTS`; anything else fails the task. The rule's salt
is read at run time, and it cannot change once the rule has jobs (§5.2).

## 4. Rule semantics

- `filters_json` is a list of `FilterSchema` objects, validated as in the mass transfer form
  (`MassTransferJobForm.clean_filters_json`): a non-empty list with at least one include filter.
- A series is selected when it matches at least one include filter and no exclude filter, using
  `series_matches_filter` and `study_matches_filter` (`adit/core/utils/series_filters.py`). Include
  filters match case-sensitively. Exclude filters match case-insensitively, and an exclude filter
  with age bounds also excludes series whose birth date is unknown, exactly as in mass transfer.
- Study-level conditions (modality present in the study, study description, institution on study,
  age) are evaluated on the batch's own series.
- Age is computed from Patient Birth Date and Study Date. A study without a birth date does not
  match an include filter with age bounds.
- Modality is a series-level condition: `"modality": "CT"` selects the CT series of a study. A rule
  without series-level conditions selects every series.
- `EXCLUDE_MODALITIES` does not apply, the same as in mass transfer: only the rule's filters decide
  what is sent. Staff who want to leave out presentation states or structured reports add exclude
  filters, for example `{"mode": "exclude", "modality": "SR"}`.

## 5. Data model: `adit/router/models.py`

### 5.1 Models

**`RouterSender`**
- `server`: `OneToOneField(DicomServer, on_delete=PROTECT)`
- `calling_ae_title`: `CharField(max_length=16, unique=True)`; the admin form pre-fills the
  server's AE title
- `enabled`: `BooleanField(default=True)`

**`RoutingRule`**
- `name`: `CharField(max_length=100, unique=True)`
- `enabled`: `BooleanField(default=True)`
- `filters_json`: `JSONField`
- `destination`: `ForeignKey(DicomServer, on_delete=PROTECT)`; must support C-STORE or STOW-RS
- `pseudonymize`: `BooleanField(default=True)`
- `pseudonym_salt`: `CharField(max_length=64, blank=True, default=secrets.token_hex)`; cleared when
  `pseudonymize` is off, as in `MassTransferJob.clean`
- `trial_protocol_id`, `trial_protocol_name`: `CharField(max_length=64, blank=True, default="")`
  with the validators of `TransferJob`
- `created_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=PROTECT)`; users who created rules
  are deactivated, not deleted
- `created`, `updated`

**`RouterBatch`**
- `batch_id`: `UUIDField(unique=True)`, the folder name
- `sender`: `ForeignKey(RouterSender, on_delete=PROTECT)`
- `study_instance_uid`: `CharField(max_length=64)`
- `number_of_images`: `PositiveIntegerField()`
- `closed_at`: `DateTimeField(auto_now_add=True)`
- `files_deleted_at`: `DateTimeField(null=True, blank=True)`

Only batches that matched a rule get a row.

**`RouterJob(TransferJob)`**
- `rule`: `ForeignKey(RoutingRule, on_delete=PROTECT)`, so a rule with jobs can't be deleted, only
  disabled
- `batch`: `ForeignKey(RouterBatch, on_delete=PROTECT)`
- `UniqueConstraint(fields=["rule", "batch"])`
- `default_priority = settings.ROUTER_DEFAULT_PRIORITY`,
  `urgent_priority = settings.ROUTER_URGENT_PRIORITY`
- Created with `status=PENDING` and `send_finished_mail=False`; `trial_protocol_id` and
  `trial_protocol_name` are copied from the rule

**`RouterTask(TransferTask)`**
- `job`: `ForeignKey(RouterJob, on_delete=CASCADE, related_name="tasks")`
- `sent_instance_uids`: `ArrayField(CharField(max_length=64), blank=True, default=list)`
- an index on `study_uid` for the "already sent" lookup
- the inherited fields are set as in §3.2

**`RouterSettings(DicomAppSettings)`**: the standard per-app settings row, created in `init_db`
like `MassTransferSettings`. Its `suspended` flag pauses intake (§3.1); deliveries continue.

### 5.2 Rule editing

- `pseudonymize` and `pseudonym_salt` become read-only once the rule has a job, because changing
  them would break "same patient, same pseudonym". Staff create a new rule instead.
- The other fields stay editable and apply to batches decided afterwards. Existing jobs keep their
  copied destination and trial protocol.
- Switching pseudonymization off requires the existing `can_transfer_unpseudonymized` permission.

## 6. Staff pages

All router views require `is_staff`. The main menu gets a "Router" item with `staff_only=True`
(`MainMenuItem` in adit-radis-shared supports it).

| Page | Content | Actions |
|---|---|---|
| Rules (menu target) | every rule: name, on/off, destination, pseudonymizes, deliveries by status, last match | new rule |
| Rule form | name, enabled, destination, filters in the mass transfer CodeMirror editor with its help, pseudonymize and salt (read-only after the first match), trial protocol ID (the help explains that XNAT uses it as the project ID) and name | save |
| Rule detail | the rule's settings and a table of its jobs: closed at, patient ID, pseudonym, study, images sent, status; filterable by status | edit, enable/disable, retry failed deliveries (resets the failed tasks whose batch still has its folder) |
| Router jobs | all router jobs, filterable by rule and status | none |
| Job and task detail | the generic views from `adit/core/views.py` | Cancel, Retry, Restart, Reset and Kill. No Verify (jobs start `PENDING`) and no Delete (Cancel keeps the history). Retry, Restart and Reset are refused once the batch folder is deleted |

- `RouterSender`, `RoutingRule` and `RouterBatch` (read-only) are registered in the Django admin.
  Senders are managed only there, next to the DICOM servers.
- A job stats collector (`adit/core/site.py`) adds router jobs to the Admin Section's job overview.
- The rule form gets an in-app help template like the other apps' `_*_help.html`.

## 7. Configuration and deployment

**Settings** in `adit/settings/base.py`, overridable by env:

| Setting | Default | Meaning |
|---|---|---|
| `ROUTER_AE_TITLE` | empty (router disabled) | the router's own AE title, different from `RECEIVER_AE_TITLE` |
| `ROUTER_SCP_PORT` | 11112 | the port inside the router container |
| `ROUTER_SPOOL_PATH` | `/spool` | the spool path inside the containers |
| `ROUTER_QUIET_PERIOD_SECONDS` | 300 | a study closes after this long without a new image |
| `ROUTER_MAX_OPEN_SECONDS` | 3600 | and at the latest this long after its first image |
| `ROUTER_CLOSE_CRON` | `* * * * *` | the schedule of `close_router_batches` |
| `ROUTER_SENDER_REFRESH_SECONDS` | 30 | how often the router reloads senders and the suspended flag |
| `ROUTER_SPOOL_MIN_FREE_GB` | 20 | below this, images are refused and the admins are mailed |
| `ROUTER_LOW_SPACE_MAIL_HOURS` | 6 | at most one low-space mail per this many hours |
| `ROUTER_FAILED_RETENTION_DAYS` | 7 | how long a batch with a failed delivery is kept |
| `ROUTER_QUARANTINE_RETENTION_DAYS` | 7 | how long unreadable files are kept |
| `ROUTER_SENT_LIST_RETENTION_DAYS` | 30 | how long `sent_instance_uids` are kept |
| `ROUTER_PROCESS_TIMEOUT` | 3600 | pebble process timeout of a delivery, in seconds |
| `ROUTER_DEFAULT_PRIORITY` / `ROUTER_URGENT_PRIORITY` | 3 / 7 | between batch transfers (2/6) and selective transfers (4/8) |

**Compose**
- `docker-compose.base.yml`: a `router` service (`<<: *default-app`, hostname `router.local`) and
  the spool mount `${ROUTER_SPOOL_DIR:-router_spool}:/spool` on `router`, `default_worker` and
  `dicom_worker`. `router_spool` is declared as a named volume and is used unless
  `ROUTER_SPOOL_DIR` names a host folder.
- `docker-compose.dev.yml`: `router` publishes `11123:11112` and runs
  `./manage.py router --autoreload`.
- `docker-compose.prod.yml`: `router` publishes `${ROUTER_PORT:-11113}:11112`, runs
  `./manage.py router`, one replica.
- Like `MOUNT_DIR`, the shared spool assumes those containers run on one host or on a shared
  network filesystem.

**Test servers and example data**
- `orthanc/orthanc1.json` and `orthanc/orthanc2.json` list the router as a modality,
  `"ROUTER": ["ADIT1DEVROUTER", "router", 11112]` (see #406).
- `example.env` sets `ROUTER_AE_TITLE=ADIT1DEVROUTER`.
- `populate_example_data` registers Orthanc 1 as a sender and adds a disabled example rule (CT to
  Orthanc 2).

**Docs**
- `docs/user-docs/admin-guide.md` gets a "DICOM Router" section covering:
  - PACS forwarding set-up, keeping the forwarding filter as narrow as the rules allow (for example
    CT only);
  - registering senders and writing rules;
  - the XNAT project via the trial protocol ID;
  - leaving out PR or SR series with exclude filters, since `EXCLUDE_MODALITIES` does not apply;
  - backfill with mass transfer: the same filters and salt give the same selection, pseudonyms and
    UIDs;
  - how long data stays in the spool;
  - security: only the PACS network may reach the router port, AE titles are not authentication,
    and the spool belongs on an encrypted disk.
- `docs/user-docs/features.md` lists the router.
- `CLAUDE.md` describes the app, the `router` service, the env vars and the `router` command.
- Each stage updates `CLAUDE.md` and the env var docs for what it adds; stage 4 adds the
  user-facing router docs.

## 8. Races and failure handling

| Situation | Behaviour |
|---|---|
| Unknown calling AE title, or no enabled sender | association rejected |
| Spool below `ROUTER_SPOOL_MIN_FREE_GB`, or router suspended | each C-STORE answered with `0xA700`; the PACS retries later; low space mails the admins |
| An image is moved in while its folder is being closed | the replace either lands before the rename (part of the batch) or fails with `FileNotFoundError` and is retried into a new folder (the next batch) |
| A study keeps trickling in | closed after `ROUTER_MAX_OPEN_SECONDS`; the rest becomes a late batch |
| Unreadable file | moved to `quarantine/`, logged, left out of the batch |
| Crash between closing and deciding | the batch folder has no row and is decided on the next run |
| Two closing runs decide the same folder | the unique constraints let one win; the other logs and skips |
| Router crashes while writing an image | no success was sent, so the PACS resends; `tmp/` is cleaned at start |
| Worker crashes during a delivery | the stale task sweep covers every `DicomTask` subclass (`dicom_task_models()`, `adit/core/utils/recovery.py:37`) and runs the task again; C-STORE is idempotent at the destination |
| Destination down or rejecting images | retried like other DICOM tasks, then `FAILURE`; the batch stays for `ROUTER_FAILED_RETENTION_DAYS`; daily mail; staff retry from the rule page |
| The PACS forwards the same images again | images already in `sent_instance_uids` for the rule, study and destination are left out |
| A task is reset after its batch folder was deleted | the processor fails with "images deleted; forward the study again" |

## 9. Accepted risks

- An AE title is not authentication. Protection is at the network level (§7 docs).
- A study whose images pause longer than the quiet period is sent in several batches, and
  destinations see the later ones as additions. XNAT merges them automatically only in projects
  that archive automatically.
- Conditions are evaluated per batch. A late batch can be judged differently from the first when
  a condition depends on images the late batch lacks: `institution_name` with
  `apply_institution_on_study`, and `min_number_of_series_related_instances`, which counts only the
  batch's images of a series.
- Two batches of one study delivered at the same time can both send an image the PACS forwarded
  twice; the destination receives a duplicate.
- After `ROUTER_SENT_LIST_RETENTION_DAYS`, images the PACS forwards again are sent again.
- Studies that close while a rule is disabled are not sent for that rule, and their images are
  gone.
- Changing a rule's trial protocol ID affects only images sent afterwards. Images already sent are
  not sent again to the new XNAT project.
- A delivery that fails half-way leaves the accepted images at the destination until a retry
  completes it.
- A changed Patient ID (for example after a patient merge in the PACS) gives a different pseudonym,
  and so a different XNAT subject.

## 10. Build stages

One pull request each, stacked: stage 1 is based on main and every later stage on the one
before it.

1. **Filters into core.** Move `FilterSpec`, `FilterSchema`, `DiscoveredSeries`, `_dicom_match`,
   `_age_at_study`, `_series_matches_filter` and the study-level checks of `_discover_study_series`
   into `adit/core/utils/series_filters.py`, and the deterministic pseudonym helper (salt + Patient
   ID, `_DETERMINISTIC_PSEUDONYM_LENGTH`) into `adit/core/utils/pseudonymizer.py`. Mass transfer
   imports them from there. A pure refactor. #374 doesn't touch the moved code; whichever of the
   two merges second resolves a small conflict in the imports and the pseudonym code.
2. **Router inbox.** The `adit/router` app with `RouterSender` and `RouterSettings`, the `StoreScp`
   additions, the `router` command and spool writer, and the compose, env and Orthanc config
   changes. With no sender registered it refuses everything.
3. **Rules and delivery.** `RoutingRule`, `RouterBatch`, `RouterJob`, `RouterTask`,
   `close_router_batches`, `RouterTaskProcessor`, clean-up, retention, `report_router_failures`
   and the Django admin registrations. Everything is configured through the Django admin at this
   stage.
4. **Staff pages and docs.** §6 and the user docs in §7.

## 11. Follow-ups (out of scope)

- Rule preview: list the studies on a sender PACS that a rule would have matched over the last N
  days, without sending anything. It would reuse the mass transfer discovery code.
- A spool status line on the rules page: free space, open studies, batches waiting.
- A completeness check before closing: C-FIND the sending PACS for each series' instance count and
  keep waiting while the batch holds fewer.
- Instance Availability Notification as a second way in (the PACS notifies, ADIT pulls only the
  matches) for PACS that support it.
- Users create rules and staff approve them (the rule already records its creator).
- Rules limited to particular senders; folder and NIfTI destinations.

## 12. Testing

- **Unit tests** for the spool and the pure functions:
  - the spool writer, including the rename race;
  - closing by quiet period and by maximum open time;
  - deciding folders without a row;
  - rule selection: include and exclude filters, whole study, missing birth date, PR and SR series
    sent when the filters select them;
  - "already sent" filtering;
  - clean-up and retention decisions.
- **Listener tests** with fake pynetdicom events, in the style of
  `adit/core/tests/utils/test_store_scp.py`:
  - unknown senders and an empty sender list are rejected;
  - `0xA700` when suspended or low on space;
  - invalid UIDs are refused;
  - success only after the file is in its study folder.
- **Model and form tests:**
  - the unique constraints;
  - a rule with jobs can't be deleted;
  - salt and pseudonymize are read-only after the first match;
  - switching pseudonymization off needs the permission.
- **Processor tests:**
  - two batches of one study with the same salt produce the same pseudonym and replacement UIDs;
  - Patient Comments carries the XNAT text;
  - a batch whose folder was deleted fails with the clear message.
- **End-to-end test** (`@pytest.mark.acceptance`, with the Orthanc test servers):
  - the test starts a router listener, registers it on Orthanc 1 through the Orthanc REST API, and
    has Orthanc 1 send a study;
  - it runs `close_router_batches` and then a worker once (`run_worker_once`);
  - the study arrives in Orthanc 2, pseudonymized and carrying the XNAT text;
  - a study that matches no rule never arrives, and its folder is gone.
