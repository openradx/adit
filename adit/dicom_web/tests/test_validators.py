import pytest

from adit.core.validators import ValidationError
from adit.dicom_web.validators import validate_pseudonym

INVALID_PSEUDONYMS = [
    "Test\\Pseudonym1",  # Invalid due to backslash
    "Test\nPseudonym2",  # Invalid due to control character
    "Test\rPseudonym3",  # Invalid due to control character
    "Test\fPseudonym4",  # Invalid due to control character
    "Test*Pseudonym5",  # Invalid due to wildcard character
    "T" * 65,  # Invalid due to exceeding character limit
]

VALID_PSEUDONYMS = [
    "ValidPseudonym1",
    "AnotherValidPseudonym",
    "Short",
    "T" * 64,  # Exactly at the character limit
]


@pytest.mark.parametrize("invalid_pseudonym", INVALID_PSEUDONYMS)
def test_validate_pseudonym_invalid(invalid_pseudonym):
    """Test that validate_pseudonym raises ValidationError for invalid pseudonyms."""
    with pytest.raises(ValidationError):
        validate_pseudonym(invalid_pseudonym)


@pytest.mark.parametrize("valid_pseudonym", VALID_PSEUDONYMS)
def test_validate_pseudonym_valid(valid_pseudonym):
    """Test that validate_pseudonym does not raise an error for valid pseudonyms."""
    validate_pseudonym(valid_pseudonym)
