from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator

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


def validate_modalities(value: list[str]) -> None:
    modalities = map(str.strip, value)
    for modality in modalities:
        if not modality.isalpha() or len(modality) > 16:
            raise ValidationError(f"Invalid modality: {modality}")


def validate_patient_sex(patient_sex: str):
    if patient_sex not in ["F", "M", "U"]:
        raise ValidationError(f"Invalid patient sex: {patient_sex}")
