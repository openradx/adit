from django.test import TestCase

import requests


TOKEN = "67de33da68eb68cd46416c8d2e4d4535e9c2b9cc"
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
