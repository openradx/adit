import chunk
from django.db import models
import os

# WADO-RS   
class DicomStudyResponseBodyWriter():
    BOUNDARY = b"adit-boundary"
    CONTENT_TYPE = "application/dicom"
    def write(self, study, binary_file):
        with open(binary_file, "wb") as file:
            for instance in study:
                file.write(b"--" + self.BOUNDARY + b"\r\n")
                file.write(b"Content-Type: application/dicom" + b"\r\n")

                instance = open(instance, "rb")
                while True:
                    chunk = instance.read(1024)
                    if not chunk:
                        break
                    file.write(chunk)

                file.write(b"\r\n")
        
            file.write(b"--" + self.BOUNDARY + b"--")
        
        return binary_file, self.BOUNDARY
            
