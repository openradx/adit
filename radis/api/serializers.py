from rest_framework import serializers

from radis.core.validators import (
    no_backslash_char_validator,
    no_control_chars_validator,
    no_wildcard_chars_validator,
    validate_modalities,
    validate_patient_sex,
)


class ReportSerializer(serializers.Serializer):
    document_id = serializers.CharField(max_length=128)
    institutes = serializers.ListField(child=serializers.CharField())
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
    patient_birth_date = serializers.DateField()
    patient_sex = serializers.CharField(
        max_length=1,
        validators=[validate_patient_sex],
    )
    study_instance_uid = serializers.CharField(
        max_length=64,
        validators=[
            no_backslash_char_validator,
            no_control_chars_validator,
            no_wildcard_chars_validator,
        ],
    )
    accession_number = serializers.CharField(
        allow_blank=True,
        max_length=64,
        validators=[
            no_backslash_char_validator,
            no_control_chars_validator,
            no_wildcard_chars_validator,
        ],
    )
    study_description = serializers.CharField(allow_blank=True, max_length=64)
    study_datetime = serializers.DateTimeField()
    series_instance_uid = serializers.CharField(
        max_length=64,
        validators=[
            no_backslash_char_validator,
            no_control_chars_validator,
            no_wildcard_chars_validator,
        ],
    )
    modalities_in_study = serializers.ListField(
        child=serializers.CharField(),
        validators=[validate_modalities],
    )
    sop_instance_uid = serializers.CharField(
        max_length=64,
        validators=[
            no_backslash_char_validator,
            no_control_chars_validator,
            no_wildcard_chars_validator,
        ],
    )
    references = serializers.ListField(child=serializers.URLField())
    body = serializers.CharField()
