from rest_framework import serializers
from rest_framework.fields import empty

from django.conf import settings

from adit.core.models import DicomNode, TransferTask
from adit.selective_transfer.models import SelectiveTransferJob

from .formats import ApplicationDicom, ApplicationDicomJson
from .writers import ElementWriter

from typing import Type
from pydicom import DataElement


# WADO-RS
class DicomWebSerializer():
    FORMATS = [ApplicationDicom, ApplicationDicomJson]
    MULTIPART_MEDIA_TYPES = ["multipart/related"]
    MEDIA_TYPES = ["application/dicom+json"]

    @property
    def bulk_content_types(self):
        return self._get_content_types("bulk")

    @property
    def meta_content_types(self):
        return self._get_content_types("meta")
    
    @property
    def bulk_d_content_type(self):
        return self._get_d_content_type("bulk")
    
    @property
    def meta_d_content_type(self):
        return self._get_d_content_type("meta")

    @property
    def multipart_content_types(self):
        list = []
        for supported_format in self.FORMATS:
            if supported_format.multipart:
                list.append(supported_format.content_type)
        return list

    def setup_writer(
        self, fpath: str, mode: str, content_type: str, boundary=settings.DEFAULT_BOUNDARY
    ) -> None:
        self.boundary = boundary
        self.writer = self._get_writer(fpath, mode, content_type)

    def start_file(
        self, fpath: str, content_type:str
    ) -> None:
        if content_type in self.multipart_content_types:
            with open(fpath, "wb") as file:
                file.write(b"")

    def end_file(
        self, fpath: str, content_type: str
    ) -> None:
        if content_type in self.multipart_content_types:
            if content_type in self.bulk_content_types:
                boundary = self.boundary.encode('ascii') 
                with open(fpath, "ab") as file:
                    file.write(b"--"+boundary+b"--")
            else:
                with open(fpath, "a") as file:
                    file.write("--"+self.boundary+"--")

    def write(
        self, ds: Type[DataElement]
    ) -> tuple:
        return self.writer.write_ds(ds)

    def _get_content_types(
        self, mode: str
    ) -> list:
        list = []
        for supported_format in self.FORMATS:
            if supported_format.mode==mode:
                list.append(supported_format.content_type)
        return list

    def _get_d_content_type(
        self, mode: str
    ) -> str:
        for supported_format in self.FORMATS:
            if supported_format.mode==mode:
                if supported_format.mode_default:
                    return supported_format.content_type
        raise SystemError("No default content type for mode: {mode} provided.")

    def _get_writer(
        self, fpath: str, mode: str, content_type: str
    ) -> Type[ElementWriter]:
        for supported_format in self.FORMATS:
            if supported_format.mode==mode:
                if supported_format.content_type==content_type:
                    writer = supported_format.writer(fpath, self.boundary)
                    return writer
        raise SystemError(f"No writer found for mode: {mode} and content_type: {content_type}")



class DicomNodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = DicomNode
        fields = ["name"]


class TransferTaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = TransferTask
        fields = ["patient_id", "study_uid", "series_uids", "pseudonym"]

    def __init__(self, instance=None, data=empty, max_series_count=100, **kwargs):
        self.max_series_count = max_series_count
        super().__init__(instance=instance, data=data, **kwargs)

    def validate_series_uids(self, series_uids):  # pylint: disable=no-self-use
        # TODO validate the series UID itself
        if len(series_uids) > self.max_series_count:
            raise serializers.ValidationError(
                f"Maximum {self.max_series_count} series per task allowed."
            )
        return series_uids


class SelectiveTransferJobListSerializer(serializers.ModelSerializer):
    source = DicomNodeSerializer()
    destination = DicomNodeSerializer()
    status = serializers.CharField(source="get_status_display")

    class Meta:
        model = SelectiveTransferJob
        fields = [
            "id",
            "source",
            "destination",
            "status",
            "message",
            "trial_protocol_id",
            "trial_protocol_name",
            "owner",
            "created",
            "start",
            "end",
        ]
