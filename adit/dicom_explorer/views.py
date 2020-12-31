import asyncio
from asgiref.sync import sync_to_async
from django.core.exceptions import ValidationError
from django.shortcuts import render, redirect
from django.urls import resolve
from django.contrib.auth.decorators import login_required
from adit.core.models import DicomServer
from adit.core import validators
from .forms import DicomExplorerQueryForm
from .utils.dicom_data_collector import DicomDataCollector


@login_required
def dicom_explorer_form_view(request):
    if request.GET:
        form = DicomExplorerQueryForm(request.GET)
    else:
        form = DicomExplorerQueryForm()

    if not request.GET or not form.is_valid():
        return render(
            request, "dicom_explorer/dicom_explorer_query_form.html", {"form": form}
        )

    query = form.cleaned_data
    server = query["server"]
    patient_id = query.get("patient_id")
    accession_number = query.get("accession_number")
    study_uid = query.get("study_uid")
    series_uid = query.get("series_uid")

    if patient_id and not (accession_number or study_uid):
        resource_type = "patients"
    elif (accession_number or study_uid) and not series_uid:
        resource_type = "studies"
    elif series_uid:
        resource_type = "series"
    else:
        # Should never happen as we validate the form
        raise AssertionError("Invalid DICOM explorer query.")

    return redirect(
        "dicom_explorer_query", server_id=server.id, resource_type=resource_type
    )


async def dicom_explorer_query_view(
    request, server_id=None, patient_id=None, study_uid=None, series_uid=None
):
    denied_response = await check_permission(request)
    if denied_response:
        return denied_response

    if patient_id is not None and not is_valid_id(patient_id):
        render_error(request, "Invalid patient identifier.")
    if study_uid is not None and not is_valid_id(study_uid):
        render_error(request, "Invalid study identifier.")
    if series_uid is not None and not is_valid_id(series_uid):
        render_error(request, "Invalid series identifier.")

    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(
        None, render_query_result, request, server_id, patient_id, study_uid, series_uid
    )

    return response


@sync_to_async
@login_required
def check_permission(request):
    # A dummy function for the permission decorators
    pass


def is_valid_id(value):
    try:
        validators.no_backslash_char_validator(value)
        validators.no_control_chars_validator(value)
        validators.no_wildcard_chars_validator(value)
    except ValidationError:
        return False

    return True


def render_error(request, error_message):
    render(
        request, "dicom_explorer/error_message.html", {"error_message": error_message}
    )


def render_query_result(request, server_id, patient_id, study_uid, series_uid):
    server = DicomServer.objects.get(pk=server_id)
    if not server or not server.source_active:
        return render_error(request, "Invalid server ID.")

    query = {}
    if request.GET:
        query.update(request.GET)

    url_name = resolve(request.path_info).url_name

    if url_name == "dicom_explorer_query_servers":
        return render_server_query_result(request, server_id)

    if url_name == "dicom_explorer_query_patients":
        return render_patient_query_result(request, server, patient_id, query)

    if url_name == "dicom_explorer_query_studies":
        return render_study_query_result(request, server, study_uid, query)

    if url_name == "dicom_explorer_query_series":
        return render_series_query_result(request, server, study_uid, series_uid, query)

    raise AssertionError(f"Invalid URL name {url_name}.")


def render_server_query_result(request, server_id):
    if not server_id:
        servers = DicomServer.objects.find(source_active=True)
        return render(request, "dicom_explorer/server_list.html", {"servers": servers})

    server = DicomServer.objects.get(pk=server_id)

    if not server:
        return render_error(request, f"Invalid server ID {server_id}.")

    return render(request, "dicom_explorer/server_detail.html", {"server": server})


def render_patient_query_result(request, server, patient_id, query):
    collector = DicomDataCollector(server.create_connector())

    if not patient_id:
        patients = collector.collect_patient_data(query=query)

        return render(
            request,
            "dicom_explorer/patient_list.html",
            {"server": server, "patients": patients},
        )

    patients = collector.collect_patient_data(patient_id, query)

    if len(patients) == 0:
        return render_error(request, f"No patient found for Patient ID {patient_id}.")

    if len(patients) > 1:
        return render_error(
            request, f"Multiple patients found for Patient ID {patient_id}."
        )

    studies = collector.collect_study_data(query={"PatientID": patient_id})

    return render(
        request,
        "dicom_explorer/patient_detail.html",
        {"server": server, "patient": patients[0], "studies": studies},
    )


def render_study_query_result(request, server, study_uid, query):
    collector = DicomDataCollector(server.create_connector())

    if not study_uid:
        studies = collector.collect_study_data(query=query)

        return render(
            request,
            "dicom_explorer/study_list.html",
            {"server": server, "studies": studies},
        )

    studies = collector.collect_study_data(study_uid, query)

    if len(studies) == 0:
        return render_error(
            request, f"No study found for Study Instance UID {study_uid}."
        )

    if len(studies) > 1:
        return render_error(
            request, f"Multiple studies found for Study Instance UID {study_uid}."
        )

    patients = collector.collect_patient_data(studies[0]["PatientID"])

    if len(patients) == 0:
        # Should never happen as we already found a valid study with this UID
        raise AssertionError(
            f"No patient found for study with Study Instance UID {study_uid}."
        )

    if len(patients) > 1:
        # Should never happen as we already found a valid study with this UID
        raise AssertionError(
            f"Multiple patients found for study with Study Instance UID {study_uid}.",
        )

    series_list = collector.collect_series_data(study_uid)

    return render(
        request,
        "dicom_explorer/study_detail.html",
        {
            "server": server,
            "patient": patients[0],
            "study": studies[0],
            "series_list": series_list,
        },
    )


def render_series_query_result(request, server, study_uid, series_uid, query):
    collector = DicomDataCollector(server.create_connector())

    studies = collector.collect_study_data(study_uid)

    if len(studies) == 0:
        return render_error(
            request, f"No study found for Study Instance UID {study_uid}."
        )

    if len(studies) > 1:
        return render_error(
            request, f"Multiple studies found for Study Instance UID {study_uid}."
        )

    patients = collector.collect_patient_data(patient_id=studies[0]["PatientID"])

    if len(patients) == 0:
        # Should never happen as we already found a valid study with this UID
        raise AssertionError(
            f"No patient found for study with Study Instance UID {study_uid}."
        )

    if len(patients) > 1:
        # Should never happen as we already found a valid study with this UID
        raise AssertionError(
            f"Multiple patients found for study with Study Instance UID {study_uid}.",
        )

    if not series_uid:
        series_list = collector.collect_series_data(study_uid, query=query)

        return render(
            request,
            "dicom_explorer/series_list.html",
            {
                "server": server,
                "patient": patients[0],
                "study": studies[0],
                "series_list": series_list,
            },
        )

    series_list = collector.collect_series_data(study_uid, series_uid, query)

    if len(series_list) == 0:
        return render_error(
            request,
            (
                f"No series found for Study Instance UID {study_uid} "
                f"and Series Instance UID {series_uid}."
            ),
        )

    if len(series_list) > 1:
        return render_error(
            request,
            (
                f"Multiple series found for Study Instance UID {study_uid} "
                f"and Series Instance UID {series_uid}."
            ),
        )

    return render(
        request,
        "dicom_explorer/series_detail.html",
        {
            "server": server,
            "patient": patients[0],
            "study": studies[0],
            "series": series_list[0],
        },
    )
