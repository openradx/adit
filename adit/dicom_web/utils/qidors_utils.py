import logging
from datetime import datetime
from typing import Any

from adrf.views import sync_to_async
from pydicom import Dataset, datadict, valuerep
from rest_framework.exceptions import NotFound

from adit.core.models import DicomServer
from adit.core.utils.dicom_connector import DicomConnector

logger = logging.getLogger(__name__)


async def qido_find(source_server: DicomServer, query: dict, level: str):
    query = await sync_to_async(convert_datetime_strings)(query)
    connector = DicomConnector(source_server)

    logger.info("Connected to server %s.", source_server.ae_title)

    if level == "STUDY":
        results = await sync_to_async(connector.find_studies)(query)
    elif level == "SERIES":
        results = await sync_to_async(connector.find_series)(query)
    else:
        raise NotFound("Supported levels are 'STUDY' and 'SERIES'")

    if len(results) <= 0:
        raise NotFound("No query results found.")

    results = await sync_to_async(convert_to_dicom_json)(results)
    return results


def convert_datetime_strings(query: dict[str, Any]) -> dict[str, Any]:
    """Converts all datetime strings in a query to datetime objects."""
    for k, v in query.items():
        if not v:
            continue
        t = datadict.tag_for_keyword(k)
        if t is None:
            continue
        vr = datadict.dictionary_VR(t)
        if vr == "DA":
            iso = string_to_isoformat(v, valuerep.DA)
            query[k] = datetime.fromisoformat(iso)
        elif vr == "DT":
            iso = string_to_isoformat(v, valuerep.DT)
            query[k] = datetime.fromisoformat(iso)
        elif vr == "TM":
            iso = string_to_isoformat(v, valuerep.TM)
            query[k] = datetime.fromisoformat(iso)
    return query


def string_to_isoformat(date_string, value_representation):
    """Converts a date string to an isoformat string according to the given value representation."""
    try:
        rep = value_representation(date_string)
    except ValueError:
        rep = value_representation.fromisoformat(date_string)
    return rep.isoformat()


def convert_to_dicom_json(results: list) -> list:
    """Converts a list of adit query resulty to a list of json instances."""
    list = []
    for result in results:
        ds = Dataset()
        for k, v in result.items():
            tag = datadict.tag_for_keyword(k)
            if tag is None:
                continue
            vr = datadict.dictionary_VR(tag)
            if vr == "DA":
                ds.add_new(k, vr, v.strftime("%Y%m%d"))
            elif vr == "DT":
                ds.add_new(k, vr, v.strftime("%Y%m%d%H%M%S"))
            elif vr == "TM":
                ds.add_new(k, vr, v.strftime("%H%M%S"))
            else:
                ds.add_new(k, vr, v)
        list.append(ds.to_json(suppress_invalid_tags=True))
    return list
