from datetime import datetime

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


def validate_year_of_birth(year: int):
    currentYear = datetime.now().year
    if year > currentYear:
        raise ValidationError(f"Year of birth can't be in the future: {year}")


def validate_gender(gender: str):
    if gender not in ["F", "M"]:
        raise ValidationError(f"Invalid gender: {gender}")
