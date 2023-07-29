import logging
from typing import Any

import shortuuid
from adrf.views import APIView, Response, status
from django.urls import reverse
from rest_framework.request import Request

from radis.core.utils.report_utils import extract_doc_id
from radis.core.vespa_app import vespa_app

from .serializers import ReportSerializer

logger = logging.getLogger(__name__)


def adjust_fields(fields: dict[str, Any]):
    # Vespa can't store datetimes natively, so we store it as a number,
    # see schema in vespa_app.py
    fields["study_datetime"] = int(fields["study_datetime"].timestamp())


class ReportListAPIView(APIView):
    async def post(self, request: Request):
        serializer = ReportSerializer(data=request.data)
        if serializer.is_valid():
            fields = serializer.validated_data
            adjust_fields(fields)

            async with vespa_app.get_client().asyncio() as client:
                response = await client.feed_data_point("report", shortuuid.uuid(), fields)
            result = response.get_json()
            if response.get_status_code() != status.HTTP_200_OK:
                logger.error("Error while feeding Vespa: %s", result)
                return Response(
                    result.get("message", "Unknown error."),
                    status=response.get_status_code(),
                )

            id = extract_doc_id(result["id"])
            path = reverse("report_detail", args=[id])
            return Response({"id": id, "path": path}, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ReportDetailAPIView(APIView):
    async def get(self, request: Request, doc_id: str):
        async with vespa_app.get_client().asyncio() as client:
            response = await client.get_data("report", doc_id)
        return Response(response.get_json(), status=response.get_status_code())

    async def put(self, request, doc_id: str):
        serializer = ReportSerializer(data=request.data)
        if serializer.is_valid():
            fields = serializer.validated_data
            adjust_fields(fields)

            async with vespa_app.get_client().asyncio() as client:
                response = await client.update_data("report", doc_id, fields)
            return Response(response.get_json(), response.get_status_code())
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    async def delete(self, request: Request, doc_id: str):
        async with vespa_app.get_client().asyncio() as client:
            response = await client.delete_data("report", doc_id)
        return Response(response.get_json(), response.get_status_code())
