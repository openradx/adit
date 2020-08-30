import string
import random
from datetime import datetime
from io import StringIO
from django.test import TestCase
from batch_transfer.utils.request_parsers import ParsingError, RequestParser


def get_header_data():
    return [
        "RequestID",
        "PatientID",
        "PatientName",
        "PatientBirthDate",
        "AccessionNumber",
        "StudyDate",
        "Modality",
        "Pseudonym",
    ]


def get_row_data():
    return [
        {
            "RequestID": "1",
            "PatientID": "10002",
            "PatientName": "Banana, Ben",
            "PatientBirthDate": "18.02.1962",
            "AccessionNumber": "8374128439",
            "StudyDate": "27.03.2018",
            "Modality": "CT",
            "Pseudonym": "DEDH6SVQ",
        },
        {
            "RequestID": "2",
            "PatientID": "10004",
            "PatientName": "Coconut, Coco",
            "PatientBirthDate": "09.12.1976",
            "AccessionNumber": "54K42P2317U",
            "StudyDate": "01.06.2019",
            "Modality": "MR",
            "Pseudonym": "C2XJQ2AR",
        },
    ]


def create_str(length):
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=length))


def create_csv_file(columns, data):
    csv_str = ""
    csv_str += ";".join(columns) + "\n"
    for row in data:
        values = []
        for column in columns:
            values.append(row[column])
        csv_str += ";".join(values) + "\n"
    return StringIO(csv_str)


class RequestParserTest(TestCase):
    def test_valid_csv_file(self):
        columns = get_header_data()
        rows = get_row_data()
        file = create_csv_file(columns, rows)

        data = RequestParser(";", ["%d.%m.%Y"]).parse(file)

        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]["PatientName"], "Banana^Ben")
        self.assertEqual(data[0]["Modality"], "CT")
        self.assertEqual(data[1]["PatientID"], "10004")
        self.assertEqual(data[1]["RequestID"], 2)
        study_date = datetime(2019, 6, 1)
        self.assertEqual(data[1]["StudyDate"], study_date)
        patient_birth_date = datetime(1976, 12, 9)
        self.assertEqual(data[1]["PatientBirthDate"], patient_birth_date)
        self.assertEqual(data[1]["Pseudonym"], "C2XJQ2AR")

    def test_missing_request_id(self):
        columns = get_header_data()
        rows = get_row_data()
        rows[0]["RequestID"] = " "
        file = create_csv_file(columns, rows)

        with self.assertRaises(ParsingError):
            RequestParser(";", ["%d.%m.%Y"]).parse(file)

    def test_invalid_request_id(self):
        columns = get_header_data()
        rows = get_row_data()
        rows[0]["RequestID"] = "ABC"
        file = create_csv_file(columns, rows)

        with self.assertRaises(ParsingError):
            RequestParser(";", ["%d.%m.%Y"]).parse(file)

    def test_duplicate_request_id(self):
        columns = get_header_data()
        rows = get_row_data()
        request_id = rows[0]["RequestID"]
        rows[1]["RequestID"] = request_id
        file = create_csv_file(columns, rows)

        with self.assertRaises(ParsingError):
            RequestParser(";", ["%d.%m.%Y"]).parse(file)

    def test_valid_patient_id(self):
        columns = get_header_data()
        rows = get_row_data()
        rows[0]["PatientID"] = create_str(64)
        file = create_csv_file(columns, rows)

        try:
            RequestParser(";", ["%d.%m.%Y"]).parse(file)
        except ParsingError:
            self.fail()

    def test_invalid_patient_id(self):
        columns = get_header_data()
        rows = get_row_data()
        rows[0]["PatientID"] = create_str(65)
        file = create_csv_file(columns, rows)

        with self.assertRaises(ParsingError):
            RequestParser(";", ["%d.%m.%Y"]).parse(file)

    def test_valid_patient_name(self):
        columns = get_header_data()
        rows = get_row_data()
        patient_name = ", ".join([create_str(64) for _ in range(5)])
        rows[0]["PatientName"] = patient_name
        file = create_csv_file(columns, rows)

        try:
            RequestParser(";", ["%d.%m.%Y"]).parse(file)
        except ParsingError:
            self.fail()

    def test_invalid_patient_name(self):
        columns = get_header_data()
        rows = get_row_data()
        patient_name = ", ".join([create_str(65) for _ in range(5)])
        rows[0]["PatientName"] = patient_name
        file = create_csv_file(columns, rows)

        with self.assertRaises(ParsingError):
            RequestParser(";", ["%d.%m.%Y"]).parse(file)

    def test_valid_patient_birth_date(self):
        columns = get_header_data()
        rows = get_row_data()
        rows[0]["PatientBirthDate"] = "01.01.1955"
        file = create_csv_file(columns, rows)

        try:
            RequestParser(";", ["%d.%m.%Y"]).parse(file)
        except ParsingError:
            self.fail()

    def test_invalid_patient_birth_date(self):
        columns = get_header_data()
        rows = get_row_data()

        rows[0]["PatientBirthDate"] = "foobar"
        file = create_csv_file(columns, rows)
        with self.assertRaises(ParsingError):
            RequestParser(";", ["%d.%m.%Y"]).parse(file)

        rows[0]["PatientBirthDate"] = "32.01.1955"
        file = create_csv_file(columns, rows)
        with self.assertRaises(ParsingError):
            RequestParser(";", ["%d.%m.%Y"]).parse(file)

    def test_valid_accession_number(self):
        columns = get_header_data()
        rows = get_row_data()
        rows[0]["AccessionNumber"] = create_str(16)
        file = create_csv_file(columns, rows)

        try:
            RequestParser(";", ["%d.%m.%Y"]).parse(file)
        except ParsingError:
            self.fail()

    def test_invalid_accession_number(self):
        columns = get_header_data()
        rows = get_row_data()
        rows[0]["AccessionNumber"] = create_str(17)
        file = create_csv_file(columns, rows)

        with self.assertRaises(ParsingError):
            RequestParser(";", ["%d.%m.%Y"]).parse(file)

    def test_valid_modality(self):
        columns = get_header_data()
        rows = get_row_data()
        rows[0]["Modality"] = create_str(16)
        file = create_csv_file(columns, rows)

        try:
            RequestParser(";", ["%d.%m.%Y"]).parse(file)
        except ParsingError:
            self.fail()

    def test_invalid_modality(self):
        columns = get_header_data()
        rows = get_row_data()
        rows[0]["Modality"] = create_str(17)
        file = create_csv_file(columns, rows)

        with self.assertRaises(ParsingError):
            RequestParser(";", ["%d.%m.%Y"]).parse(file)

    def test_valid_pseudonym(self):
        columns = get_header_data()
        rows = get_row_data()
        pseudonym = ", ".join([create_str(64) for _ in range(5)])
        rows[0]["Pseudonym"] = pseudonym
        file = create_csv_file(columns, rows)

        try:
            RequestParser(";", ["%d.%m.%Y"]).parse(file)
        except ParsingError:
            self.fail()

    def test_invalid_pseudonym(self):
        columns = get_header_data()
        rows = get_row_data()
        pseudonym = ", ".join([create_str(65) for _ in range(5)])
        rows[0]["Pseudonym"] = pseudonym
        file = create_csv_file(columns, rows)

        with self.assertRaises(ParsingError):
            RequestParser(";", ["%d.%m.%Y"]).parse(file)

    def test_patient_name_missing_when_birth_date_present(self):
        columns = get_header_data()
        rows = get_row_data()
        rows[0]["AccessionNumber"] = " "
        rows[0]["PatientID"] = " "
        rows[0]["PatientName"] = " "
        file = create_csv_file(columns, rows)

        with self.assertRaises(ParsingError):
            RequestParser(";", ["%d.%m.%Y"]).parse(file)

    def test_birth_date_missing_when_patient_name_present(self):
        columns = get_header_data()
        rows = get_row_data()
        rows[0]["AccessionNumber"] = " "
        rows[0]["PatientID"] = " "
        rows[0]["PatientBirthDate"] = " "
        file = create_csv_file(columns, rows)

        with self.assertRaises(ParsingError):
            RequestParser(";", ["%d.%m.%Y"]).parse(file)

    def test_patient_not_identifiable(self):
        columns = get_header_data()
        rows = get_row_data()
        rows[0]["AccessionNumber"] = " "
        rows[0]["PatientID"] = " "
        rows[0]["PatientName"] = " "
        rows[0]["PatientBirthDate"] = " "
        file = create_csv_file(columns, rows)

        with self.assertRaises(ParsingError):
            RequestParser(";", ["%d.%m.%Y"]).parse(file)

    def test_conflict_of_patient_id_with_patient_name_birth_date(self):
        columns = get_header_data()
        rows = get_row_data()
        patient_id = rows[0]["PatientID"]
        rows[1]["PatientID"] = patient_id
        file = create_csv_file(columns, rows)

        with self.assertRaises(ParsingError):
            RequestParser(";", ["%d.%m.%Y"]).parse(file)

    def test_conflict_of_pseudonym_with_different_patients(self):
        columns = get_header_data()
        rows = get_row_data()
        pseudonym = rows[0]["Pseudonym"]
        rows[1]["Pseudonym"] = pseudonym
        file = create_csv_file(columns, rows)

        with self.assertRaises(ParsingError):
            RequestParser(";", ["%d.%m.%Y"]).parse(file)
