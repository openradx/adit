from rest_framework import serializers


class SearchParamsSerializer(serializers.Serializer):
    query = serializers.CharField(default="")
    page = serializers.IntegerField(min_value=1, default=1)
    per_page = serializers.IntegerField(min_value=1, max_value=100, default=25)
