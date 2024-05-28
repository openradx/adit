import logging

logger = logging.getLogger(__name__)


class ChunkedHTTPRequestMiddleware:
    """Workaround for Django Rest Framework not handling chunked requests properly.
    This middleware sets the CONTENT_LENGTH to 1 if the request is chunked and the
    CONTENT_LENGTH is not set.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if (
            "Transfer-Encoding" in request.headers
            and request.headers["Transfer-Encoding"] == "chunked"
        ):
            if not request.META.get("CONTENT_LENGTH", None):
                request.META["CONTENT_LENGTH"] = "1"
                logger.debug("Set chunked request CONTENT_LENGTH to 1")

        response = self.get_response(request)

        return response
