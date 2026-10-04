import pytest
from pydicom.uid import (
    CTImageStorage,
    ExplicitVRLittleEndian,
    ImplicitVRLittleEndian,
    JPEGLosslessSV1,
)
from pynetdicom.presentation import AllStoragePresentationContexts

from adit.core.errors import DicomError
from adit.core.utils.presentation_contexts import (
    requested_store_contexts,
    storage_scp_contexts,
)


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
