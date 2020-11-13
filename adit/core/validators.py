from django.core.validators import RegexValidator


no_special_chars_validator = RegexValidator(
    regex=r"[\f\n\r\\]",
    message="Contains invalid characters.",
    inverse_match=True,
)

no_wildcard_validator = RegexValidator(
    regex=r"[\*\?]",
    message="No wildcards allowed.",
    inverse_match=True,
)
