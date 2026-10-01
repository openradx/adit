from pydicom.uid import (
    BasicTextSRStorage,
    CTImageStorage,
    ExplicitVRLittleEndian,
    ImplicitVRLittleEndian,
    JPEGLosslessSV1,
)
from pynetdicom.presentation import AllStoragePresentationContexts

from adit.core.utils.presentation_contexts import storage_scp_contexts


def _syntaxes_by_class() -> dict[str, list[str]]:
    return {
        str(cx.abstract_syntax): [str(ts) for ts in cx.transfer_syntax]
        for cx in storage_scp_contexts()
    }


def test_scp_contexts_cover_every_pynetdicom_storage_class():
    syntaxes = _syntaxes_by_class()

    for cx in AllStoragePresentationContexts:
        assert str(cx.abstract_syntax) in syntaxes


def test_scp_contexts_include_retired_classes_adit_knows():
    # Ultrasound Image Storage (Retired) is in ADIT's list but not in pynetdicom's.
    assert "1.2.840.10008.5.1.4.1.1.6" in _syntaxes_by_class()


def test_image_classes_accept_compressed_and_uncompressed_syntaxes():
    syntaxes = _syntaxes_by_class()[CTImageStorage]

    assert JPEGLosslessSV1 in syntaxes
    assert ImplicitVRLittleEndian in syntaxes
    assert ExplicitVRLittleEndian in syntaxes


def test_non_image_classes_accept_only_uncompressed_syntaxes():
    syntaxes = _syntaxes_by_class()[BasicTextSRStorage]

    assert ImplicitVRLittleEndian in syntaxes
    assert JPEGLosslessSV1 not in syntaxes


def test_newer_image_classes_accept_compressed_syntaxes():
    syntaxes = _syntaxes_by_class()

    # Breast Projection X-Ray Image Storage For Presentation
    breast_projection = "1.2.840.10008.5.1.4.1.1.13.1.4"
    assert JPEGLosslessSV1 in syntaxes[breast_projection]

    # Enhanced RT Image Storage
    enhanced_rt = "1.2.840.10008.5.1.4.1.1.481.23"
    assert JPEGLosslessSV1 in syntaxes[enhanced_rt]
