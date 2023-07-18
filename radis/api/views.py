import shortuuid
from adrf.views import APIView, Response, status

from radis.vespa_app import get_async_vespa_client

from .serializers import ReportSerializer


class ReportList(APIView):
    async def post(self, request):
        serializer = ReportSerializer(data=request.data, many=True)
        if serializer.is_valid():
            batch = []
            for fields in serializer.validated_data:
                batch.append(
                    {
                        "id": shortuuid.uuid(),
                        "fields": fields,
                    }
                )
            client = get_async_vespa_client()
            result = await client.feed_batch("radis", batch)
            return Response(result, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ReportDetail(APIView):
    async def get(self, request, pk):
        client = get_async_vespa_client()
        # TODO: I guess we have to translate this to an Http Response
        return await client.get_data("radis", pk)

    async def put(self, request, pk):
        serializer = ReportSerializer(data=request.data)
        if serializer.is_valid():
            client = get_async_vespa_client()
            result = await client.update_data("radis", pk, serializer.validated_data)
            return Response(result)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    async def delete(self, request, pk):
        client = get_async_vespa_client()
        # TODO: I guess we have to translate this to an Http Response
        return client.delete_data("radis", pk)
