from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator

pos_int_list_validator = RegexValidator(
    regex=r"^\s*\d+(?:\s*,\s*\d+)*\s*\Z",
    message="Enter only digits separated by commas.",
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


def validate_uids(value: str) -> None:
    uids = map(str.strip, value.split(","))
    for uid in uids:
        if len(uid) > 64:
            raise ValidationError("UID string too long (max 64 characters).")

        uid_chars_validator(uid)


def validate_modalities(value: str) -> None:
    modalities = map(str.strip, value.split(","))
    for modality in modalities:
        if not modality.isalpha() or len(modality) > 16:
            raise ValidationError(f"Invalid modality: {modality}")


def validate_series_number(value: str) -> None:
    # Series Number uses a Value Representation (VR) of Integer String (IS)
    # https://dicom.nema.org/dicom/2013/output/chtml/part05/sect_6.2.html
    if not isinstance(value, str):
        raise ValidationError(f"Invalid type of series number: {value} [{type(value)}]")

    try:
        snr = int(value)
        if snr < -(2**31) or snr > 2**31 - 1:
            raise ValueError()
    except ValueError:
        raise ValidationError(f"Invalid series number: {value}")


def validate_series_numbers(value: str) -> None:
    series_numbers = map(str.strip, value.split(","))
    for series_number in series_numbers:
        validate_series_number(series_number)
