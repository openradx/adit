import string
import random
from datetime import date
from io import StringIO
import pytest
from adit.batch_transfer.utils.parsers import RequestsParser, ParserError


@pytest.fixture
def columns():
    return [
        "Batch ID",
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
            "Batch ID": "1",
            "Patient ID": "10002",
            "Patient Name": "Banana, Ben",
            "Birth Date": "18.02.1962",
            "Accession Number": "8374128439",
            "Study Date": "27.03.2018",
            "Modality": "CT",
            "Pseudonym": "DEDH6SVQ",
        },
        {
            "Batch ID": "2",
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

    requests = []
    try:
        requests = RequestsParser().parse(file)
    except ParserError:
        pytest.fail("Unexpected ParserError with valid data.")

    assert len(requests) == 2
    assert requests[0].patient_name == "Banana^Ben"
    assert requests[0].modality == "CT"
    assert requests[1].patient_id == "10004"
    assert requests[1].batch_id == 2
    study_date = date(2019, 6, 1)
    assert requests[1].study_date == study_date
    patient_birth_date = date(1976, 12, 9)
    assert requests[1].patient_birth_date == patient_birth_date
    assert requests[1].pseudonym == "C2XJQ2AR"


def test_missing_batch_id(columns, rows, create_csv_file):
    rows[0]["Batch ID"] = ""
    file = create_csv_file(columns, rows)

    with pytest.raises(ParserError) as err:
        RequestsParser().parse(file)

    assert err.match(r"Invalid data on line 2")
    assert err.match(r"Batch ID - A valid integer is required")


def test_invalid_batch_id(columns, rows, create_csv_file):
    rows[0]["Batch ID"] = "ABC"
    file = create_csv_file(columns, rows)

    with pytest.raises(ParserError) as err:
        RequestsParser().parse(file)

    assert err.match(r"Invalid data on line 2 \(Batch ID ABC\)")
    assert err.match(r"Batch ID - A valid integer is required")


def test_duplicate_batch_id(rows, columns, create_csv_file):
    batch_id = rows[0]["Batch ID"]
    rows[1]["Batch ID"] = batch_id
    file = create_csv_file(columns, rows)

    with pytest.raises(ParserError) as err:
        RequestsParser().parse(file)

    assert err.match(r"Duplicate 'Batch ID': 1")


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

    assert err.match(r"Invalid data on line 2 \(Batch ID 1\)")
    assert err.match(r"Patient ID - Ensure this field has no more than 64 characters")


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

    assert err.match(r"Invalid data on line 2 \(Batch ID 1\)")
    assert err.match(
        r"Patient Name - Ensure this field has no more than 324 characters"
    )


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

    assert err.match(r"Invalid data on line 2 \(Batch ID 1\)")
    assert err.match(r"Birth Date - Date has wrong format.")


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

    assert err.match(r"Invalid data on line 2 \(Batch ID 1\)")
    assert err.match(
        r"Accession Number - Ensure this field has no more than 16 characters"
    )


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

    assert err.match(r"Invalid data on line 2 \(Batch ID 1\)")
    assert err.match(r"Modality - Ensure this field has no more than 16 characters")


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

    assert err.match(r"Invalid data on line 2 \(Batch ID 1\)")
    assert err.match(r"Pseudonym - Ensure this field has no more than 64 characters")


def test_patient_identifiable(rows, columns, create_csv_file):
    rows[0]["Patient ID"] = ""
    file = create_csv_file(columns, rows)

    try:
        RequestsParser().parse(file)
    except ParserError:
        pytest.fail("Unexpected ParserError with identifiable patient.")

    rows[0]["Patient ID"] = "1234"
    rows[0]["Patient Name"] = ""
    rows[0]["Birth Date"] = ""

    file = create_csv_file(columns, rows)

    try:
        RequestsParser().parse(file)
    except ParserError:
        pytest.fail("Unexpected ParserError with identifiable patient.")


def test_patient_not_identifiable(rows, columns, create_csv_file):
    rows[0]["Patient ID"] = ""
    rows[0]["Patient Name"] = ""
    file = create_csv_file(columns, rows)

    with pytest.raises(ParserError) as err:
        RequestsParser().parse(file)

    assert err.match(r"patient must be identifiable")

    rows[0]["Patient ID"] = ""
    rows[0]["Patient Name"] = "Foo, Bar"
    rows[0]["Birth Date"] = ""
    file = create_csv_file(columns, rows)

    with pytest.raises(ParserError) as err:
        RequestsParser().parse(file)

    assert err.match(r"A patient must be identifiable")


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
    rows[0]["Accession Number"] = ""
    rows[0]["Modality"] = ""
    file = create_csv_file(columns, rows)

    with pytest.raises(ParserError) as err:
        RequestsParser().parse(file)

    assert err.match(r"A study must be identifiable")

    rows[0]["Accesion Number"] = ""
    rows[0]["Modality"] = "MR"
    rows[0]["Study Date"] = ""
    file = create_csv_file(columns, rows)

    with pytest.raises(ParserError) as err:
        RequestsParser().parse(file)

    assert err.match(r"A study must be identifiable")
