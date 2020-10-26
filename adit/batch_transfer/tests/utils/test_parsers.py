import string
import random
from datetime import date
from io import StringIO
from django.test import TestCase
from adit.batch_transfer.utils.parsers import RequestsParser, ParsingError


def get_header_data():
    return [
        "RowNumber",
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
            "RowNumber": "1",
            "PatientID": "10002",
            "PatientName": "Banana, Ben",
            "PatientBirthDate": "18.02.1962",
            "AccessionNumber": "8374128439",
            "StudyDate": "27.03.2018",
            "Modality": "CT",
            "Pseudonym": "DEDH6SVQ",
        },
        {
            "RowNumber": "2",
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

        requests = RequestsParser(";", ["%d.%m.%Y"]).parse(file)

        self.assertEqual(len(requests), 2)
        self.assertEqual(requests[0].patient_name, "Banana^Ben")
        self.assertEqual(requests[0].modality, "CT")
        self.assertEqual(requests[1].patient_id, "10004")
        self.assertEqual(requests[1].row_number, 2)
        study_date = date(2019, 6, 1)
        self.assertEqual(requests[1].study_date, study_date)
        patient_birth_date = date(1976, 12, 9)
        self.assertEqual(requests[1].patient_birth_date, patient_birth_date)
        self.assertEqual(requests[1].pseudonym, "C2XJQ2AR")

    def test_missing_row_number(self):
        columns = get_header_data()
        rows = get_row_data()
        rows[0]["RowNumber"] = ""
        file = create_csv_file(columns, rows)

        with self.assertRaisesRegex(ParsingError, "RowNumber:.*must be an integer"):
            RequestsParser(";", ["%d.%m.%Y"]).parse(file)

    def test_invalid_row_number(self):
        columns = get_header_data()
        rows = get_row_data()
        rows[0]["RowNumber"] = "ABC"
        file = create_csv_file(columns, rows)

        with self.assertRaisesRegex(ParsingError, "RowNumber:.*must be an integer"):
            RequestsParser(";", ["%d.%m.%Y"]).parse(file)

    def test_duplicate_row_number(self):
        columns = get_header_data()
        rows = get_row_data()
        row_number = rows[0]["RowNumber"]
        rows[1]["RowNumber"] = row_number
        file = create_csv_file(columns, rows)

        with self.assertRaisesRegex(ParsingError, "Duplicate RowNumber"):
            RequestsParser(";", ["%d.%m.%Y"]).parse(file)

    def test_valid_patient_id(self):
        columns = get_header_data()
        rows = get_row_data()
        rows[0]["PatientID"] = create_str(64)
        file = create_csv_file(columns, rows)

        try:
            RequestsParser(";", ["%d.%m.%Y"]).parse(file)
        except ParsingError:
            self.fail()

    def test_invalid_patient_id(self):
        columns = get_header_data()
        rows = get_row_data()
        rows[0]["PatientID"] = create_str(65)
        file = create_csv_file(columns, rows)

        with self.assertRaisesRegex(ParsingError, "PatientID:.*at most 64"):
            RequestsParser(";", ["%d.%m.%Y"]).parse(file)

    def test_valid_patient_name(self):
        columns = get_header_data()
        rows = get_row_data()
        patient_name = ", ".join([create_str(64) for _ in range(5)])
        rows[0]["PatientName"] = patient_name
        file = create_csv_file(columns, rows)

        try:
            RequestsParser(";", ["%d.%m.%Y"]).parse(file)
        except ParsingError:
            self.fail()

    def test_invalid_patient_name(self):
        columns = get_header_data()
        rows = get_row_data()
        patient_name = ", ".join([create_str(64) for _ in range(5)])
        patient_name += "x"
        rows[0]["PatientName"] = patient_name
        file = create_csv_file(columns, rows)

        with self.assertRaisesRegex(ParsingError, "PatientName:.*has at most 324"):
            RequestsParser(";", ["%d.%m.%Y"]).parse(file)

    def test_valid_patient_birth_date(self):
        columns = get_header_data()
        rows = get_row_data()
        rows[0]["PatientBirthDate"] = "01.01.1955"
        file = create_csv_file(columns, rows)

        try:
            RequestsParser(";", ["%d.%m.%Y"]).parse(file)
        except ParsingError:
            self.fail()

    def test_invalid_patient_birth_date(self):
        columns = get_header_data()
        rows = get_row_data()

        rows[0]["PatientBirthDate"] = "foobar"
        file = create_csv_file(columns, rows)
        with self.assertRaisesRegex(
            ParsingError, "PatientBirthDate:.*invalid date format"
        ):
            RequestsParser(";", ["%d.%m.%Y"]).parse(file)

        rows[0]["PatientBirthDate"] = "32.01.1955"
        file = create_csv_file(columns, rows)
        with self.assertRaisesRegex(
            ParsingError, "PatientBirthDate:.*invalid date format"
        ):
            RequestsParser(";", ["%d.%m.%Y"]).parse(file)

    def test_valid_accession_number(self):
        columns = get_header_data()
        rows = get_row_data()
        rows[0]["AccessionNumber"] = create_str(16)
        file = create_csv_file(columns, rows)

        try:
            RequestsParser(";", ["%d.%m.%Y"]).parse(file)
        except ParsingError:
            self.fail()

    def test_invalid_accession_number(self):
        columns = get_header_data()
        rows = get_row_data()
        rows[0]["AccessionNumber"] = create_str(17)
        file = create_csv_file(columns, rows)

        with self.assertRaisesRegex(ParsingError, "AccessionNumber:.*has at most 16"):
            RequestsParser(";", ["%d.%m.%Y"]).parse(file)

    def test_valid_modality(self):
        columns = get_header_data()
        rows = get_row_data()
        rows[0]["Modality"] = create_str(16)
        file = create_csv_file(columns, rows)

        try:
            RequestsParser(";", ["%d.%m.%Y"]).parse(file)
        except ParsingError:
            self.fail()

    def test_invalid_modality(self):
        columns = get_header_data()
        rows = get_row_data()
        rows[0]["Modality"] = create_str(17)
        file = create_csv_file(columns, rows)

        with self.assertRaisesRegex(ParsingError, "Modality:.*has at most 16"):
            RequestsParser(";", ["%d.%m.%Y"]).parse(file)

    def test_valid_pseudonym(self):
        columns = get_header_data()
        rows = get_row_data()
        rows[0]["Pseudonym"] = create_str(64)
        file = create_csv_file(columns, rows)

        try:
            RequestsParser(";", ["%d.%m.%Y"]).parse(file)
        except ParsingError:
            self.fail()

    def test_invalid_pseudonym(self):
        columns = get_header_data()
        rows = get_row_data()
        rows[0]["Pseudonym"] = create_str(65)
        file = create_csv_file(columns, rows)

        with self.assertRaisesRegex(ParsingError, "Pseudonym:.*has at most 64"):
            RequestsParser(";", ["%d.%m.%Y"]).parse(file)

    def test_patient_identifiable(self):
        columns = get_header_data()
        rows = get_row_data()

        rows[0]["PatientID"] = ""
        file = create_csv_file(columns, rows)
        try:
            RequestsParser(";", ["%d.%m.%Y"]).parse(file)
        except ParsingError:
            self.fail()

        rows[0]["PatientID"] = "1234"
        rows[0]["PatientName"] = ""
        rows[0]["PatientBirthDate"] = ""
        file = create_csv_file(columns, rows)
        try:
            RequestsParser(";", ["%d.%m.%Y"]).parse(file)
        except ParsingError:
            self.fail()

    def test_patient_not_identifiable(self):
        columns = get_header_data()
        rows = get_row_data()

        rows[0]["PatientID"] = ""
        rows[0]["PatientName"] = ""
        file = create_csv_file(columns, rows)
        with self.assertRaisesRegex(ParsingError, "patient must be identifiable"):
            RequestsParser(";", ["%d.%m.%Y"]).parse(file)

        rows[0]["PatientID"] = ""
        rows[0]["PatientName"] = "Foo, Bar"
        rows[0]["PatientBirthDate"] = ""
        file = create_csv_file(columns, rows)
        with self.assertRaisesRegex(ParsingError, "patient must be identifiable"):
            RequestsParser(";", ["%d.%m.%Y"]).parse(file)

    def test_study_identifiable(self):
        columns = get_header_data()
        rows = get_row_data()

        rows[0]["AccessionNumber"] = ""
        file = create_csv_file(columns, rows)
        try:
            RequestsParser(";", ["%d.%m.%Y"]).parse(file)
        except ParsingError:
            self.fail()

        rows[0]["AccessionNumber"] = "1234"
        rows[0]["StudyDate"] = ""
        rows[0]["Modality"] = ""
        file = create_csv_file(columns, rows)
        try:
            RequestsParser(";", ["%d.%m.%Y"]).parse(file)
        except ParsingError:
            self.fail()

    def test_study_not_identifiable(self):
        columns = get_header_data()
        rows = get_row_data()

        rows[0]["AccessionNumber"] = ""
        rows[0]["Modality"] = ""
        file = create_csv_file(columns, rows)
        with self.assertRaisesRegex(ParsingError, "study must be identifiable"):
            RequestsParser(";", ["%d.%m.%Y"]).parse(file)

        rows[0]["AccesionNumber"] = ""
        rows[0]["Modality"] = "MR"
        rows[0]["StudyDate"] = ""
        file = create_csv_file(columns, rows)
        with self.assertRaisesRegex(ParsingError, "study must be identifiable"):
            RequestsParser(";", ["%d.%m.%Y"]).parse(file)
