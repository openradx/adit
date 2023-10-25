from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator

letters_validator = RegexValidator(r"^[a-zA-Z]*$", "Only letters A-Z are allowed.")

# Series Number uses a Value Representation (VR) of Integer String (IS)
# https://dicom.nema.org/dicom/2013/output/chtml/part05/sect_6.2.html
integer_string_validator = RegexValidator(
    r"^\s*[-+]?[0-9]+\s*$", "Invalid string representation of a number."
)

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

uid_chars_validator = RegexValidator(regex=r"^[\d\.]+$", message="Invalid character in UID.")


def validate_uids(value: list[str]) -> None:
    for uid in value:
        if len(uid) > 64:
            raise ValidationError("UID string too long (max 64 characters).")

        uid_chars_validator(uid)


###
# Unused validators that are only used in old migrations.
# TODO: Delete them after squashing migrations.
###


def validate_modalities(value: str) -> None:
    modalities = map(str.strip, value.split(","))
    for modality in modalities:
        if not modality.isalpha() or len(modality) > 16:
            raise ValidationError(f"Invalid modality: {modality}")


def validate_series_numbers(value: str) -> None:
    series_numbers = map(str.strip, value.split(","))
    for series_number in series_numbers:
        validate_series_number(series_number)


def validate_series_number(value: str) -> None:
    if not isinstance(value, str):
        raise ValidationError(f"Invalid type of series number: {value} [{type(value)}]")

    try:
        snr = int(value)
        if snr < -(2**31) or snr > 2**31 - 1:
            raise ValueError()
    except ValueError:
        raise ValidationError(f"Invalid series number: {value}")
