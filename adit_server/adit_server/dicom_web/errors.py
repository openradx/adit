from rest_framework.exceptions import APIException


class BadGatewayApiError(APIException):
    status_code = 502


# The 503 error code (in contrast to 502) will be retried by the ADIT client (or better to
# say by the dicomweb-client which is used internally).
# https://dicomweb-client.readthedocs.io/en/latest/package.html#dicomweb_client.api.DICOMwebClient.set_http_retry_params
class ServiceUnavailableApiError(APIException):
    status_code = 503
