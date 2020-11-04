from django.core.exceptions import ValidationError


def validate_pseudonym(pseudonym):
    """Validate a given pseudonym.

    A pseudonym is a string with LO (Long String) as value representation (VR)
    as it is used by ADIT for PatientID (also LO) and PatientName (PN).
    """
    if not str.isprintable(pseudonym) or "\\" in pseudonym:
        raise ValidationError("Invalid pseudonym.")
