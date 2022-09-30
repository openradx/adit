from typing import Type
from django.test import TestCase
from dicomweb_client import DICOMwebClient

from django.http import (
    HttpResponseForbidden
)
from urllib.error import HTTPError
import requests


TOKEN = "3d97d8dbea63bb1d26c147a9affb74494d53512b"
BASE_URL = "http://localhost:8000/rest_api/"
PACS_AE_TITLE = "ORTHANC1"


# Auth tests
class AuthenticationTestCase(TestCase):

    def test_invalid_header(self):
        response = requests.get(
            BASE_URL+PACS_AE_TITLE+"/qidors/studies",
            headers = {"nonvalid": f"Token {TOKEN}"}
        )
        self.assertEqual(response.status_code, 401)

        response = requests.get(
            BASE_URL+PACS_AE_TITLE+"/qidors/studies",
            headers = {"Authentication": f"nonvalid {TOKEN}"}
        )
        self.assertEqual(response.status_code, 401)

    def test_invalid_token(self):
        response = requests.get(
            BASE_URL+PACS_AE_TITLE+"/qidors/studies",
            headers = {"Authorization": f"Token thisisnotavalidtoken"}
        )
        self.assertEqual(response.status_code, 401)

    def test_valid_token(self):
        response = requests.get(
            BASE_URL+PACS_AE_TITLE+"/qidors/studies",
            headers = {"Authorization": f"Token {TOKEN}"}
        )
        self.assertEqual(response.status_code, 200)


# Request handler tests
class RequestHandlerTestCase(TestCase):

    def test_invalid_PACS(self):
        response = requests.get(
            BASE_URL+"nonvalidpacs"+"/qidors/studies",
            headers = {"Authorization": f"Token {TOKEN}"}
        )
        self.assertEqual(response.status_code, 400)

    def test_invalid_study_uid(self):
        response = requests.get(
            BASE_URL+PACS_AE_TITLE+"/qidors/studies/invalid_study_uid/series",
            headers = {"Authorization": f"Token {TOKEN}"}
        )
        self.assertEqual(response.status_code, 404)

