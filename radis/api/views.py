from rest_framework.views import APIView

from radis.core.tasks import process_report

from .serializers import ReportSerializer


class ReportList(APIView):
    def post(self, request, format=None):
        serializer = ReportSerializer(data=request.data, many=True)
        if serializer.is_valid():
            process_report.delay(**serializer.data, serializer="pickle")


class ReportDetail(APIView):
    def get(self, request, pk, format=None):
        # get report by report_id from vespa and return
        pass
