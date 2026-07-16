"""Focused unit tests for pure (non-DB) helpers in ``stowrs_utils``.

Only ``remove_unknow_vr_attributes`` is exercised here: it operates purely on an
in-memory pydicom ``Dataset`` and needs neither the database nor a DICOM server.
The other public helper (``stow_store``) drives a ``DicomOperator`` against a
real ``DicomServer`` and is therefore out of scope for non-DB unit tests.
"""

import pytest
from pydicom import Dataset, Sequence

from adit.dicom_web.utils.stowrs_utils import remove_unknow_vr_attributes


@pytest.mark.asyncio
async def test_converts_unknown_vr_to_st_and_records_original():
    """UN elements are rewritten to VR 'ST' and logged in an attributes sequence.

    STOW targets often reject elements with an unknown (UN) value representation.
    The helper rewrites them to a short-text ('ST') VR in place and returns an
    OriginalAttributesSequence documenting the modification (per DICOM PS3.18
    I.2.2), so the change is auditable.
    """
    ds = Dataset()
    ds.PatientID = "PID"
    ds.add_new(0x00090010, "UN", b"\x01\x02")  # private element with UN VR

    original_attributes = await remove_unknow_vr_attributes(ds)

    assert isinstance(original_attributes, Sequence)
    assert len(original_attributes) == 1

    # The element's VR is rewritten in place; a normal (non-UN) element is untouched.
    assert ds[0x00090010].VR == "ST"
    assert ds.PatientID == "PID"

    modification = original_attributes[0]
    assert modification.ModifyingSystem == "ADIT"
    assert modification.ReasonForTheAttributeModification == "VR_UNKNOWN"
    # AttributeModificationDateTime is a 14-char DICOM datetime stamp.
    assert len(modification.AttributeModificationDateTime) == 14
    assert modification.AttributeModificationDateTime.isdigit()
    # The original element is preserved inside the modified-attributes sequence.
    assert len(modification.ModifiedAttributesSequence) == 1


@pytest.mark.asyncio
async def test_no_unknown_vr_returns_empty_sequence():
    """A dataset without UN elements is left unchanged with an empty sequence."""
    ds = Dataset()
    ds.PatientID = "PID"
    ds.StudyInstanceUID = "1.2.3"

    original_attributes = await remove_unknow_vr_attributes(ds)

    assert isinstance(original_attributes, Sequence)
    assert len(original_attributes) == 0
    # Existing, well-typed elements are untouched.
    assert ds.PatientID == "PID"
    assert ds.StudyInstanceUID == "1.2.3"


@pytest.mark.asyncio
async def test_unserializable_un_value_falls_back_to_placeholder():
    """If the UN value cannot be stringified, a placeholder is stored instead.

    The helper does ``str(elem.value)`` and on ValueError substitutes the literal
    string "not serializable", so a hostile/odd value can never abort the cleanup.
    """

    class Unserializable:
        def __str__(self):
            raise ValueError("cannot stringify")

    ds = Dataset()
    ds.add_new(0x00090011, "UN", b"\x00")
    # Replace the raw value with something whose str() raises.
    ds[0x00090011].value = Unserializable()

    original_attributes = await remove_unknow_vr_attributes(ds)

    assert len(original_attributes) == 1
    assert ds[0x00090011].VR == "ST"
    assert ds[0x00090011].value == "not serializable"
