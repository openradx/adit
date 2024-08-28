import asyncio
from urllib.parse import urlencode

from adit_radis_shared.common.decorators import login_required_async, permission_required_async
from adit_radis_shared.common.types import AuthenticatedHttpRequest
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import resolve, reverse

from adit.core import validators
from adit.core.models import DicomServer
from adit.core.utils.dicom_dataset import QueryDataset

from .forms import DicomExplorerQueryForm
from .utils.dicom_data_collector import DicomDataCollector


@login_required
def dicom_explorer_form_view(request: AuthenticatedHttpRequest) -> HttpResponse:
    if request.GET:
        form = DicomExplorerQueryForm(request.GET, user=request.user)
    else:
        form = DicomExplorerQueryForm(user=request.user)

    if not request.GET or not form.is_valid():
        return render(request, "dicom_explorer/query_form.html", {"form": form})

    query = form.cleaned_data
    server = query["server"]
    patient_id = query.get("patient_id")
    accession_number = query.get("accession_number")

    if server and not (patient_id or accession_number):
        return redirect("dicom_explorer_server_detail", server_id=server.id)

    if patient_id and not accession_number:
        return redirect("dicom_explorer_patient_detail", server_id=server.id, patient_id=patient_id)

    if accession_number:
        params = {"AccessionNumber": accession_number}
        if patient_id:
            params["PatientID"] = patient_id

        url = reverse("dicom_explorer_patient_query")
        url = f"{url}?{urlencode(params)}"
        return redirect(url)

    # Should never happen as we validate the form
    raise AssertionError("Invalid DICOM explorer query.")


@login_required_async
@permission_required_async("dicom_explorer.query_dicom_server")
async def dicom_explorer_resources_view(
    request: AuthenticatedHttpRequest,
    server_id: str | None = None,
    patient_id: str | None = None,
    study_uid: str | None = None,
    series_uid: str | None = None,
) -> HttpResponse:
    if patient_id is not None and not is_valid_id(patient_id):
        render_error(request, f"Invalid Patient ID {patient_id}.")
    if study_uid is not None and not is_valid_id(study_uid):
        render_error(request, f"Invalid Study Instance UID {study_uid}.")
    if series_uid is not None and not is_valid_id(series_uid):
        render_error(request, f"Invalid Sereis Instance UID {series_uid}.")

    loop = asyncio.get_event_loop()
    try:
        future = loop.run_in_executor(
            None,
            render_query_result,
            request,
            server_id,
            patient_id,
            study_uid,
            series_uid,
        )
        timeout = settings.DICOM_EXPLORER_RESPONSE_TIMEOUT
        response = await asyncio.wait_for(future, timeout=timeout)
        return response
    except asyncio.TimeoutError:
        return render_error(request, "Connection to server timed out. Please try again later.")


def is_valid_id(value):
    try:
        validators.no_backslash_char_validator(value)
        validators.no_control_chars_validator(value)
        validators.no_wildcard_chars_validator(value)
    except ValidationError:
        return False

    return True


def render_error(request: HttpRequest, error_message: str) -> HttpResponse:
    return render(request, "dicom_explorer/error_message.html", {"error_message": error_message})


def render_query_result(
    request: AuthenticatedHttpRequest,
    server_id: str | None = None,
    patient_id: str | None = None,
    study_uid: str | None = None,
    series_uid: str | None = None,
) -> HttpResponse:
    """Calls other functions to render specific data.

    One can presume that the parameters are correctly set as they are checked
    when the URL is resolved.
    """
    query: dict[str, str] = {}
    for key, value in request.GET.items():
        assert isinstance(value, str)
        query[key] = value

    url_name = resolve(request.path_info).url_name

    if url_name == "dicom_explorer_server_query":
        return render_server_query(request, query)

    try:
        server = DicomServer.objects.accessible_by_user(request.user, "source").get(id=server_id)
    except DicomServer.DoesNotExist:
        return render_error(request, "Invalid DICOM server.")

    if url_name == "dicom_explorer_server_detail":
        response = render_server_detail(request, server)
    elif url_name == "dicom_explorer_patient_query":
        response = render_patient_query(request, server, query)
    elif url_name == "dicom_explorer_patient_detail":
        if not patient_id:
            raise AssertionError("Missing patient ID.")
        response = render_patient_detail(request, server, patient_id)
    elif url_name == "dicom_explorer_study_query":
        response = render_study_query(request, server, query)
    elif url_name == "dicom_explorer_study_detail":
        if not study_uid:
            raise AssertionError("Missing study UID.")
        response = render_study_detail(request, server, study_uid)
    elif url_name == "dicom_explorer_series_query":
        if not study_uid:
            raise AssertionError("Missing study UID.")
        response = render_series_query(request, server, study_uid, query)
    elif url_name == "dicom_explorer_series_detail":
        if not study_uid:
            raise AssertionError("Missing study UID.")
        if not series_uid:
            raise AssertionError("Missing series UID.")
        response = render_series_detail(request, server, study_uid, series_uid)
    else:
        raise AssertionError(f"Invalid URL name {url_name}.")

    return response


def render_server_query(request: HttpRequest, query: dict[str, str]) -> HttpResponse:
    """Query servers and render the result."""
    final_query = query | {"accesses_source": True}
    servers = DicomServer.objects.filter(**final_query).order_by("id")
    return render(request, "dicom_explorer/server_query.html", {"servers": servers})


def render_server_detail(request: HttpRequest, server: DicomServer) -> HttpResponse:
    """Render server details."""
    if not server:
        return render_error(request, f"Invalid server ID {server.id}.")

    return render(request, "dicom_explorer/server_detail.html", {"server": server})


def render_patient_query(
    request: HttpRequest, server: DicomServer, query: dict[str, str]
) -> HttpResponse:
    """Query patients and render the result."""
    collector = DicomDataCollector(server)
    query_ds = QueryDataset.from_dict(query)
    limit = settings.DICOM_EXPLORER_RESULT_LIMIT
    patients = collector.collect_patients(query_ds, limit_results=limit)
    max_results_reached = len(patients) >= limit
    return render(
        request,
        "dicom_explorer/patient_query.html",
        {
            "server": server,
            "patients": patients,
            "max_results_reached": max_results_reached,
        },
    )


def render_patient_detail(
    request: HttpRequest, server: DicomServer, patient_id: str
) -> HttpResponse:
    """Render patient data and his studies."""
    collector = DicomDataCollector(server)
    patients = collector.collect_patients(QueryDataset.create(PatientID=patient_id))

    if len(patients) == 0:
        return render_error(request, f"No patient found with Patient ID {patient_id}.")

    if len(patients) > 1:
        return render_error(request, f"Multiple patients found with Patient ID {patient_id}.")

    studies = collector.collect_studies(QueryDataset.create(PatientID=patient_id))
    return render(
        request,
        "dicom_explorer/patient_detail.html",
        {"server": server, "patient": patients[0], "studies": studies},
    )


def render_study_query(
    request: HttpRequest, server: DicomServer, query: dict[str, str]
) -> HttpResponse:
    collector = DicomDataCollector(server)
    query_ds = QueryDataset.from_dict(query)
    limit = settings.DICOM_EXPLORER_RESULT_LIMIT
    studies = collector.collect_studies(query_ds, limit_results=limit)
    max_results_reached = len(studies) >= limit
    return render(
        request,
        "dicom_explorer/study_query.html",
        {
            "server": server,
            "studies": studies,
            "max_results_reached": max_results_reached,
        },
    )


def render_study_detail(request: HttpRequest, server: DicomServer, study_uid: str) -> HttpResponse:
    collector = DicomDataCollector(server)
    studies = collector.collect_studies(QueryDataset.create(StudyInstanceUID=study_uid))

    if len(studies) == 0:
        return render_error(request, f"No study found with Study Instance UID {study_uid}.")

    if len(studies) > 1:
        return render_error(request, f"Multiple studies found with Study Instance UID {study_uid}.")

    patients = collector.collect_patients(QueryDataset.create(PatientID=studies[0].PatientID))

    if len(patients) == 0:
        # Should never happen as we already found a valid study with this UID
        raise AssertionError(f"No patient found for study with Study Instance UID {study_uid}.")

    if len(patients) > 1:
        # Should never happen as we already found a valid study with this UID
        raise AssertionError(
            f"Multiple patients found for study with Study Instance UID {study_uid}.",
        )

    series_list = collector.collect_series(QueryDataset.create(StudyInstanceUID=study_uid))
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


def render_series_query(
    request: HttpRequest, server: DicomServer, study_uid: str, query: dict[str, str]
) -> HttpResponse:
    collector = DicomDataCollector(server)
    studies = collector.collect_studies(QueryDataset.create(StudyInstanceUID=study_uid))

    if len(studies) == 0:
        return render_error(request, f"No study found with Study Instance UID {study_uid}.")

    if len(studies) > 1:
        return render_error(request, f"Multiple studies found with Study Instance UID {study_uid}.")

    patients = collector.collect_patients(QueryDataset.create(PatientID=studies[0].PatientID))

    if len(patients) == 0:
        # Should never happen as we already found a valid study with this UID
        raise AssertionError(f"No patient found for study with Study Instance UID {study_uid}.")

    if len(patients) > 1:
        # Should never happen as we already found a valid study with this UID
        raise AssertionError(
            f"Multiple patients found for study with Study Instance UID {study_uid}.",
        )

    series_list = collector.collect_series(
        QueryDataset.from_dict(query, StudyInstanceUID=study_uid)
    )

    return render(
        request,
        "dicom_explorer/series_query.html",
        {
            "server": server,
            "patient": patients[0],
            "study": studies[0],
            "series_list": series_list,
        },
    )


def render_series_detail(
    request: HttpRequest, server: DicomServer, study_uid: str, series_uid: str
) -> HttpResponse:
    collector = DicomDataCollector(server)

    studies = collector.collect_studies(QueryDataset.create(StudyInstanceUID=study_uid))

    if len(studies) == 0:
        return render_error(request, f"No study found with Study Instance UID {study_uid}.")

    if len(studies) > 1:
        return render_error(request, f"Multiple studies found with Study Instance UID {study_uid}.")

    patients = collector.collect_patients(QueryDataset.create(PatientID=studies[0].PatientID))

    if len(patients) == 0:
        # Should never happen as we already found a valid study with this UID
        raise AssertionError(f"No patient found for study with Study Instance UID {study_uid}.")

    if len(patients) > 1:
        # Should never happen as we already found a valid study with this UID
        raise AssertionError(
            f"Multiple patients found for study with Study Instance UID {study_uid}.",
        )

    series_list = collector.collect_series(
        QueryDataset.create(StudyInstanceUID=study_uid, SeriesInstanceUID=series_uid)
    )

    if len(series_list) == 0:
        return render_error(
            request,
            (
                f"No series found with Study Instance UID {study_uid} "
                f"and Series Instance UID {series_uid}."
            ),
        )

    if len(series_list) > 1:
        return render_error(
            request,
            (
                f"Multiple series found with Study Instance UID {study_uid} "
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
