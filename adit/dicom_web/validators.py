from adit.core.validators import (
    ValidationError,
    no_backslash_char_validator,
    no_control_chars_validator,
    no_wildcard_chars_validator,
)


def validate_pseudonym(pseudonym: str) -> None:
    no_backslash_char_validator(pseudonym)
    no_control_chars_validator(pseudonym)
    no_wildcard_chars_validator(pseudonym)
    if len(pseudonym) > 64:
        raise ValidationError("Pseudonym string too long (max 64 characters).")


def validate_trial_protocol_id(trial_protocol_id: str) -> None:
    no_backslash_char_validator(trial_protocol_id)
    if len(trial_protocol_id) > 64:
        raise ValidationError("Trial protocol id string too long (max 64 characters).")


def validate_trial_protocol_name(trial_protocol_name: str) -> None:
    no_backslash_char_validator(trial_protocol_name)
    if len(trial_protocol_name) > 64:
        raise ValidationError("Trial protocol nanme string too long (max 64 characters).")
