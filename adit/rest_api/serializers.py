from asyncore import write
from rest_framework import serializers
from rest_framework.fields import empty
from adit.core.models import DicomNode, TransferJob, TransferTask
from adit.selective_transfer.models import SelectiveTransferJob

from pydicom import dcmread
from pydicom.filewriter import dcmwrite
from pydicom.uid import RLELossless

import json
import os


# WADO-RS
class DicomStudySerializer():
    BOUNDARY = "adit-boundary"

    
    class DicomDataElementWriter():
        def __init__(self, file, BOUNDARY):
            self.file = file
            self.BOUNDARY = BOUNDARY
            self.CONTENT_TYPE = b"application/dicom"

        def write(self, instance, chunk_size=1024):
            self.file.write(b"--" + self.BOUNDARY + b"\r\n")
            self.file.write(b"Content-Type: " + self.CONTENT_TYPE + b"\r\n")

            ds = dcmread(instance)
            if ds.is_little_endian:
                dcmwrite(self.file, ds)

            self.file.write(b"\r\n")


    class MetaDataElementWriter():
        def __init__(self, file, BOUNDARY):
            self.file = file
            self.BOUNDARY = BOUNDARY
            self.CONTENT_TYPE = "application/dicom+json"
            
        def write(self, instance):
            self.file.write("--" + self.BOUNDARY + "\r\n")
            self.file.write("Content-Type: " + self.CONTENT_TYPE + "\r\n")
            
            ds = dcmread(instance).file_meta
            DataSet = ds.to_json_dict()
            
            json.dump(DataSet, self.file)
            
            self.file.write("\r\n")


    class JPEGDataElementWriter():
        def __init__(self, file, BOUNDARY):
            self.file = file
            self.BOUNDARY = BOUNDARY
            self.CONTENT_TYPE = b"image/dicom+jpeg"

        def write(self, instance):
            ds = dcmread(instance)
            ds.compress(RLELossless, encoding_plugin='pylibjpeg')

            self.file.write(b"--" + self.BOUNDARY + b"\r\n")
            self.file.write(b"Content-Type: " + self.CONTENT_TYPE + b"\r\n")
            
            self.file.write(ds.PixelData)
            
            self.file.write(b"\r\n")


    def write(self, study, fpath, mode=None):
        if mode == None:
            return self._write_full(self, study, fpath)
            
        if mode == "metadata":
            return self._write_meta(self, study, fpath)

        if mode == "jpeg":
            return self._write_jpeg(self, study, fpath)


    def _write_jpeg(self, study, fpath):
        BOUNDARY = self.BOUNDARY.encode('ascii') 

        with open(fpath, "wb") as file:
            instance_writer = self.JPEGDataElementWriter(file, BOUNDARY)
            
            for instance in study:
                instance_writer.write(instance)
                
        return fpath, instance_writer.BOUNDARY


    def _write_full(self, study, fpath):
        BOUNDARY = self.BOUNDARY.encode('ascii') 

        with open(fpath, "wb") as file:
            instance_writer = self.DicomDataElementWriter(file, BOUNDARY)

            for instance in study:
                instance_writer.write(instance)
            
            file.write(b"--" + BOUNDARY + b"--")

        return fpath, instance_writer.BOUNDARY


    def _write_meta(self, study, fpath):
        with open(fpath, "w") as file:
            instance_writer = self.MetaDataElementWriter(file, self.BOUNDARY)

            for instance in study:
                instance_writer.write(instance)

            file.write("--" + self.BOUNDARY + "--")

        return fpath, instance_writer.BOUNDARY


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
