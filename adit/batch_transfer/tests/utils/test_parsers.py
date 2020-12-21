import string
import random
from datetime import date
from io import StringIO
import pytest
from adit.batch_transfer.utils.parsers import RequestsParser, ParserError


@pytest.fixture
def columns():
    return [
        "Row",
        "Patient ID",
        "Patient Name",
        "Birth Date",
        "Accession Number",
        "Study Date",
        "Modality",
        "Pseudonym",
    ]


@pytest.fixture
def rows():
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


@pytest.fixture
def create_random_str():
    def _create_random_str(length):
        return "".join(random.choices(string.ascii_uppercase + string.digits, k=length))

    return _create_random_str


@pytest.fixture
def create_csv_file():
    def _create_csv_file(column_data, row_data):
        csv_str = ""
        csv_str += ";".join(column_data) + "\n"
        for row in row_data:
            values = []
            for column in column_data:
                values.append(row[column])
            csv_str += ";".join(values) + "\n"
        return StringIO(csv_str)

    return _create_csv_file


def test_valid_csv_file(columns, rows, create_csv_file):
    file = create_csv_file(columns, rows)

    requests = RequestsParser(";", ["%d.%m.%Y"]).parse(file)

    assert len(requests) == 2
    assert requests[0].patient_name == "Banana^Ben"
    assert requests[0].modality == "CT"
    assert requests[1].patient_id == "10004"
    assert requests[1].row_number == 2
    study_date = date(2019, 6, 1)
    assert requests[1].study_date == study_date
    patient_birth_date = date(1976, 12, 9)
    assert requests[1].patient_birth_date == patient_birth_date
    assert requests[1].pseudonym == "C2XJQ2AR"


def test_missing_row_number(columns, rows, create_csv_file):
    rows[0]["RowNumber"] = ""
    file = create_csv_file(columns, rows)

    with pytest.raises(ParserError) as err:
        RequestsParser(";", ["%d.%m.%Y"]).parse(file)

    assert err.match(r"RowNumber:.*must be an integer")


def test_invalid_row_number(columns, rows, create_csv_file):
    rows[0]["RowNumber"] = "ABC"
    file = create_csv_file(columns, rows)

    with pytest.raises(ParserError) as err:
        RequestsParser(";", ["%d.%m.%Y"]).parse(file)

    assert err.match(r"RowNumber:.*must be an integer")


def test_duplicate_row_number(rows, columns, create_csv_file):
    row_number = rows[0]["RowNumber"]
    rows[1]["RowNumber"] = row_number
    file = create_csv_file(columns, rows)

    with pytest.raises(ParserError) as err:
        RequestsParser(";", ["%d.%m.%Y"]).parse(file)

    assert err.match(r"Duplicate RowNumber")


def test_valid_patient_id(rows, columns, create_csv_file, create_random_str):
    rows[0]["PatientID"] = create_random_str(64)
    file = create_csv_file(columns, rows)

    try:
        RequestsParser(";", ["%d.%m.%Y"]).parse(file)
    except ParserError:
        pytest.fail("Unexpected ParserError with valid PatientID.")


def test_invalid_patient_id(rows, columns, create_csv_file, create_random_str):
    rows[0]["PatientID"] = create_random_str(65)
    file = create_csv_file(columns, rows)

    with pytest.raises(ParserError) as err:
        RequestsParser(";", ["%d.%m.%Y"]).parse(file)

    assert err.match(r"PatientID:.*at most 64")


def test_valid_patient_name(rows, columns, create_csv_file, create_random_str):
    patient_name = ", ".join([create_random_str(64) for _ in range(5)])
    rows[0]["PatientName"] = patient_name
    file = create_csv_file(columns, rows)

    try:
        RequestsParser(";", ["%d.%m.%Y"]).parse(file)
    except ParserError:
        pytest.fail("Unexpected ParserError with valid PatientName.")


def test_invalid_patient_name(rows, columns, create_csv_file, create_random_str):
    patient_name = ", ".join([create_random_str(64) for _ in range(5)])
    patient_name += "x"
    rows[0]["PatientName"] = patient_name
    file = create_csv_file(columns, rows)

    with pytest.raises(ParserError) as err:
        RequestsParser(";", ["%d.%m.%Y"]).parse(file)

    assert err.match(r"PatientName:.*has at most 324")


def test_valid_patient_birth_date(rows, columns, create_csv_file):
    rows[0]["PatientBirthDate"] = "01.01.1955"
    file = create_csv_file(columns, rows)

    try:
        RequestsParser(";", ["%d.%m.%Y"]).parse(file)
    except ParserError:
        pytest.fail("Unexpected ParserError with valid PatientBirthDate.")


@pytest.mark.parametrize("birth_date", ["foobar", "32.01.1955"])
def test_invalid_patient_birth_date(birth_date, rows, columns, create_csv_file):
    rows[0]["PatientBirthDate"] = birth_date
    file = create_csv_file(columns, rows)

    with pytest.raises(ParserError) as err:
        RequestsParser(";", ["%d.%m.%Y"]).parse(file)

    assert err.match(r"PatientBirthDate: Invalid date format")


def test_valid_accession_number(rows, columns, create_csv_file, create_random_str):
    rows[0]["AccessionNumber"] = create_random_str(16)
    file = create_csv_file(columns, rows)

    try:
        RequestsParser(";", ["%d.%m.%Y"]).parse(file)
    except ParserError:
        pytest.fail("Unexpected ParserError with valid AccessionNumber.")


def test_invalid_accession_number(rows, columns, create_csv_file, create_random_str):
    rows[0]["AccessionNumber"] = create_random_str(17)
    file = create_csv_file(columns, rows)

    with pytest.raises(ParserError) as err:
        RequestsParser(";", ["%d.%m.%Y"]).parse(file)

    assert err.match(r"AccessionNumber:.*has at most 16")


def test_valid_modality(rows, columns, create_csv_file, create_random_str):
    rows[0]["Modality"] = create_random_str(16)
    file = create_csv_file(columns, rows)

    try:
        RequestsParser(";", ["%d.%m.%Y"]).parse(file)
    except ParserError:
        pytest.fail("Unexpected ParserError with valid Modality.")


def test_invalid_modality(rows, columns, create_csv_file, create_random_str):
    rows[0]["Modality"] = create_random_str(17)
    file = create_csv_file(columns, rows)

    with pytest.raises(ParserError) as err:
        RequestsParser(";", ["%d.%m.%Y"]).parse(file)

    assert err.match(r"Modality:.*has at most 16")


def test_valid_pseudonym(rows, columns, create_csv_file, create_random_str):
    rows[0]["Pseudonym"] = create_random_str(64)
    file = create_csv_file(columns, rows)

    try:
        RequestsParser(";", ["%d.%m.%Y"]).parse(file)
    except ParserError:
        pytest.fail("Unexpected ParserError with valid Pseudonym.")


def test_invalid_pseudonym(rows, columns, create_csv_file, create_random_str):
    rows[0]["Pseudonym"] = create_random_str(65)
    file = create_csv_file(columns, rows)

    with pytest.raises(ParserError) as err:
        RequestsParser(";", ["%d.%m.%Y"]).parse(file)

    assert err.match(r"Pseudonym:.*has at most 64")


def test_patient_identifiable(rows, columns, create_csv_file):
    rows[0]["PatientID"] = ""
    file = create_csv_file(columns, rows)

    try:
        RequestsParser(";", ["%d.%m.%Y"]).parse(file)
    except ParserError:
        pytest.fail("Unexpected ParserError with identifiable patient.")

    rows[0]["PatientID"] = "1234"
    rows[0]["PatientName"] = ""
    rows[0]["PatientBirthDate"] = ""
    file = create_csv_file(columns, rows)

    try:
        RequestsParser(";", ["%d.%m.%Y"]).parse(file)
    except ParserError:
        pytest.fail("Unexpected ParserError with identifiable patient.")


def test_patient_not_identifiable(rows, columns, create_csv_file):
    rows[0]["PatientID"] = ""
    rows[0]["PatientName"] = ""
    file = create_csv_file(columns, rows)

    with pytest.raises(ParserError) as err:
        RequestsParser(";", ["%d.%m.%Y"]).parse(file)

    assert err.match(r"patient must be identifiable")

    rows[0]["PatientID"] = ""
    rows[0]["PatientName"] = "Foo, Bar"
    rows[0]["PatientBirthDate"] = ""
    file = create_csv_file(columns, rows)

    with pytest.raises(ParserError) as err:
        RequestsParser(";", ["%d.%m.%Y"]).parse(file)

    assert err.match(r"patient must be identifiable")


def test_study_identifiable(rows, columns, create_csv_file):
    rows[0]["AccessionNumber"] = ""
    file = create_csv_file(columns, rows)

    try:
        RequestsParser(";", ["%d.%m.%Y"]).parse(file)
    except ParserError:
        pytest.fail("Unexpected ParserError with identifiable study.")

    rows[0]["AccessionNumber"] = "1234"
    rows[0]["StudyDate"] = ""
    rows[0]["Modality"] = ""

    file = create_csv_file(columns, rows)

    try:
        RequestsParser(";", ["%d.%m.%Y"]).parse(file)
    except ParserError:
        pytest.fail("Unexpected ParserError with identifiable study.")


def test_study_not_identifiable(rows, columns, create_csv_file):
    rows[0]["AccessionNumber"] = ""
    rows[0]["Modality"] = ""
    file = create_csv_file(columns, rows)

    with pytest.raises(ParserError) as err:
        RequestsParser(";", ["%d.%m.%Y"]).parse(file)

    assert err.match(r"study must be identifiable")

    rows[0]["AccesionNumber"] = ""
    rows[0]["Modality"] = "MR"
    rows[0]["StudyDate"] = ""
    file = create_csv_file(columns, rows)

    with pytest.raises(ParserError) as err:
        RequestsParser(";", ["%d.%m.%Y"]).parse(file)

    assert err.match(r"study must be identifiable")
