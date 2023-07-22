from typing import Any

import shortuuid
from adrf.views import APIView, Response, status
from vespa.io import VespaResponse

from radis.core.vespa_app import vespa_app

from .serializers import ReportSerializer


def adjust_fields(fields: dict[str, Any]):
    # Vespa can't store datetimes natively, so we store it as a number,
    # see schema in vespa_app.py
    fields["study_datetime"] = int(fields["study_datetime"].timestamp())


class ReportList(APIView):
    async def post(self, request):
        serializer = ReportSerializer(data=request.data)
        if serializer.is_valid():
            fields = serializer.validated_data
            adjust_fields(fields)

            async with vespa_app.get_client().asyncio() as client:
                response = await client.feed_data_point("radis", shortuuid.uuid(), fields)
            if response.get_status_code() != status.HTTP_200_OK:
                return Response(response.get_json(), status=response.get_status_code())
            return Response(response.get_json(), status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ReportDetail(APIView):
    async def get(self, request, pk):
        async with vespa_app.get_client().asyncio() as client:
            response: VespaResponse = await client.get_data("radis", pk)
        return Response(response.get_json(), status=response.get_status_code())

    async def put(self, request, pk):
        serializer = ReportSerializer(data=request.data)
        if serializer.is_valid():
            fields = serializer.validated_data
            adjust_fields(fields)

            async with vespa_app.get_client().asyncio() as client:
                response = await client.update_data("radis", pk, fields)
            return Response(response.get_json(), response.get_status_code())
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    async def delete(self, request, pk):
        async with vespa_app.get_client().asyncio() as client:
            response = await client.delete_data("radis", pk)
        return Response(response.get_json(), response.get_status_code())
