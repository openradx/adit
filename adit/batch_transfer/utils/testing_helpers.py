from io import BytesIO
from unittest.mock import create_autospec

import pandas as pd
from adit_radis_shared.accounts.factories import GroupFactory
from adit_radis_shared.common.utils.testing_helpers import add_permission
from django.core.files import File
from django.core.files.uploadedfile import SimpleUploadedFile

from adit.core.factories import DicomServerFactory


def create_batch_transfer_group():
    group = GroupFactory.create(name="Radiologists")
    add_permission(group, "batch_transfer", "add_batchtransferjob")
    add_permission(group, "batch_transfer", "view_batchtransferjob")
    return group


def create_data_dict():
    return {
        "source": DicomServerFactory(),
        "destination": DicomServerFactory(),
        "project_name": "Apollo project",
        "project_description": "Fly to the moon",
        "ethics_application_id": "12345",
    }


def create_file_dict():
    file = create_autospec(File, size=5242880)
    file.name = "sample_sheet.xlsx"
    file.read.return_value.decode.return_value = ""
    return {"batch_file": file}


def create_form_data():
    buffer = BytesIO()
    data = pd.DataFrame(
        [
            ["1001", "1.2.840.113845.11.1000000001951524609.20200705182951.2689481", "WSOHMP4N"],
            ["1002", "1.2.840.113845.11.1000000001951524609.20200705170836.2689469", "C2XJQ2AR"],
            ["1003", "1.2.840.113845.11.1000000001951524609.20200705172608.2689471", "KRS8CZ3S"],
        ],
        columns=["PatientID", "StudyInstanceUID", "Pseudonym"],  # type: ignore
    )
    data.to_excel(buffer, index=False)  # type: ignore

    return {
        "source": DicomServerFactory.create().pk,
        "destination": DicomServerFactory.create().pk,
        "project_name": "Apollo project",
        "project_description": "Fly to the moon",
        "ethics_application_id": "12345",
        "batch_file": SimpleUploadedFile(
            name="sample_sheet.xlsx",
            content=buffer.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ),
    }
