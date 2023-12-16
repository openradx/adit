# type: ignore

import pytest
from django_test_migrations.migrator import Migrator


@pytest.mark.django_db
def test_0011_convert_dicom_node_accesses(migrator: Migrator):
    old_state = migrator.apply_initial_migration(("core", "0010_dicomnodegroupaccess"))

    DicomNodeInstituteAccess = old_state.apps.get_model("core", "DicomNodeInstituteAccess")
    DicomFolder = old_state.apps.get_model("core", "DicomFolder")
    DicomServer = old_state.apps.get_model("core", "DicomServer")
    Institute = old_state.apps.get_model("accounts", "Institute")

    institute = Institute.objects.create(name="Radiology Department")
    server = DicomServer.objects.create(
        name="Orthanc", ae_title="ORTHANC", host="127.0.0.1", port=11112
    )
    folder = DicomFolder.objects.create(name="Foobar", path="/foo/bar")
    DicomNodeInstituteAccess.objects.create(
        institute=institute,
        dicom_node=server,
        source=True,
        destination=True,
    )
    DicomNodeInstituteAccess.objects.create(
        institute=institute,
        dicom_node=folder,
        source=False,
        destination=True,
    )

    # As migration core.0011_convert_dicom_node_accesses depends on
    # accounts.0007_convert_institutes_to_groups this migration will also run
    # and the institute will be converted to a group automatically
    new_state = migrator.apply_tested_migration(("core", "0011_convert_dicom_node_accesses"))

    DicomNodeGroupAccess = new_state.apps.get_model("core", "DicomNodeGroupAccess")

    assert DicomNodeGroupAccess.objects.count() == 2
    server_access = DicomNodeGroupAccess.objects.get(dicom_node__name=server.name)
    assert server_access.group.name == institute.name
    assert server_access.source
    assert server_access.destination
    folder_access = DicomNodeGroupAccess.objects.get(dicom_node__name=folder.name)
    assert folder_access.group.name == institute.name
    assert not folder_access.source
    assert folder_access.destination
