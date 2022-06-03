from requests import RequestException

from django.core import serializers

from adit.core.models import TransferJob, DicomNode, DicomServer
from adit.core.utils.dicom_connector import DicomConnector

def handle_request(request, *args, **kwargs):
    # Find PACS
    pacs_ae_title = kwargs.get("pacs", None)
    SourceServerSet = DicomServer.objects.filter(ae_title=pacs_ae_title)
    if len(SourceServerSet) != 1:
        raise RequestException(f"The specified PACS with AE title: {pacs_ae_title} does not exist or multiple Entities with this title exist.")
    SourceServer = SourceServerSet[0]

    # TODO: Implement accept header handler
    
    return SourceServer

