"""Sorts and modifies DICOM files.

Examples:
python prepare_dicoms.py in_folder out_folder -m PatientName "Papaya^Pamela" -m PatientBirthDate "19760829"
"""
import argparse
import os
from pathlib import Path
import pydicom

parser = argparse.ArgumentParser()
parser.add_argument("input_folder", help="The DICOM input folder.")
parser.add_argument("output_folder", help="The DICOM output folder.")
parser.add_argument(
    "-a",
    "--anonymize",
    help="Anonymizes person names.",
    action="store_true",
)
parser.add_argument(
    "-m",
    "--modify_dicom_tag",
    help="Modifies a DICOM tag.",
    type=str,
    nargs=2,
    action="append",
)

args = parser.parse_args()


def person_names_callback(_, data_element):
    if data_element.VR == "PN":
        if data_element.value:
            data_element.value = "UNKNOWN^UNKNOWN"


modalities = []
for root, dirs, files in os.walk(args.input_folder):
    for file in files:
        filepath = os.path.join(root, file)
        ds = pydicom.dcmread(filepath)
        modalities.append(ds.Modality)
modalities = ",".join(sorted(list(set(modalities))))

for root, dirs, files in os.walk(args.input_folder):
    for file in files:
        filepath = os.path.join(root, file)
        ds = pydicom.dcmread(filepath)

        if args.anonymize:
            ds.walk(person_names_callback)

        if args.modify_dicom_tag:
            for modification in args.modify_dicom_tag:
                tag_to_modify = modification[0]
                value_to_assign = modification[1]
                ds[tag_to_modify].value = value_to_assign

        patient_id = ds.PatientID
        study_name = f"{ds.StudyDate}_{ds.StudyTime}_{modalities}"
        series_descr = ds.SeriesDescription
        outpath = os.path.join(args.output_folder, patient_id, study_name, series_descr)
        Path(outpath).mkdir(parents=True, exist_ok=True)
        instance_number = str(ds.InstanceNumber)
        filename = f"{instance_number.zfill(5)}.dcm"
        ds.save_as(os.path.join(outpath, filename))
