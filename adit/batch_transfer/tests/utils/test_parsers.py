import string
import random
from datetime import date
from io import StringIO
import pytest
from adit.batch_transfer.utils.parsers import RequestsParser, ParserError


@pytest.fixture
def columns():
    return [
        "Row ID",
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
            "Row ID": "1",
            "Patient ID": "10002",
            "Patient Name": "Banana, Ben",
            "Birth Date": "18.02.1962",
            "Accession Number": "8374128439",
            "Study Date": "27.03.2018",
            "Modality": "CT",
            "Pseudonym": "DEDH6SVQ",
        },
        {
            "Row ID": "2",
            "Patient ID": "10004",
            "Patient Name": "Coconut, Coco",
            "Birth Date": "09.12.1976",
            "Accession Number": "54K42P2317U",
            "Study Date": "01.06.2019",
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

    requests = RequestsParser().parse(file)

    assert len(requests) == 2
    assert requests[0].patient_name == "Banana^Ben"
    assert requests[0].modality == "CT"
    assert requests[1].patient_id == "10004"
    assert requests[1].row_id == 2
    study_date = date(2019, 6, 1)
    assert requests[1].study_date == study_date
    patient_birth_date = date(1976, 12, 9)
    assert requests[1].patient_birth_date == patient_birth_date
    assert requests[1].pseudonym == "C2XJQ2AR"


def test_missing_row_id(columns, rows, create_csv_file):
    rows[0]["Row ID"] = ""
    file = create_csv_file(columns, rows)

    with pytest.raises(ParserError) as err:
        RequestsParser().parse(file)

    assert err.match(r"Row ID:.*must be an integer")


def test_invalid_row_id(columns, rows, create_csv_file):
    rows[0]["Row ID"] = "ABC"
    file = create_csv_file(columns, rows)

    with pytest.raises(ParserError) as err:
        RequestsParser().parse(file)

    assert err.match(r"Row ID:.*must be an integer")


def test_duplicate_row_id(rows, columns, create_csv_file):
    row_id = rows[0]["Row ID"]
    rows[1]["Row ID"] = row_id
    file = create_csv_file(columns, rows)

    with pytest.raises(ParserError) as err:
        RequestsParser().parse(file)

    assert err.match(r"Duplicate Row ID")


def test_valid_patient_id(rows, columns, create_csv_file, create_random_str):
    rows[0]["Patient ID"] = create_random_str(64)
    file = create_csv_file(columns, rows)

    try:
        RequestsParser().parse(file)
    except ParserError:
        pytest.fail("Unexpected ParserError with valid Patient ID.")


def test_invalid_patient_id(rows, columns, create_csv_file, create_random_str):
    rows[0]["Patient ID"] = create_random_str(65)
    file = create_csv_file(columns, rows)

    with pytest.raises(ParserError) as err:
        RequestsParser().parse(file)

    assert err.match(r"PatientID:.*at most 64")


def test_valid_patient_name(rows, columns, create_csv_file, create_random_str):
    patient_name = ", ".join([create_random_str(64) for _ in range(5)])
    rows[0]["Patient Name"] = patient_name
    file = create_csv_file(columns, rows)

    try:
        RequestsParser().parse(file)
    except ParserError:
        pytest.fail("Unexpected ParserError with valid Patient Name.")


def test_invalid_patient_name(rows, columns, create_csv_file, create_random_str):
    patient_name = ", ".join([create_random_str(64) for _ in range(5)])
    patient_name += "x"
    rows[0]["Patient Name"] = patient_name
    file = create_csv_file(columns, rows)

    with pytest.raises(ParserError) as err:
        RequestsParser().parse(file)

    assert err.match(r"PatientName:.*has at most 324")


def test_valid_patient_birth_date(rows, columns, create_csv_file):
    rows[0]["Birth Date"] = "01.01.1955"
    file = create_csv_file(columns, rows)

    try:
        RequestsParser().parse(file)
    except ParserError:
        pytest.fail("Unexpected ParserError with valid Birth Date.")


@pytest.mark.parametrize("birth_date", ["foobar", "32.01.1955"])
def test_invalid_patient_birth_date(birth_date, rows, columns, create_csv_file):
    rows[0]["Birth Date"] = birth_date
    file = create_csv_file(columns, rows)

    with pytest.raises(ParserError) as err:
        RequestsParser().parse(file)

    assert err.match(r"Birth Date: Invalid date format")


def test_valid_accession_number(rows, columns, create_csv_file, create_random_str):
    rows[0]["Accession Number"] = create_random_str(16)
    file = create_csv_file(columns, rows)

    try:
        RequestsParser().parse(file)
    except ParserError:
        pytest.fail("Unexpected ParserError with valid AccessionNumber.")


def test_invalid_accession_number(rows, columns, create_csv_file, create_random_str):
    rows[0]["Accession Number"] = create_random_str(17)
    file = create_csv_file(columns, rows)

    with pytest.raises(ParserError) as err:
        RequestsParser().parse(file)

    assert err.match(r"Accession Number:.*has at most 16")


def test_valid_modality(rows, columns, create_csv_file, create_random_str):
    rows[0]["Modality"] = create_random_str(16)
    file = create_csv_file(columns, rows)

    try:
        RequestsParser().parse(file)
    except ParserError:
        pytest.fail("Unexpected ParserError with valid Modality.")


def test_invalid_modality(rows, columns, create_csv_file, create_random_str):
    rows[0]["Modality"] = create_random_str(17)
    file = create_csv_file(columns, rows)

    with pytest.raises(ParserError) as err:
        RequestsParser().parse(file)

    assert err.match(r"Modality:.*has at most 16")


def test_valid_pseudonym(rows, columns, create_csv_file, create_random_str):
    rows[0]["Pseudonym"] = create_random_str(64)
    file = create_csv_file(columns, rows)

    try:
        RequestsParser().parse(file)
    except ParserError:
        pytest.fail("Unexpected ParserError with valid Pseudonym.")


def test_invalid_pseudonym(rows, columns, create_csv_file, create_random_str):
    rows[0]["Pseudonym"] = create_random_str(65)
    file = create_csv_file(columns, rows)

    with pytest.raises(ParserError) as err:
        RequestsParser().parse(file)

    assert err.match(r"Pseudonym:.*has at most 64")


def test_patient_identifiable(rows, columns, create_csv_file):
    rows[0]["PatientID"] = ""
    file = create_csv_file(columns, rows)

    try:
        RequestsParser().parse(file)
    except ParserError:
        pytest.fail("Unexpected ParserError with identifiable patient.")

    rows[0]["PatientID"] = "1234"
    rows[0]["PatientName"] = ""
    rows[0]["PatientBirthDate"] = ""
    file = create_csv_file(columns, rows)

    try:
        RequestsParser().parse(file)
    except ParserError:
        pytest.fail("Unexpected ParserError with identifiable patient.")


def test_patient_not_identifiable(rows, columns, create_csv_file):
    rows[0]["PatientID"] = ""
    rows[0]["PatientName"] = ""
    file = create_csv_file(columns, rows)

    with pytest.raises(ParserError) as err:
        RequestsParser().parse(file)

    assert err.match(r"patient must be identifiable")

    rows[0]["PatientID"] = ""
    rows[0]["PatientName"] = "Foo, Bar"
    rows[0]["PatientBirthDate"] = ""
    file = create_csv_file(columns, rows)

    with pytest.raises(ParserError) as err:
        RequestsParser().parse(file)

    assert err.match(r"patient must be identifiable")


def test_study_identifiable(rows, columns, create_csv_file):
    rows[0]["AccessionNumber"] = ""
    file = create_csv_file(columns, rows)

    try:
        RequestsParser().parse(file)
    except ParserError:
        pytest.fail("Unexpected ParserError with identifiable study.")

    rows[0]["AccessionNumber"] = "1234"
    rows[0]["StudyDate"] = ""
    rows[0]["Modality"] = ""

    file = create_csv_file(columns, rows)

    try:
        RequestsParser().parse(file)
    except ParserError:
        pytest.fail("Unexpected ParserError with identifiable study.")


def test_study_not_identifiable(rows, columns, create_csv_file):
    rows[0]["AccessionNumber"] = ""
    rows[0]["Modality"] = ""
    file = create_csv_file(columns, rows)

    with pytest.raises(ParserError) as err:
        RequestsParser().parse(file)

    assert err.match(r"study must be identifiable")

    rows[0]["AccesionNumber"] = ""
    rows[0]["Modality"] = "MR"
    rows[0]["StudyDate"] = ""
    file = create_csv_file(columns, rows)

    with pytest.raises(ParserError) as err:
        RequestsParser().parse(file)

    assert err.match(r"study must be identifiable")
