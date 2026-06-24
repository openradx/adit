"""Unit tests for the DICOM string validators in ``adit/core/validators.py``.

These are pure validators (no DB), so the tests are plain functions. Each
RegexValidator raises ``django.core.exceptions.ValidationError`` on a non-match
(or, for the ``inverse_match=True`` ones, on a match).
"""

import pytest
from django.core.exceptions import ValidationError

from adit.core.validators import (
    integer_string_validator,
    letters_validator,
    no_backslash_char_validator,
    no_control_chars_validator,
    no_wildcard_chars_validator,
    uid_chars_validator,
    validate_modalities,
    validate_series_number,
    validate_series_numbers,
    validate_uids,
)


class TestLettersValidator:
    @pytest.mark.parametrize("value", ["", "abc", "ABC", "aBcDe"])
    def test_accepts_letters(self, value):
        letters_validator(value)  # must not raise

    @pytest.mark.parametrize("value", ["abc1", "a b", "a-b", "ä"])
    def test_rejects_non_letters(self, value):
        with pytest.raises(ValidationError):
            letters_validator(value)


class TestIntegerStringValidator:
    @pytest.mark.parametrize("value", ["0", "123", "-5", "+7", "  42  "])
    def test_accepts_integer_strings(self, value):
        integer_string_validator(value)

    @pytest.mark.parametrize("value", ["", "1.5", "abc", "1a", "--3"])
    def test_rejects_non_integer_strings(self, value):
        with pytest.raises(ValidationError):
            integer_string_validator(value)


class TestNoBackslashValidator:
    @pytest.mark.parametrize("value", ["abc", "1.2.3", "no backslash here"])
    def test_accepts_without_backslash(self, value):
        no_backslash_char_validator(value)

    def test_rejects_backslash(self):
        with pytest.raises(ValidationError):
            no_backslash_char_validator("a\\b")


class TestNoControlCharsValidator:
    @pytest.mark.parametrize("value", ["abc", "1.2.3", "tab\tok"])
    def test_accepts_without_control_chars(self, value):
        # Note: only \f, \n, \r are rejected; a tab is allowed.
        no_control_chars_validator(value)

    @pytest.mark.parametrize("value", ["a\nb", "a\rb", "a\fb"])
    def test_rejects_control_chars(self, value):
        with pytest.raises(ValidationError):
            no_control_chars_validator(value)


class TestNoWildcardCharsValidator:
    @pytest.mark.parametrize("value", ["abc", "1.2.3"])
    def test_accepts_without_wildcards(self, value):
        no_wildcard_chars_validator(value)

    @pytest.mark.parametrize("value", ["a*b", "a?b"])
    def test_rejects_wildcards(self, value):
        with pytest.raises(ValidationError):
            no_wildcard_chars_validator(value)


class TestUidCharsValidator:
    @pytest.mark.parametrize("value", ["1.2.3", "1.2.840.113619", "123"])
    def test_accepts_uid_chars(self, value):
        uid_chars_validator(value)

    @pytest.mark.parametrize("value", ["1.2.a", "1-2-3", "1 2", "abc"])
    def test_rejects_non_uid_chars(self, value):
        with pytest.raises(ValidationError):
            uid_chars_validator(value)


class TestValidateUids:
    def test_accepts_valid_uid_list(self):
        validate_uids(["1.2.3", "1.2.840.113619"])

    def test_accepts_empty_list(self):
        validate_uids([])

    def test_rejects_too_long_uid(self):
        with pytest.raises(ValidationError, match="too long"):
            validate_uids(["1" + "." * 64])  # 65 chars

    def test_accepts_uid_exactly_64_chars(self):
        uid = "1" * 64
        validate_uids([uid])

    def test_rejects_invalid_char_in_uid(self):
        with pytest.raises(ValidationError, match="Invalid character"):
            validate_uids(["1.2.abc"])

    def test_rejects_when_any_uid_invalid(self):
        with pytest.raises(ValidationError):
            validate_uids(["1.2.3", "bad-uid"])


class TestValidateModalities:
    @pytest.mark.parametrize("value", ["CT", "CT,MR", "CT, MR , US"])
    def test_accepts_valid_modalities(self, value):
        validate_modalities(value)

    def test_rejects_non_alpha_modality(self):
        with pytest.raises(ValidationError, match="Invalid modality"):
            validate_modalities("CT,1MR")

    def test_rejects_too_long_modality(self):
        with pytest.raises(ValidationError, match="Invalid modality"):
            validate_modalities("A" * 17)


class TestValidateSeriesNumber:
    @pytest.mark.parametrize("value", ["0", "123", "-5", str(2**31 - 1), str(-(2**31))])
    def test_accepts_in_range(self, value):
        validate_series_number(value)

    @pytest.mark.parametrize("value", [str(2**31), str(-(2**31) - 1)])
    def test_rejects_out_of_range(self, value):
        with pytest.raises(ValidationError, match="Invalid series number"):
            validate_series_number(value)

    @pytest.mark.parametrize("value", ["abc", "1.5", ""])
    def test_rejects_non_integer(self, value):
        with pytest.raises(ValidationError, match="Invalid series number"):
            validate_series_number(value)

    def test_rejects_non_string_type(self):
        with pytest.raises(ValidationError, match="Invalid type of series number"):
            validate_series_number(123)  # type: ignore[arg-type]


class TestValidateSeriesNumbers:
    def test_accepts_comma_separated(self):
        validate_series_numbers("1, 2, 3")

    def test_rejects_when_one_invalid(self):
        with pytest.raises(ValidationError):
            validate_series_numbers("1, abc, 3")
