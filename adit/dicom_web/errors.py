from rest_framework.exceptions import APIException


class RemoteServerError(APIException):
    status_code = 503
