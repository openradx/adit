from django.test import TestCase
import json
import requests


TOKEN = "555240a9fc96541d5109fd4a8447c60da10f669f"
BASE_URL = "http://localhost:8000/rest_api/"
PACS_AE_TITLE = "ORTHANC1"


# Auth tests
class AuthenticationTestCase(TestCase):
    def test_invalid_header(self):
        response = requests.get(
            BASE_URL + PACS_AE_TITLE + "/qidors/studies",
            headers={"nonvalid": f"Token {TOKEN}"},
        )
        self.assertEqual(response.status_code, 401)

        response = requests.get(
            BASE_URL + PACS_AE_TITLE + "/qidors/studies",
            headers={"Authentication": f"nonvalid {TOKEN}"},
        )
        self.assertEqual(response.status_code, 401)

    def test_invalid_token(self):
        response = requests.get(
            BASE_URL + PACS_AE_TITLE + "/qidors/studies",
            headers={"Authorization": f"Token thisisnotavalidtoken"},
        )
        self.assertEqual(response.status_code, 401)

    def test_valid_token(self):
        response = requests.get(
            BASE_URL + PACS_AE_TITLE + "/qidors/studies",
            headers={"Authorization": f"Token {TOKEN}"},
        )
        self.assertEqual(response.status_code, 200)


# Request handler tests
class RequestHandlerTestCase(TestCase):
    def test_invalid_PACS(self):
        response = requests.get(
            BASE_URL + "nonvalidpacs" + "/qidors/studies",
            headers={"Authorization": f"Token {TOKEN}"},
        )
        self.assertEqual(response.status_code, 400)

    def test_invalid_study_uid(self):
        response = requests.get(
            BASE_URL + PACS_AE_TITLE + "/qidors/studies/invalid_study_uid/series",
            headers={"Authorization": f"Token {TOKEN}"},
        )
        self.assertEqual(response.status_code, 404)

    def test_invalid_media_type(self):
        response = requests.get(
            BASE_URL
            + PACS_AE_TITLE
            + "/wadors/studies/1.2.840.113845.11.1000000001951524609.20200705174419.2689474",
            headers={
                "Authorization": f"Token {TOKEN}",
                "Accept": "multipart/related; type=application/invalid_media_type",
            },
        )
        self.assertEqual(response.status_code, 406)


def get_test_result():
    test_result = [
        {
            "00080005": {"Value": ["ISO_IR 100"], "vr": "CS"}, 
            "00080020": {"Value": ["20190604"], "vr": "DA"}, 
            "00080030": {"Value": ["182823"], "vr": "TM"}, 
            "00080050": {"Value": ["0062115936"], "vr": "SH"}, 
            "00080060": {"Value": ["CT"], "vr": "CS"}, 
            "00080090": {"Value": [{"Alphabetic": "UNKNOWN^UNKNOWN"}], "vr": "PN"}, 
            "0008103E": {"Value": ["Kopf nativ  5.0  H42s"], "vr": "LO"}, 
            "00081190": {"Value": ["http://localhost/dicom-web/studies/1.2.840.113845.11.1000000001951524609.20200705182951.2689481/series/1.3.12.2.1107.5.1.4.66002.30000020070514400054400005494"], "vr": "UR"}, 
            "00100010": {"Value": [{"Alphabetic": "Apple^Annie"}], "vr": "PN"}, 
            "00100020": {"Value": ["1001"], "vr": "LO"}, "00100030": {"Value": ["19450427"], "vr": "DA"}, 
            "00100040": {"Value": ["F"], "vr": "CS"}, 
            "0020000D": {"Value": ["1.2.840.113845.11.1000000001951524609.20200705182951.2689481"], "vr": "UI"}, 
            "0020000E": {"Value": ["1.3.12.2.1107.5.1.4.66002.30000020070514400054400005494"], "vr": "UI"}, 
            "00200010": {"Value": ["RCTS"], "vr": "SH"}, "00200011": {"Value": [2], "vr": "IS"}, 
            "00201209": {"Value": [4], "vr": "IS"}}, 
        {
            "00080005": {"Value": ["ISO_IR 100"], "vr": "CS"}, 
            "00080020": {"Value": ["20190604"], "vr": "DA"}, "00080030": {"Value": ["182823"], "vr": "TM"}, 
            "00080050": {"Value": ["0062115936"], "vr": "SH"}, "00080060": {"Value": ["CT"], "vr": "CS"}, 
            "00080090": {"Value": [{"Alphabetic": "UNKNOWN^UNKNOWN"}], "vr": "PN"}, 
            "0008103E": {"Value": ["Kopf nativ  2.0  H70h"], "vr": "LO"}, 
            "00081190": {"Value": ["http://localhost/dicom-web/studies/1.2.840.113845.11.1000000001951524609.20200705182951.2689481/series/1.3.12.2.1107.5.1.4.66002.30000020070514400054400005512"], "vr": "UR"}, 
            "00100010": {"Value": [{"Alphabetic": "Apple^Annie"}], "vr": "PN"}, 
            "00100020": {"Value": ["1001"], "vr": "LO"}, 
            "00100030": {"Value": ["19450427"], "vr": "DA"}, 
            "00100040": {"Value": ["F"], "vr": "CS"}, 
            "0020000D": {"Value": ["1.2.840.113845.11.1000000001951524609.20200705182951.2689481"], "vr": "UI"}, 
            "0020000E": {"Value": ["1.3.12.2.1107.5.1.4.66002.30000020070514400054400005512"], "vr": "UI"}, 
            "00200010": {"Value": ["RCTS"], "vr": "SH"}, "00200011": {"Value": [3], "vr": "IS"}, 
            "00201209": {"Value": [4], "vr": "IS"}
        }, 
        {
            "00080005": {"Value": ["ISO_IR 100"], "vr": "CS"}, 
            "00080020": {"Value": ["20190604"], "vr": "DA"}, 
            "00080030": {"Value": ["182823"], "vr": "TM"}, 
            "00080050": {"Value": ["0062115936"], "vr": "SH"}, 
            "00080060": {"Value": ["SR"], "vr": "CS"}, 
            "00080090": {"Value": [{"Alphabetic": "UNKNOWN^UNKNOWN"}], "vr": "PN"}, 
            "0008103E": {"Value": ["FUJI Basic Text SR for HL7 Radiological Report"], "vr": "LO"}, 
            "00081190": {"Value": ["http://localhost/dicom-web/studies/1.2.840.113845.11.1000000001951524609.20200705182951.2689481/series/1.2.840.113845.11.2000000001951524609.20200705191841.1919177"], "vr": "UR"}, 
            "00100010": {"Value": [{"Alphabetic": "Apple^Annie"}], "vr": "PN"}, 
            "00100020": {"Value": ["1001"], "vr": "LO"}, 
            "00100030": {"Value": ["19450427"], "vr": "DA"}, 
            "00100040": {"Value": ["F"], "vr": "CS"}, 
            "0020000D": {"Value": ["1.2.840.113845.11.1000000001951524609.20200705182951.2689481"], "vr": "UI"}, 
            "0020000E": {"Value": ["1.2.840.113845.11.2000000001951524609.20200705191841.1919177"], "vr": "UI"}, 
            "00200010": {"vr": "SH"}, "00200011": {"Value": [999], "vr": "IS"}, 
            "00201209": {"Value": [1], "vr": "IS"}
        }, 
        {
            "00080005": {"Value": ["ISO_IR 100"], "vr": "CS"}, 
            "00080020": {"Value": ["20190604"], "vr": "DA"}, "00080030": {"Value": ["182823"], "vr": "TM"}, 
            "00080050": {"Value": ["0062115936"], "vr": "SH"}, "00080060": {"Value": ["CT"], "vr": "CS"}, 
            "00080090": {"Value": [{"Alphabetic": "UNKNOWN^UNKNOWN"}], "vr": "PN"}, 
            "0008103E": {"Value": ["Topogramm  0.6  T20f"], "vr": "LO"}, 
            "00081190": {"Value": ["http://localhost/dicom-web/studies/1.2.840.113845.11.1000000001951524609.20200705182951.2689481/series/1.3.12.2.1107.5.1.4.66002.30000020070513455668000000609"], "vr": "UR"}, 
            "00100010": {"Value": [{"Alphabetic": "Apple^Annie"}], "vr": "PN"}, 
            "00100020": {"Value": ["1001"], "vr": "LO"}, 
            "00100030": {"Value": ["19450427"], "vr": "DA"}, 
            "00100040": {"Value": ["F"], "vr": "CS"}, 
            "0020000D": {"Value": ["1.2.840.113845.11.1000000001951524609.20200705182951.2689481"], "vr": "UI"}, 
            "0020000E": {"Value": ["1.3.12.2.1107.5.1.4.66002.30000020070513455668000000609"], "vr": "UI"}, 
            "00200010": {"Value": ["RCTS"], "vr": "SH"}, "00200011": {"Value": [1], "vr": "IS"}, 
            "00201209": {"Value": [2], "vr": "IS"}
        }
    ]
    return test_result, test_result[0]["0020000D"]["Value"][0]


class QidoWadoTestCase(TestCase):
    def test_query_studies(self):
        _, test_study_uid = get_test_result()
        response = requests.get(
            BASE_URL
            + PACS_AE_TITLE
            + f"/qidors/studies/",
            headers={
                "Authorization": f"Token {TOKEN}",
            },
        )
        query_result = eval(response.text)
        result_study_uids = [
            eval(query_result[i])["0020000D"]["Value"][0] for i in range(len(query_result))
        ]
        self.assertTrue(test_study_uid in result_study_uids)

    def test_query_studies_with_filter(self):
        _, test_study_uid = get_test_result()
        response = requests.get(
            BASE_URL
            + PACS_AE_TITLE
            + f"/qidors/studies/?PatientID=1001",
            headers={
                "Authorization": f"Token {TOKEN}",
            },
        )
        query_result = eval(response.text)

        result_study_uids = [
            eval(query_result[i])["0020000D"]["Value"][0] for i in range(len(query_result))
        ]
        self.assertTrue(test_study_uid in result_study_uids)

        result_patient_ids = [
            eval(query_result[i])["00100020"]["Value"][0] for i in range(len(query_result))
        ]
        for id in result_patient_ids:
            self.assertTrue(id=="1001")

    def test_query_series(self):
        test_result, test_study_uid = get_test_result()
        response = requests.get(
            BASE_URL
            + PACS_AE_TITLE
            + f"/qidors/studies/{test_study_uid}/series/",
            headers={
                "Authorization": f"Token {TOKEN}",
            },
        )
        query_result = eval(response.text)
        test_series_uids = [
            test_result[i]["0020000E"]["Value"][0] for i in range(len(test_result))
        ]
        for i in range(len(query_result)):
            query_series = eval(query_result[i])
            self.assertTrue(
                query_series["0020000E"]["Value"][0] in test_series_uids
            )
