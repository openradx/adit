from asyncore import write
from rest_framework import serializers
from rest_framework.fields import empty
from adit.core.models import DicomNode, TransferTask
from adit.selective_transfer.models import SelectiveTransferJob

from pydicom.filewriter import dcmwrite, write_dataset, write_data_element, write_file_meta_info
from pydicom.uid import RLELossless
from pydicom.dataset import FileMetaDataset

import json

# WADO-RS
class DicomSerializer():
    BOUNDARY = "adit-boundary"
    FILE_FORMATS = ["application/dicom","image/dicom+jpeg",]
    FILE_D_FORMAT = "application/dicom"
    META_DATA_FORMATS = ["application/dicom+json", "application/dicom+xml",]
    META_DATA_D_FORMAT = "application/dicom+json"
    
    MULTIPART_MEDIA_TYPES = ["multipart/related"]
    MULTIPART_FORMATS = ["application/dicom", "image/dicom+jpeg", "application/dicom+xml"]
    MEDIA_TYPES = ["application/dicom+json"]

    list = []

    
    class DicomDataElementWriter():
        def __init__(self, file, BOUNDARY):
            self.file = file
            self.BOUNDARY = BOUNDARY
            self.CONTENT_TYPE = "application/dicom"

        def write(self, ds):
            _write_boundary(self.file, self.BOUNDARY)
            _write_header(self.file, content_type=self.CONTENT_TYPE)
            #_write_dicom_header(self.file)
            if ds.is_little_endian:
                dcmwrite(self.file, ds, write_like_original=False)
            self.file.write(b"\r\n")


    class JSONDataElementWriter():
        def __init__(self, file, BOUNDARY):
            self.file = file
            self.BOUNDARY = BOUNDARY
            self.CONTENT_TYPE = "application/dicom+json"
            self.list = []
            
        def write(self, list):
            json.dump(list, self.file)


    class XMLDataElementWriter():
        def __init__(self, file, BOUNDARY):
            self.file = file
            self.BOUNDARY = BOUNDARY
            self.CONTENT_TYPE = "application/dicom+xml"

        def write(self, ds):
            self.file.write("--" + self.BOUNDARY + "\r\n")
            _write_header(self.file, content_type=self.CONTENT_TYPE)
            write_file_meta_info(self.file, ds.file_meta)


    class JPEGDataElementWriter():
        def __init__(self, file, BOUNDARY):
            self.file = file
            self.BOUNDARY = BOUNDARY
            self.CONTENT_TYPE = "image/dicom+jpeg"

        def write(self, ds):
            ds.compress(RLELossless, encoding_plugin='pylibjpeg')
            self.file.write(b"--" + self.BOUNDARY + b"\r\n")
            _write_header(self.file, content_type=self.CONTENT_TYPE)
            self.file.write(ds.PixelData)
            self.file.write(b"\r\n")


    def write(self, ds, fpath, file_format=None):
        if file_format == "application/dicom":
            return self._write_full(self, ds, fpath)
        if file_format == "application/dicom+json":
            return self._write_json(self, ds, fpath)
        if file_format == "application/dicom+xml":
            return self._write_xml(self, ds, fpath)
        if file_format == "image/dicom+jpeg":
            return self._write_jpeg(self, ds, fpath)


    def _write_jpeg(self, ds, fpath):
        BOUNDARY = self.BOUNDARY.encode('ascii') 
        with open(fpath, "ab") as file:
            instance_writer = self.JPEGDataElementWriter(file, BOUNDARY)
            instance_writer.write(ds)                
        return fpath, instance_writer.BOUNDARY


    def _write_full(self, ds, fpath):
        BOUNDARY = self.BOUNDARY.encode('ascii') 
        with open(fpath, "ab") as file:
            instance_writer = self.DicomDataElementWriter(file, BOUNDARY)
            instance_writer.write(ds)
        return fpath, instance_writer.BOUNDARY


    def _write_json(self, ds, fpath):
        json_meta = ds.file_meta.to_json_dict()
        self.list.append(json_meta)
        with open(fpath, "w") as file:
            instance_writer = self.JSONDataElementWriter(file, self.BOUNDARY)
            instance_writer.write(self.list)
        return fpath, instance_writer.BOUNDARY


    def _write_xml(self, ds, fpath):
        with open(fpath, "a") as file:
            instance_writer = self.XMLDataElementWriter(file, self.BOUNDARY)
            instance_writer.write(ds)
        return fpath, instance_writer.BOUNDARY


    def end_file(self, fpath, file_format):
        if file_format in self.MULTIPART_FORMATS:
            if file_format in self.FILE_FORMATS:
                BOUNDARY = self.BOUNDARY.encode('ascii') 
                with open(fpath, "ab") as file:
                    file.write(b"--"+BOUNDARY+b"--")
            else:
                with open(fpath, "a") as file:
                    file.write("--"+self.BOUNDARY+"--")


    def start_file(self, fpath, file_format):
        if file_format in self.MULTIPART_FORMATS:
            with open(fpath, "wb") as file:
                file.write(b"")


def _write_header(file, content_type, boundary=None, binary=True):
    content = f"Content-Type: {content_type}"
    if not boundary is None:
        bound = f"; boundary={boundary}"
    else:
        bound = ""
    if binary:
        header = (content+bound).encode('ascii')
    else:
        header = (content+bound)
    file.write(header)
    file.write(b"\r\n")
    file.write(b"\r\n")

def _write_boundary(file, boundary, binary=True):
    file.write(b"\r\n")
    file.write(b"--" + boundary + b"\r\n")

def _write_dicom_header(file):
    file.write(b'\x00' * 128)
    file.write(b'DICM')



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
