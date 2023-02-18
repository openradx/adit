import datetime
from urllib.parse import urlencode
import pytest
from dicomweb_client.api import DICOMwebClient
from adit.accounts.factories import UserFactory
from adit.accounts.models import Group
from adit.core.factories import DicomServerFactory
from adit.token_authentication.models import RestAuthToken


@pytest.fixture
def test_pacs_ae_title():
    return "TESTSERVER"


@pytest.fixture
def dicom_server(db):
    dicom_server = DicomServerFactory()
    return dicom_server.ae_title


@pytest.fixture
def token_data(db):
    return urlencode(
        {
            "expiry_time": 1,
            "client": "Test Client",
        }
    )


@pytest.fixture
def user_with_permission(db):
    user = UserFactory()
    token_authentication_group = Group.objects.get(name="token_authentication_group")
    user.groups.add(token_authentication_group)
    return user


@pytest.fixture
def token(db, client, token_data, user_with_permission):
    token = RestAuthToken.objects.create_token(
        user=user_with_permission,
        client="test client",
        expiry_time=datetime.datetime.now() + datetime.timedelta(hours=1),
    )
    return str(token)


@pytest.fixture
def dicom_web_client():
    return DICOMwebClient(
        url="http://localhost:8000/rest_api/ORTHANC1",
        qido_url_prefix="qidors",
        wado_url_prefix="wadors",
        headers={"Authorization": "Token 7350ddda0a2efca30fa5e09088b8fddf2878fe20"},
    )


@pytest.fixture
def orthanc1_test_patient_ids():
    return ["1001", "1002", "1003", "1004", "1005", "1006", "1007", "1008"]


@pytest.fixture
def orthanc1_test_study_uids():
    return [
        "1.2.840.113845.11.1000000001951524609.20200705174649.2689475",
        "1.2.840.113845.11.1000000001951524609.20200705170836.2689469",
        "1.2.840.113845.11.1000000001951524609.20200705163958.2689467",
        "1.2.840.113845.11.1000000001951524609.20200705173311.2689472",
        "1.2.840.113845.11.1000000001951524609.20200705182951.2689481",
        "1.2.840.113845.11.1000000001951524609.20200705161257.2689463",
        "1.2.840.113845.11.1000000001951524609.20200705150256.2689458",
        "1.2.840.113845.11.1000000001951524609.20200705184633.2689482",
        "1.2.840.113845.11.1000000001951524609.20200705172608.2689471",
        "1.2.840.113845.11.1000000001951524609.20200705174419.2689474",
    ]


@pytest.fixture
def orthanc1_test_study_with_series_uids():
    return (
        "1.2.840.113845.11.1000000001951524609.20200705182951.2689481",
        [
            "1.3.12.2.1107.5.1.4.66002.30000020070513455668000000609",
            "1.3.12.2.1107.5.1.4.66002.30000020070514400054400005494",
            "1.3.12.2.1107.5.1.4.66002.30000020070514400054400005512",
            "1.2.840.113845.11.2000000001951524609.20200705191841.1919177",
        ],
    )
