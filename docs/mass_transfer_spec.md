# Mass Transfer — Branch Specification

## What Is It?

Mass Transfer is a new ADIT module that bulk-exports DICOM data from a PACS
server to a network folder. It targets research use cases where you need to
pull large cohorts — e.g. "all CT head scans from Neuroradiologie in 2024" —
pseudonymize them, and optionally convert to NIfTI.

```
┌──────────┐    C-FIND     ┌──────────┐    C-GET      ┌──────────────────┐
│   ADIT   │──────────────>│   PACS   │──────────────>│  Network Folder  │
│  Worker  │   discover    │  Server  │   fetch +     │  /mnt/data/...   │
│          │   studies &   │          │   pseudonymize│                  │
│          │   series      │          │   + write     │  PartitionKey/   │
│          │               │          │               │    Subject/      │
│          │               │          │               │      Study/      │
│          │               │          │               │        Series/   │
└──────────┘               └──────────┘               └──────────────────┘
```

---

## Core Concepts

### Job, Task, Volume

```
MassTransferJob                    (one per user request)
 ├── source: PACS Server
 ├── destination: Network Folder
 ├── date range: 2025-01-01 → 2025-06-30
 ├── granularity: weekly
 ├── anonymization_mode: pseudonymize_with_linking
 ├── filters: [CT + Neuroradiologie, MR + Neuroradiologie]
 ├── pseudonym_salt: "a7f3..."  (random per job, used for linking)
 │
 ├── MassTransferTask              (one per time partition)
 │    ├── partition_key: "20250101-20250107"
 │    ├── partition_start / partition_end
 │    │
 │    ├── MassTransferVolume       (one per exported series)
 │    │    ├── patient_id, pseudonym
 │    │    ├── study/series UIDs
 │    │    ├── status: exported | converted | skipped | error
 │    │    └── log (error reason if failed)
 │    └── ...
 └── ...
```

### Filters

Reusable, user-owned filter presets. A job references one or more filters.
Each filter can specify:

| Field              | Example            | Notes                    |
| ------------------ | ------------------ | ------------------------ |
| modality           | `CT`               | Exact match              |
| institution_name   | `Neuroradiologie*` | DICOM wildcard supported |
| study_description  | `*Schädel*`        | DICOM wildcard supported |
| series_description | `Axial*`           | DICOM wildcard supported |
| series_number      | `2`                | Exact integer match      |

Institution can be checked at study level (one C-FIND per study to check any
series) or at series level (checked per series during enumeration).

### Partitioning

The date range is split into non-overlapping time windows:

```
Job: 2025-01-01 → 2025-01-21, granularity=weekly

Task 1: 2025-01-01 → 2025-01-07  key="20250101-20250107"
Task 2: 2025-01-08 → 2025-01-14  key="20250108-20250114"
Task 3: 2025-01-15 → 2025-01-21  key="20250115-20250121"
```

Each task is an independent Procrastinate job. Tasks can run in parallel
across workers, but each task is guaranteed to run on exactly one worker
(`FOR UPDATE SKIP LOCKED`).

---

## Processing Pipeline

One task = one partition. Here is the full flow inside `MassTransferTaskProcessor.process()`:

```
                          ┌─────────────────────┐
                          │   Start task        │
                          │   (one partition)   │
                          └──────────┬──────────┘
                                     │
                          ┌──────────▼────────────┐
                          │  Check: suspended?     │──Yes──> return WARNING
                          │  Check: source/dest?   │──Bad──> raise DicomError
                          │  Check: filters?       │──None─> return FAILURE
                          └──────────┬────────────┘
                                     │
                    ┌────────────────▼─────────────────┐
                    │  Phase 1: DISCOVER               │
                    │                                  │
                    │  For each filter:                │
                    │    C-FIND studies in time window │
                    │    For each study:               │
                    │      C-FIND series               │
                    │      Apply modality/desc/inst    │
                    │      filters on each series      │
                    │                                  │
                    │  Result: list[DiscoveredSeries]  │
                    │  (in-memory, no DB writes)       │
                    └────────────────┬─────────────────┘
                                     │
                    ┌────────────────▼─────────────────┐
                    │  Resumability check              │
                    │                                  │
                    │  done_uids = DB volumes with     │
                    │    status in (EXPORTED, CONVERTED, │
                    │    SKIPPED)                      │
                    │  Delete any ERROR volumes (retry │
                    │  pending = discovered - done_uid │
                    └────────────────┬─────────────────┘
                                     │
                    ┌────────────────▼─────────────────┐
                    │  Group by patient_id             │
                    │  Compute subject_id (pseudonym   │
                    │  or raw patient_id)              │
                    └────────────────┬─────────────────┘
                                     │
                          ┌──────────▼────────────┐
                          │  For each series:      │
                          │                        │
             ┌────────────┤  DICOM export path?    │
             │            │  NIfTI conversion?     │
             │            └──────────┬─────────────┘
             │                       │
      ┌──────▼───────┐    ┌─────────▼──────────┐
      │ DICOM only   │    │ NIfTI mode         │
      │              │    │                    │
      │ C-GET series │    │ C-GET to temp dir  │
      │ pseudonymize │    │ pseudonymize       │
      │ write .dcm   │    │ dcm2niix → .nii.gz │
      │ to final dir │    │ write to final dir │
      │              │    │ temp dir auto-     │
      │              │    │ cleaned            │
      └──────┬───────┘    └─────────┬──────────┘
             │                      │
             └──────────┬───────────┘
                        │
             ┌──────────▼────────────┐
             │  Create DB volume     │
             │  (deferred insertion) │
             │  status = EXPORTED    │
             │         | CONVERTED   │
             │         | SKIPPED     │
             │         | ERROR       │
             └──────────┬────────────┘
                        │
             ┌──────────▼────────────┐
             │  Next series...       │
             │  (RetriableDicomError │
             │   re-raised for       │
             │   Procrastinate retry)│
             └──────────┬────────────┘
                        │
             ┌──────────▼────────────┐
             │  Return task result   │
             │  SUCCESS / WARNING /  │
             │  FAILURE + summary    │
             └───────────────────────┘
```

### Output Folder Structure

```
/mnt/data/mass_transfer_exports/
└── 20250101-20250107/                    # partition key
    ├── A7B3X9K2M1Q4/                     # pseudonym (or raw PatientID)
    │   ├── CT_Schaedel_20250103_f2a1/    # StudyDescription_Date_ShortHash
    │   │   ├── Axial_1/                  # SeriesDescription_SeriesNumber
    │   │   │   ├── 1.2.3.4.5.6.7.dcm
    │   │   │   ├── 1.2.3.4.5.6.8.dcm
    │   │   │   └── ...
    │   │   └── Sagittal_2/
    │   │       └── ...
    │   └── MRT_Kopf_20250105_b8c2/
    │       └── T1_1/
    │           └── ...
    └── R4T7Y2W8N3P1/
        └── ...
```

The study folder name includes a 4-char hash of the StudyInstanceUID to
prevent collisions when the same patient has multiple studies with the same
description on the same date.

---

## Anonymization Modes

| Mode                          | Folder name                      | DICOM tags         | Cross-partition consistency                   | CSV export                    |
| ----------------------------- | -------------------------------- | ------------------ | --------------------------------------------- | ----------------------------- |
| **None**                      | Raw PatientID                    | Untouched          | N/A                                           | Not available |
| **Pseudonymize**              | Random hex per study             | dicognito (random) | No — each study gets a unique random folder   | Not available |
| **Pseudonymize with Linking** | Deterministic pseudonym          | dicognito (seeded) | Yes — same patient always gets same pseudonym | patient_id → pseudonym pairs  |

### How Linking Works

```
job.pseudonym_salt = "a7f3e2..."     # random, generated once per job

                    ┌──────────────────────────┐
                    │  Pseudonymizer(seed=salt)│
                    │                          │
  "PATIENT_12345" ──┤  md5(salt + patient_id)  ├──> "A7B3X9K2M1Q4"
                    │  → deterministic 12-char │
                    └──────────────────────────┘

Same salt + same patient_id = same pseudonym, always.
No lookup table needed. Works across partitions.
Uses dicognito's Randomizer internally.
```

In non-linking mode, each study gets a fresh `secrets.token_hex(6)` — even
two studies from the same patient land in separate opaque folders, so there
is no way to correlate which studies belong to the same person.

---

## Adaptive Study Discovery (recursive split)

PACS servers often limit C-FIND results (e.g. 200 max). When a query returns
more results than the limit, the time window is recursively bisected:

```
Query: 2025-01-01 → 2025-01-07, limit=200
  → 250 results (over limit!)
  → Split:
      Left:  2025-01-01 → 2025-01-04  → 120 results (ok)
      Right: 2025-01-05 → 2025-01-07  → 140 results (ok)
  → Merge + deduplicate by StudyInstanceUID
  → 245 unique studies
```

Recursion stops with an error if the window is smaller than 30 minutes
(safety valve against infinite recursion on a PACS that always returns
too many results).

---

## Persistent DIMSE Connections

DICOM network operations (C-FIND, C-GET) require a TCP association with
specific presentation contexts. By default, ADIT opens and closes an
association per operation.

For mass transfer with hundreds of series, this is wasteful (~500ms overhead
per association). The `persistent=True` mode keeps the association open:

```
Default mode (persistent=False):
  open → C-FIND study 1 → close
  open → C-FIND study 2 → close
  open → C-FIND study 3 → close
  open → C-GET series 1 → close
  open → C-GET series 2 → close
  ...
  ~700 associations for 100 studies × ~500ms = ~350s overhead

Persistent mode (persistent=True):
  open(C-FIND) → C-FIND study 1 → study 2 → study 3 → ...
  close(C-FIND)
  open(C-GET) → C-GET series 1 → series 2 → ...
  close(C-GET)
  2-3 associations total × ~500ms = ~1s overhead
```

Service-type switching (C-FIND → C-GET) automatically closes and reopens
with the correct presentation contexts. After an abort (e.g. `limit_results`
in C-FIND), the next call auto-reconnects.

Only mass transfer opts in. All existing code is unchanged (`persistent=False`
is the default).

---

## Deferred Volume Insertion

Volumes (DB records tracking each exported series) are only created **after**
successful export or conversion — not during discovery.

```
Old approach:
  discover → create PENDING volumes in DB → export → update to EXPORTED
  Problem: failed exports leave orphan PENDING records

New approach:
  discover → in-memory DiscoveredSeries list → export → create EXPORTED volume
  No orphans. Resumability via: "skip series whose UID is already in DB"
```

On retry, ERROR volumes from prior runs are deleted first, then reprocessed.
This avoids UniqueConstraint violations on `(job, series_instance_uid)`.

---

## Error Handling

| Error type                                              | Behavior                                                |
| ------------------------------------------------------- | ------------------------------------------------------- |
| `RetriableDicomError` (PACS timeout, connection lost)   | Re-raised → Procrastinate retries the whole task        |
| `DicomError` / other exceptions (single series)         | Caught → ERROR volume created → continue to next series |
| All series fail                                         | Task status = FAILURE                                   |
| Some series fail                                        | Task status = WARNING, message shows count              |
| Non-image DICOM (dcm2niix says "No valid DICOM images") | SKIPPED volume, no error                                |

Task detail page shows a table of all skipped and failed volumes with the
specific error reason for each.

---

## Infrastructure Changes

### Dedicated Worker

Mass transfer runs on its own Procrastinate worker (`mass_transfer_worker`)
listening on the `mass_transfer` queue. This prevents long-running bulk
exports from blocking the normal DICOM transfer queue.

### Mount Propagation

Containers use `rslave` mount propagation so that NAS mounts made on the host
(e.g. `/mnt/nfs/ccinas01/adit`) are visible inside the container without
restart.

### Job Cancellation

In-progress tasks can be cancelled. The DIMSE connection leak fix ensures
that abandoned C-GET generators properly close their associations (via
`finally` blocks in the `connect_to_server` decorator).

---

## Design Decisions

1. **Partition-per-task, not study-per-task.**
   One Procrastinate job per time window, not per study. Reduces job queue
   overhead from thousands to dozens. Each task discovers and exports
   everything in its window.

2. **Filters are reusable objects, not inline fields.**
   Users define filters once ("CT Neuroradiologie") and attach them to
   multiple jobs. Filters support DICOM wildcards for fuzzy matching.

3. **Deferred insertion over eager insertion.**
   DB records only exist for successfully processed series. No cleanup
   needed for partial failures. Resumability works by checking existing UIDs.

4. **dicognito for pseudonymization, not a custom implementation.**
   dicognito handles UIDs, dates, names, and all DICOM-specific anonymization
   rules. We only add a seed parameter for deterministic (linking) mode.

5. **Folder pseudonyms computed independently from DICOM pseudonyms.**
   The folder name uses `compute_pseudonym()` (12-char alphanumeric from
   the seed) while DICOM tags are pseudonymized by dicognito's full pipeline.
   This means the folder name is stable and predictable while the internal
   DICOM data gets proper anonymization.

6. **Temp directories for NIfTI conversion.**
   DICOM files are exported to a `tempfile.TemporaryDirectory()`, converted
   with `dcm2niix`, and the temp dir is auto-cleaned. No persistent staging
   area needed.

7. **Persistent connections opt-in only.**
   `persistent=False` is the default. Only mass transfer enables it. No
   risk to existing transfer modules.

---

## Files Added/Modified

### New: `adit/mass_transfer/` (entire app — 39 files)

| File                  | Purpose                                               |
| --------------------- | ----------------------------------------------------- |
| `models.py`           | Job, Task, Volume, Filter, Settings models            |
| `processors.py`       | Discovery, export, NIfTI conversion, pseudonymization |
| `forms.py`            | Job creation form with dynamic filter selection       |
| `views.py`            | CRUD views + CSV associations export                  |
| `urls.py`             | 18 URL patterns                                       |
| `utils/partitions.py` | Date range → partition windows                        |
| `apps.py`             | App registration, menu item, processor registration   |
| `templates/`          | Job form, job detail, task detail, filter CRUD        |
| `tests/`              | 44 tests (processor, partitions, cleanup)             |

### Modified: `adit/core/`

| File                       | Change                                                       |
| -------------------------- | ------------------------------------------------------------ |
| `utils/dimse_connector.py` | `persistent` mode, service-type tracking, generator leak fix |
| `utils/dicom_operator.py`  | Pass-through `persistent` param, `close()` method            |
| `utils/pseudonymizer.py`   | `seed` parameter, `compute_pseudonym()` method               |

### Modified: Infrastructure

| File                    | Change                                                  |
| ----------------------- | ------------------------------------------------------- |
| `docker-compose.*.yml`  | `mass_transfer_worker` service, `rslave` propagation    |
| `adit/settings/base.py` | Mass transfer settings (priorities, max search results) |

---

## Test Coverage

44 tests covering:

- **Discovery**: recursive time-window splitting, deduplication, boundary correctness
- **Processing**: success, partial failure, total failure, suspension, bad source/dest, no filters, empty partition
- **Resumability**: skipping already-done series, deleting ERROR volumes on retry
- **Pseudonymization**: within-task consistency, cross-partition linking, cross-partition non-linking, no-anonymization mode
- **NIfTI conversion**: dcm2niix failure, no output, non-image DICOM skip
- **Utilities**: folder name generation, DICOM wildcard matching, integer parsing, datetime handling
- **Cleanup**: no-op verification (deferred insertion means nothing to clean up)

Run with:

```bash
DJANGO_SETTINGS_MODULE=adit.settings.development \
  python -m pytest adit/mass_transfer/tests/ -v
```
