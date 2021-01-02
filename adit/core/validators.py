from django.core.validators import RegexValidator
from django.core.exceptions import ValidationError

no_backslash_char_validator = RegexValidator(
    regex=r"\\",
    message="Contains invalid backslash character",
    inverse_match=True,
)


no_control_chars_validator = RegexValidator(
    regex=r"[\f\n\r]",
    message="Contains invalid control characters.",
    inverse_match=True,
)

no_wildcard_chars_validator = RegexValidator(
    regex=r"[\*\?]",
    message="Contains invalid wildcard characters.",
    inverse_match=True,
)


def validate_uid_list(value):
    if not isinstance(value, list):
        raise ValidationError(f"Invalid {value} UIDs type: {type(value)}")

    for uid in value:
        if not isinstance(uid, str):
            raise ValidationError(f"Invalid {uid} UID type: {type(uid)}")

        if len(uid) > 64:
            raise ValidationError(f"UID string too long: {uid}")

        no_backslash_char_validator(uid)
        no_control_chars_validator(uid)
        no_wildcard_chars_validator(uid)


def validate_modalities(value):
    if not isinstance(value, list):
        raise ValidationError(f"Invalid {value} modalities type: {type(value)}")

    for modality in value:
        if not isinstance(modality, str):
            raise ValidationError(f"Invalid {modality} modality type: {type(modality)}")

        if len(modality) > 16:
            raise ValidationError(f"Modality string too long: {modality}")

        no_backslash_char_validator(modality)
        no_control_chars_validator(modality)
        no_wildcard_chars_validator(modality)
