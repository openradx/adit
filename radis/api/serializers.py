from rest_framework import serializers

from radis.core.validators import (
    no_backslash_char_validator,
    no_control_chars_validator,
    no_wildcard_chars_validator,
)


class ReportSerializer(serializers.Serializer):
    pacs_aet = serializers.CharField(max_length=16)
    pacs_name = serializers.CharField(max_length=64)
    patient_id = serializers.CharField(
        max_length=64,
        validators=[
            no_backslash_char_validator,
            no_control_chars_validator,
            no_wildcard_chars_validator,
        ],
    )
    study_uid = serializers.CharField(
        max_length=64,
        validators=[
            no_backslash_char_validator,
            no_control_chars_validator,
            no_wildcard_chars_validator,
        ],
    )
    accession_number = serializers.CharField(
        max_length=64,
        validators=[
            no_backslash_char_validator,
            no_control_chars_validator,
            no_wildcard_chars_validator,
        ],
        required=False,
    )
    study_description = serializers.CharField(max_length=64)
    study_datetime = serializers.DateTimeField()
    series_uid = serializers.CharField(
        max_length=64,
        validators=[
            no_backslash_char_validator,
            no_control_chars_validator,
            no_wildcard_chars_validator,
        ],
    )
    modalities = serializers.ListField(child=serializers.CharField())
    instance_uid = serializers.CharField(
        max_length=64,
        validators=[
            no_backslash_char_validator,
            no_control_chars_validator,
            no_wildcard_chars_validator,
        ],
    )
    references = serializers.ListField(child=serializers.URLField())
    content = serializers.CharField()
