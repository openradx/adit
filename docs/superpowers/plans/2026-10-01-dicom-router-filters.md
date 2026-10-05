# DICOM Router Filters into Core (Stage 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move mass transfer's series filters and its deterministic pseudonym into
`adit/core/`, so the DICOM router (stages 2–4) can select series and pseudonymize exactly as
mass transfer does.

**Architecture:** This is a pure refactor.
- **New module `adit/core/utils/series_filters.py`** holds `FilterSchema`, `FilterSpec`,
  `DiscoveredSeries`, `dicom_match`, `age_at_study` and `series_matches_filter`, moved verbatim
  and made public.
- **New function `study_matches_filter`** is the study-level check that today lives inside
  `MassTransferTaskProcessor._discover_study_series`. The institution lookup is passed in as a
  callback, because mass transfer needs a C-FIND for it and the router does not.
- **`adit/core/utils/pseudonymizer.py`** gains the pseudonym lengths and
  `deterministic_pseudonym(salt, patient_id)`.
- **Mass transfer** imports everything from core, and its behaviour does not change.

**Tech Stack:** Django 6.1, pydantic, pydicom 3.0, pytest with pytest-django.

**Spec:** `docs/superpowers/specs/2026-09-30-dicom-router-design.md`, stage 1 of §10 and §4.
This is the first PR of a stack based on main. Stage 2 (`2026-10-01-dicom-router-inbox.md`)
stacks on this branch.

## Global Constraints

- **Pure refactor.** Mass transfer must select the same series and produce the same pseudonyms
  as before. Every existing mass transfer test passes unchanged, apart from its imports and the
  renamed function names.
- **Code style:** Google Python style, ruff line length 100, pyright in basic mode.
  - Comments only where the code can't speak for itself, and they explain why.
  - No history in comments or docstrings.
- **Invariants:** use `assert` for internal invariants.
- **Public names in core:** `FilterSchema`, `FilterSpec`, `DiscoveredSeries`, `dicom_match`,
  `age_at_study`, `series_matches_filter`, `study_matches_filter`,
  `DETERMINISTIC_PSEUDONYM_LENGTH` (14), `RANDOM_PSEUDONYM_LENGTH` (15) and
  `deterministic_pseudonym`.
- **Branch:** `feat/dicom-router-filters`, based on main. It holds the spec commits.
  - Before Task 1, run `git branch -m feat/dicom-router feat/dicom-router-filters` if the
    branch still has its old name.
  - #374 changes other parts of `adit/mass_transfer/processors.py` and
    `adit/mass_transfer/tests/test_processor.py`. To keep its rebase small, leave the tests
    where they are: change only their imports and the renamed calls.
- **Running tests and lint:**
  - Tests run in the web container. Start the dev stack with `uv run cli compose-up -- --watch`,
    then run `uv run cli test -- <paths>`.
  - Lint runs on the host with `uv run cli lint`.
- **Commits:** every commit message ends with the attribution trailer lines that the executing
  session's harness requires.

## Review Focus

1. **Study-level checks stay lazy.** The study-level checks still read `StudyDescription` and
   `ModalitiesInStudy` only when the filter uses them. `ResultDataset` raises for missing
   attributes, so reading them eagerly would crash on studies a PACS returns without those
   keys. Covered by Task 1, `test_study_fields_are_only_read_when_the_filter_uses_them`.
2. **Institution lookup only when needed.** The C-FIND for the institution only runs when the
   filter needs it and the earlier checks passed. Covered by Task 1,
   `test_institution_is_only_looked_up_when_filtered_on_study_level` and
   `test_institution_is_not_looked_up_when_an_earlier_check_fails`.
3. **Pseudonyms unchanged.** Mass transfer's deterministic pseudonyms stay byte-for-byte the
   same. Covered by Task 1, `test_deterministic_pseudonym_matches_compute_pseudonym`, and the
   existing mass transfer tests that compare against `compute_pseudonym(...,
   length=DETERMINISTIC_PSEUDONYM_LENGTH)`.
4. **Unknown birth dates.** A study without a birth date still passes the study check and is
   left to `series_matches_filter`, which drops it for include filters with age bounds. Covered
   by Task 1, `test_unknown_birth_date_is_left_to_the_series_check`.
5. **No import cycle.** `adit.mass_transfer.models` now imports the core module at load time.
   Covered by Task 2, Step 5: Django starts and `makemigrations --check` passes.

---

## File Structure

| File | Responsibility |
|---|---|
| `adit/core/utils/series_filters.py` (create) | filter schema and spec, discovered series, matching functions |
| `adit/core/utils/pseudonymizer.py` (modify) | pseudonym lengths and `deterministic_pseudonym` |
| `adit/mass_transfer/processors.py` (modify) | uses the core filters and pseudonym; old definitions removed |
| `adit/mass_transfer/forms.py` (modify) | imports `FilterSchema` from core |
| `adit/mass_transfer/models.py` (modify) | imports `FilterSpec` from core |
| `adit/core/tests/utils/test_series_filters.py` (create) | tests of `study_matches_filter` |
| `adit/core/tests/utils/test_pseudonymizer.py` (modify) | test of `deterministic_pseudonym` |
| `adit/mass_transfer/tests/test_processor.py` (modify) | imports and renamed calls only |
| `CLAUDE.md` (modify) | where the filters live |

---

### Task 1: Core filters module and deterministic pseudonym

**Files:**
- Create: `adit/core/utils/series_filters.py`
- Modify: `adit/core/utils/pseudonymizer.py` (after the imports, and after `compute_pseudonym`)
- Test: `adit/core/tests/utils/test_series_filters.py` (create)
- Test: `adit/core/tests/utils/test_pseudonymizer.py` (append; extend the import)

**Interfaces:**
- Consumes: `adit.core.errors.DicomError`, `adit.core.utils.dicom_utils.convert_to_python_regex`,
  `adit.core.utils.dicom_dataset.ResultDataset` and
  `adit.core.utils.pseudonymizer.compute_pseudonym`.
- Produces, in `adit/core/utils/series_filters.py`:
  - `FilterSchema`, a pydantic model.
  - `FilterSpec`, a frozen dataclass, with `FilterSpec.from_dict(d: dict) -> FilterSpec`.
  - `DiscoveredSeries`, a frozen dataclass.
  - `dicom_match(pattern: str, value: str | None, case_insensitive: bool = False) -> bool`
  - `age_at_study(birth_date: date, study_date: date) -> int`
  - `series_matches_filter(series: DiscoveredSeries, mf: FilterSpec, check_institution: bool = True, age_permissive: bool = False) -> bool`
  - `study_matches_filter(mf: FilterSpec, study: ResultDataset, has_institution: Callable[[str], bool]) -> bool`
- Produces, in `adit/core/utils/pseudonymizer.py`:
  - `DETERMINISTIC_PSEUDONYM_LENGTH = 14`, `RANDOM_PSEUDONYM_LENGTH = 15`
  - `deterministic_pseudonym(salt: str, patient_id: str) -> str`

- [ ] **Step 1: Write the failing tests for `study_matches_filter`**

Create `adit/core/tests/utils/test_series_filters.py`:

```python
from typing import cast

from pydicom import Dataset

from adit.core.utils.dicom_dataset import ResultDataset
from adit.core.utils.series_filters import FilterSpec, study_matches_filter


def _study(**values) -> ResultDataset:
    ds = Dataset()
    ds.ModalitiesInStudy = values.get("modalities", ["CT"])
    ds.StudyDescription = values.get("description", "CT Kopf nativ")
    ds.StudyDate = values.get("study_date", "20240601")
    if "birth_date" in values:
        ds.PatientBirthDate = values["birth_date"]
    return ResultDataset(ds)


def _no_institution_lookup(name: str) -> bool:
    raise AssertionError("the institution must not be looked up here")


def test_study_without_the_filtered_modality_does_not_match():
    assert not study_matches_filter(FilterSpec(modality="MR"), _study(), _no_institution_lookup)


def test_study_description_must_match():
    mf = FilterSpec(study_description="CT*")

    assert study_matches_filter(mf, _study(), _no_institution_lookup)
    assert not study_matches_filter(mf, _study(description="MR Knie"), _no_institution_lookup)


class _StudyWithoutKeys:
    """Raises like ResultDataset does when a PACS omits these keys."""

    @property
    def ModalitiesInStudy(self):
        raise AttributeError("ModalitiesInStudy")

    @property
    def StudyDescription(self):
        raise AttributeError("StudyDescription")


def test_study_fields_are_only_read_when_the_filter_uses_them():
    study = cast(ResultDataset, _StudyWithoutKeys())

    assert study_matches_filter(FilterSpec(), study, _no_institution_lookup)


def test_institution_is_only_looked_up_when_filtered_on_study_level():
    looked_up: list[str] = []

    def lookup(name: str) -> bool:
        looked_up.append(name)
        return False

    assert not study_matches_filter(FilterSpec(institution_name="Uni*"), _study(), lookup)
    assert looked_up == ["Uni*"]

    looked_up.clear()
    mf = FilterSpec(institution_name="Uni*", apply_institution_on_study=False)
    assert study_matches_filter(mf, _study(), lookup)
    assert looked_up == []


def test_institution_is_not_looked_up_when_an_earlier_check_fails():
    mf = FilterSpec(modality="MR", institution_name="Uni*")

    assert not study_matches_filter(mf, _study(), _no_institution_lookup)


def test_age_bounds_use_birth_date_and_study_date():
    study = _study(birth_date="19990615", study_date="20240601")  # 24 on the study date

    assert study_matches_filter(FilterSpec(min_age=20, max_age=30), study, _no_institution_lookup)
    assert not study_matches_filter(FilterSpec(min_age=25), study, _no_institution_lookup)
    assert not study_matches_filter(FilterSpec(max_age=23), study, _no_institution_lookup)


def test_unknown_birth_date_is_left_to_the_series_check():
    assert study_matches_filter(FilterSpec(min_age=20), _study(), _no_institution_lookup)
```

- [ ] **Step 2: Write the failing test for `deterministic_pseudonym`**

In `adit/core/tests/utils/test_pseudonymizer.py`, change the import to:

```python
from adit.core.utils.pseudonymizer import (
    DETERMINISTIC_PSEUDONYM_LENGTH,
    Pseudonymizer,
    compute_pseudonym,
    deterministic_pseudonym,
)
```

and append:

```python
def test_deterministic_pseudonym_matches_compute_pseudonym():
    pseudonym = deterministic_pseudonym("salt", "PAT1")

    assert pseudonym == compute_pseudonym("salt", "PAT1", length=DETERMINISTIC_PSEUDONYM_LENGTH)
    assert len(pseudonym) == 14
    assert deterministic_pseudonym("salt", "PAT1") == pseudonym
    assert deterministic_pseudonym("other salt", "PAT1") != pseudonym
```

- [ ] **Step 3: Run the tests and confirm they fail**

Run: `uv run cli test -- adit/core/tests/utils/test_series_filters.py adit/core/tests/utils/test_pseudonymizer.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'adit.core.utils.series_filters'` and
`ImportError: cannot import name 'DETERMINISTIC_PSEUDONYM_LENGTH'`.

- [ ] **Step 4: Create `adit/core/utils/series_filters.py`**

The classes and functions below are copied from `adit/mass_transfer/processors.py` and
`adit/mass_transfer/forms.py`; only the names and two docstrings change.
`study_matches_filter` is the study-level part of
`MassTransferTaskProcessor._discover_study_series`.

```python
"""Filters that select the series of a study, shared by mass transfer and the router."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, model_validator

from ..errors import DicomError
from .dicom_dataset import ResultDataset
from .dicom_utils import convert_to_python_regex


class FilterSchema(BaseModel):
    """Pydantic model for validating filter JSON objects."""

    mode: Literal["include", "exclude"] = "include"
    modality: str = ""
    institution_name: str = ""
    apply_institution_on_study: bool = True
    study_description: str = ""
    series_description: str = ""
    series_number: int | None = None
    min_age: Annotated[int, "non-negative"] | None = None
    max_age: Annotated[int, "non-negative"] | None = None
    min_number_of_series_related_instances: int | None = None

    model_config = {"extra": "forbid"}

    @model_validator(mode="after")
    def check_age_range(self):
        if self.min_age is not None and self.min_age < 0:
            raise ValueError("min_age must be non-negative")
        if self.max_age is not None and self.max_age < 0:
            raise ValueError("max_age must be non-negative")
        if (
            self.min_number_of_series_related_instances is not None
            and self.min_number_of_series_related_instances < 1
        ):
            raise ValueError("min_number_of_series_related_instances must be >= 1")
        if self.min_age is not None and self.max_age is not None and self.min_age > self.max_age:
            raise ValueError(f"min_age ({self.min_age}) cannot exceed max_age ({self.max_age})")
        return self

    @model_validator(mode="after")
    def check_exclude_has_criteria(self):
        if self.mode != "exclude":
            return self
        has_criterion = bool(
            self.modality
            or self.institution_name
            or self.study_description
            or self.series_description
            or self.series_number is not None
            or self.min_age is not None
            or self.max_age is not None
            or self.min_number_of_series_related_instances is not None
        )
        if not has_criterion:
            raise ValueError("exclude filter must specify at least one criterion")
        return self


@dataclass(frozen=True)
class FilterSpec:
    """Unified filter representation.

    Built from one entry of a filters_json list.
    """

    mode: Literal["include", "exclude"] = "include"
    modality: str = ""
    institution_name: str = ""
    apply_institution_on_study: bool = True
    study_description: str = ""
    series_description: str = ""
    series_number: int | None = None
    min_age: int | None = None
    max_age: int | None = None
    min_number_of_series_related_instances: int | None = None

    @classmethod
    def from_dict(cls, d: dict) -> "FilterSpec":
        mode = d.get("mode", "include")
        if mode not in ("include", "exclude"):
            raise DicomError(f"Invalid filter mode: {mode!r}")
        return cls(
            mode=mode,
            modality=d.get("modality", ""),
            institution_name=d.get("institution_name", ""),
            apply_institution_on_study=d.get("apply_institution_on_study", True),
            study_description=d.get("study_description", ""),
            series_description=d.get("series_description", ""),
            series_number=d.get("series_number"),
            min_age=d.get("min_age"),
            max_age=d.get("max_age"),
            min_number_of_series_related_instances=d.get("min_number_of_series_related_instances"),
        )


@dataclass(frozen=True)
class DiscoveredSeries:
    patient_id: str
    accession_number: str
    study_instance_uid: str
    series_instance_uid: str
    modality: str
    study_description: str
    series_description: str
    series_number: int | None
    study_datetime: datetime
    institution_name: str
    number_of_images: int
    patient_birth_date: date | None = None


def dicom_match(pattern: str, value: str | None, case_insensitive: bool = False) -> bool:
    # Callers only pass non-PN fields (institution_name, study_description,
    # series_description). Include filters compare case-sensitively to stay
    # consistent with PACS-side matching of non-PN fields; exclude filters are
    # applied client-side only and pass case_insensitive=True.
    if not pattern:
        return True
    if value is None:
        return False
    regex = convert_to_python_regex(pattern, case_insensitive=case_insensitive)
    return bool(regex.fullmatch(str(value)))


def age_at_study(birth_date: date, study_date: date) -> int:
    """Return the patient's age in whole years on the study date."""
    age = study_date.year - birth_date.year
    if (study_date.month, study_date.day) < (birth_date.month, birth_date.day):
        age -= 1
    return age


def study_matches_filter(
    mf: FilterSpec, study: ResultDataset, has_institution: Callable[[str], bool]
) -> bool:
    """Test whether *study* can hold series selected by the include filter *mf*.

    Only checks what is known on study level; the series are tested afterwards with
    series_matches_filter. Study fields are read only when the filter uses them, and
    *has_institution* is only called when the filter asks for an institution on study
    level, so callers can look the institutions up lazily.
    """
    if mf.modality and mf.modality not in study.ModalitiesInStudy:
        return False

    if mf.study_description and not dicom_match(mf.study_description, study.StudyDescription):
        return False

    if mf.institution_name and mf.apply_institution_on_study:
        if not has_institution(mf.institution_name):
            return False

    # An unknown birth date passes here; series_matches_filter decides about it.
    if mf.min_age is not None or mf.max_age is not None:
        birth_date = study.PatientBirthDate
        if birth_date and study.StudyDate:
            age = age_at_study(birth_date, study.StudyDate)
            if mf.min_age is not None and age < mf.min_age:
                return False
            if mf.max_age is not None and age > mf.max_age:
                return False

    return True


def series_matches_filter(
    series: DiscoveredSeries,
    mf: FilterSpec,
    check_institution: bool = True,
    age_permissive: bool = False,
) -> bool:
    """Test whether *series* satisfies all non-empty criteria on *mf*.

    ``check_institution=False`` skips the institution check — the include
    path uses this when ``apply_institution_on_study`` has already resolved
    the check at study level.  ``age_permissive=True`` treats an unknown
    ``patient_birth_date`` as passing the age check; excludes set this so
    a series with an unverifiable age is dropped by an age-bounded exclude
    filter.  The strict default is used by include filters so that an
    unknown age also fails inclusion — in both directions, a series whose
    age can't be determined is dropped.

    String criteria on include filters are matched case-sensitively, in line
    with PACS-side matching of non-PN fields.  Exclude filters are applied
    client-side only (they never reach the PACS), so they match
    case-insensitively — scanner naming conventions vary in capitalization
    (COR/Cor/cor) and an exclude should catch all variants.
    """
    case_insensitive = mf.mode == "exclude"
    if mf.modality and mf.modality != series.modality:
        return False
    if check_institution and mf.institution_name:
        if not dicom_match(mf.institution_name, series.institution_name, case_insensitive):
            return False
    if mf.study_description and not dicom_match(
        mf.study_description, series.study_description, case_insensitive
    ):
        return False
    if mf.series_description and not dicom_match(
        mf.series_description, series.series_description, case_insensitive
    ):
        return False
    if mf.series_number is not None:
        if series.series_number is None or mf.series_number != series.series_number:
            return False
    if mf.min_age is not None or mf.max_age is not None:
        if series.patient_birth_date:
            age = age_at_study(series.patient_birth_date, series.study_datetime.date())
            if mf.min_age is not None and age < mf.min_age:
                return False
            if mf.max_age is not None and age > mf.max_age:
                return False
        elif not age_permissive:
            return False
    if mf.min_number_of_series_related_instances is not None:
        if series.number_of_images < mf.min_number_of_series_related_instances:
            return False
    return True
```

- [ ] **Step 5: Add the pseudonym lengths and `deterministic_pseudonym`**

In `adit/core/utils/pseudonymizer.py`, after the line
`_PSEUDONYM_ALPHABET = string.ascii_uppercase + string.digits  # A-Z0-9`, add:

```python

# Deterministic pseudonyms use 14 characters. Random pseudonyms use 15 so the
# two modes can be distinguished by length.
DETERMINISTIC_PSEUDONYM_LENGTH = 14
RANDOM_PSEUDONYM_LENGTH = 15
```

and directly after the `compute_pseudonym` function, add:

```python


def deterministic_pseudonym(salt: str, patient_id: str) -> str:
    """The pseudonym a patient always gets for *salt* (mass transfer, router)."""
    return compute_pseudonym(salt, patient_id, length=DETERMINISTIC_PSEUDONYM_LENGTH)
```

- [ ] **Step 6: Run the tests and confirm they pass**

Run: `uv run cli test -- adit/core/tests/utils/test_series_filters.py adit/core/tests/utils/test_pseudonymizer.py -v`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add adit/core/utils/series_filters.py adit/core/utils/pseudonymizer.py \
  adit/core/tests/utils/test_series_filters.py adit/core/tests/utils/test_pseudonymizer.py
git commit -m "Add series filters and the deterministic pseudonym to core"
```

---

### Task 2: Mass transfer uses the core filters

**Files:**
- Modify: `adit/mass_transfer/processors.py`
- Modify: `adit/mass_transfer/forms.py`
- Modify: `adit/mass_transfer/models.py`
- Modify: `adit/mass_transfer/tests/test_processor.py` (imports and renamed calls only)
- Modify: `CLAUDE.md` (the `**mass_transfer/**` entry)

**Interfaces:**
- Consumes: everything Task 1 produces.
- Produces: no new names. After this task `adit/mass_transfer/processors.py` no longer defines
  `FilterSpec`, `DiscoveredSeries`, `_dicom_match`, `_age_at_study`, `_series_matches_filter`,
  `_DETERMINISTIC_PSEUDONYM_LENGTH` or `_RANDOM_PSEUDONYM_LENGTH`, and `forms.py` no longer
  defines `FilterSchema`.

This task has no new failing test. The existing mass transfer suite is the safety net: it
covers discovery, include and exclude filters, ages and pseudonyms. It must pass unchanged once
the code and the test imports point at core. Don't run it between the steps: in between,
tests would compare old and new `DiscoveredSeries` instances, and dataclass equality fails
across the two classes.

- [ ] **Step 1: Switch `processors.py` to core and delete the old definitions**

In `adit/mass_transfer/processors.py`:

1. Change the imports:
   - Remove `from dataclasses import dataclass`.
   - Change `from typing import Literal, cast` to `from typing import cast`.
   - Change `from adit.core.utils.dicom_utils import convert_to_python_regex, write_dataset`
     to `from adit.core.utils.dicom_utils import write_dataset`.
   - Change `from adit.core.utils.pseudonymizer import Pseudonymizer, compute_pseudonym` to:

     ```python
     from adit.core.utils.series_filters import (
         DiscoveredSeries,
         FilterSpec,
         age_at_study,
         dicom_match,
         series_matches_filter,
         study_matches_filter,
     )
     from adit.core.utils.pseudonymizer import (
         RANDOM_PSEUDONYM_LENGTH,
         Pseudonymizer,
         compute_pseudonym,
         deterministic_pseudonym,
     )
     ```

2. Delete these definitions, each from its decorator or `def` line to its last line:
   - the `FilterSpec` class (`@dataclass(frozen=True)` above `class FilterSpec:`, through the
     end of `from_dict`);
   - the comment `# Deterministic pseudonyms use 14 characters. ...` and the two lines
     `_DETERMINISTIC_PSEUDONYM_LENGTH = 14` and `_RANDOM_PSEUDONYM_LENGTH = 15`;
   - the `DiscoveredSeries` class, including its `@dataclass(frozen=True)`;
   - `def _dicom_match(...)`;
   - `def _age_at_study(...)`;
   - `def _series_matches_filter(...)`.

3. Rename the remaining call sites:

   ```bash
   perl -pi -e '
     s/\b_age_at_study\(/age_at_study(/g;
     s/\b_dicom_match\(/dicom_match(/g;
     s/\b_series_matches_filter\(/series_matches_filter(/g;
   ' adit/mass_transfer/processors.py
   ```

4. In `_create_pending_volumes`, replace:

   ```python
                if pid not in deterministic_ids:
                    deterministic_ids[pid] = compute_pseudonym(
                        job.pseudonym_salt, pid, length=_DETERMINISTIC_PSEUDONYM_LENGTH
                    )
   ```

   with:

   ```python
                if pid not in deterministic_ids:
                    deterministic_ids[pid] = deterministic_pseudonym(job.pseudonym_salt, pid)
   ```

   and `length=_RANDOM_PSEUDONYM_LENGTH` with `length=RANDOM_PSEUDONYM_LENGTH`.

5. In `_discover_study_series`, replace everything from the line after the docstring down to
   (but not including) `series_query = QueryDataset.create(`. That is the modality,
   description, institution and age checks:

   ```python
        if mf.modality and mf.modality not in study.ModalitiesInStudy:
            return

        if mf.study_description and not dicom_match(mf.study_description, study.StudyDescription):
            return

        if mf.institution_name and mf.apply_institution_on_study:
            if not self._study_has_institution(operator, study, mf.institution_name):
                return

        # Exact client-side age filtering using actual StudyDate and
        # PatientBirthDate (the query birth date range is approximate).
        birth_date = study.PatientBirthDate
        has_age_filter = mf.min_age is not None or mf.max_age is not None
        if birth_date and study.StudyDate and has_age_filter:
            age = age_at_study(birth_date, study.StudyDate)
            if mf.min_age is not None and age < mf.min_age:
                return
            if mf.max_age is not None and age > mf.max_age:
                return
   ```

   with:

   ```python
        if not study_matches_filter(
            mf, study, lambda name: self._study_has_institution(operator, study, name)
        ):
            return

        birth_date = study.PatientBirthDate
   ```

   `birth_date` is still needed further down, for `DiscoveredSeries(patient_birth_date=...)`.

Check that nothing old is left:
`grep -n "class FilterSpec\|class DiscoveredSeries\|def _dicom_match\|def _age_at_study\|def _series_matches_filter\|_PSEUDONYM_LENGTH = \|convert_to_python_regex\|Literal" adit/mass_transfer/processors.py`

Expected: no output.

- [ ] **Step 2: Import `FilterSchema` and `FilterSpec` from core in the forms and models**

In `adit/mass_transfer/forms.py`:
- delete the `FilterSchema` class (from `class FilterSchema(BaseModel):` through the `return self`
  that ends `check_exclude_has_criteria`);
- change `from typing import Annotated, Literal, cast` to `from typing import cast`;
- delete `from pydantic import BaseModel, model_validator`. Keep
  `from pydantic import ValidationError as PydanticValidationError`;
- add `from adit.core.utils.series_filters import FilterSchema` after
  `from adit.core.models import DicomNode`.

In `adit/mass_transfer/models.py`:
- delete `from typing import TYPE_CHECKING` and the block
  `if TYPE_CHECKING:` / `    from .processors import FilterSpec`;
- add `from adit.core.utils.series_filters import FilterSpec` after
  `from adit.core.models import ...`;
- in `get_filters`, change the return annotation to `list[FilterSpec]` and delete the local
  `from .processors import FilterSpec` line.

- [ ] **Step 3: Point the mass transfer tests at the new names**

Run this from the repository root. It only rewrites call sites; names like
`test_dicom_match_exact` keep their old spelling, because `\b` never matches inside an
identifier:

```bash
perl -pi -e '
  s/\b_age_at_study\(/age_at_study(/g;
  s/\b_dicom_match\(/dicom_match(/g;
  s/\b_series_matches_filter\(/series_matches_filter(/g;
  s/from adit\.mass_transfer\.processors import _DETERMINISTIC_PSEUDONYM_LENGTH/from adit.core.utils.pseudonymizer import DETERMINISTIC_PSEUDONYM_LENGTH/;
  s/\b_DETERMINISTIC_PSEUDONYM_LENGTH\b/DETERMINISTIC_PSEUDONYM_LENGTH/g;
' adit/mass_transfer/tests/test_processor.py
```

Then replace the import block at the top of `adit/mass_transfer/tests/test_processor.py`:

```python
from adit.mass_transfer.processors import (
    DiscoveredSeries,
    FilterSpec,
    MassTransferTaskProcessor,
    _age_at_study,
    _birth_date_range,
    _destination_base_dir,
    _dicom_match,
    _parse_int,
    _series_folder_name,
    _series_matches_filter,
    _study_datetime,
    _study_folder_name,
)
```

with:

```python
from adit.core.utils.series_filters import (
    DiscoveredSeries,
    FilterSpec,
    age_at_study,
    dicom_match,
    series_matches_filter,
)
from adit.mass_transfer.processors import (
    MassTransferTaskProcessor,
    _birth_date_range,
    _destination_base_dir,
    _parse_int,
    _series_folder_name,
    _study_datetime,
    _study_folder_name,
)
```

Check that nothing old is left:
`grep -n "_age_at_study\|_dicom_match(\|_series_matches_filter(\|_DETERMINISTIC_PSEUDONYM_LENGTH" adit/mass_transfer/tests/test_processor.py`

Expected: no output.

- [ ] **Step 4: Update `CLAUDE.md`**

In the `**mass_transfer/**` entry, replace
`Series are discovered with JSON include/exclude filters (`FilterSpec`: modality, institution, study/series description, series number, age)`
with
`Series are discovered with JSON include/exclude filters (`FilterSpec` in `adit/core/utils/series_filters.py`, shared with the DICOM router: modality, institution, study/series description, series number, age)`.

- [ ] **Step 5: Run the affected suites, check migrations, and lint**

Run:

```bash
uv run cli test -- adit/mass_transfer adit/core/tests/utils -q
docker compose -f docker-compose.base.yml -f docker-compose.dev.yml -p adit_dev exec web ./manage.py makemigrations --check --dry-run
uv run cli lint
```

Expected:
- all tests pass;
- `makemigrations` prints `No changes detected`, which also shows Django loads
  `adit.mass_transfer.models` without an import cycle;
- lint reports no errors.

- [ ] **Step 6: Commit**

```bash
git add adit/mass_transfer/processors.py adit/mass_transfer/forms.py adit/mass_transfer/models.py \
  adit/mass_transfer/tests/test_processor.py CLAUDE.md
git commit -m "Use the core series filters and pseudonym in mass transfer"
```
