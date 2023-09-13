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


def validate_modalities(value: str) -> None:
    modalities = map(str.strip, value.split(","))
    for modality in modalities:
        if not modality.isalpha() or len(modality) > 16:
            raise ValidationError(f"Invalid modality: {modality}")
