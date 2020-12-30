import asyncio
from asgiref.sync import sync_to_async
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
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

    redirect("dicom_explorer_query", server_id=server.id, resource_type=resource_type)


async def dicom_explorer_query_view(request, server_id, resource_type):
    denied_response = await check_permission(request)
    if denied_response:
        return denied_response

    form = await get_form(request)
    form_valid = await sync_to_async(form.is_valid)()

    if request.GET and form_valid:
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, render_query_result, request, form)
    else:
        response = await render_query_form(request, form)

    return response


@sync_to_async
@login_required
def check_permission(request):
    # A dummy function for the permission decorators
    pass


def render_query_result(request, form):
    query = form.cleaned_data
    server = query["server"]
    connector = server.create_connector()
    collector = DicomDataCollector(connector)

    if query.get("patient_id") and not (
        query.get("accession_number") or query.get("study_uid")
    ):
        patient, studies = collector.collect_patient_data(query.get("patient_id"))
        return render(
            request,
            "dicom_explorer/explore_patient.html",
            {
                "level": "patient",
                "server": server,
                "patient": patient,
                "studies": studies,
            },
        )

    if (query.get("accession_number") or query.get("study_uid")) and not query.get(
        "series_uid"
    ):
        patient, study, series_list = collector.collect_study_data(
            query.get("patient_id"),
            query.get("accession_number"),
            query.get("study_uid"),
        )
        return render(
            request,
            "dicom_explorer/explore_study.html",
            {
                "level": "study",
                "server": server,
                "patient": patient,
                "study": study,
                "series_list": series_list,
            },
        )

    if query.get("series_uid"):
        patient, study, series = collector.collect_series_data(
            query.get("patient_id"),
            query.get("accession_number"),
            query.get("study_uid"),
            query.get("series_uid"),
        )
        return render(
            request,
            "dicom_explorer/explore_series.html",
            {
                "level": "series",
                "server": server,
                "patient": patient,
                "study": study,
                "series": series,
            },
        )

    # Should never happen as we validate the query with the form instance
    raise AssertionError(f"Invalid DICOM explorer query: {query}")