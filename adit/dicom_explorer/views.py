import asyncio
from asgiref.sync import sync_to_async
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from .forms import DicomExplorerQueryForm
from .utils.dicom_data_collector import DicomDataCollector


@sync_to_async
@login_required
def check_permission(request):
    # A dummy function for the permission decorators
    pass


@sync_to_async
def get_form(request):
    if not request.GET:
        form = DicomExplorerQueryForm(initial=request.GET)
    else:
        form = DicomExplorerQueryForm(request.GET)
    return form


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


@sync_to_async
def render_query_form(request, form):
    return render(request, "dicom_explorer/query_form.html", {"form": form})


async def dicom_explorer_view(request):
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
