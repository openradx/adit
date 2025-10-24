"""Tests for retry configuration module."""

from unittest.mock import patch

import pytest
from requests import HTTPError, Response

from adit.core.errors import DicomError, RetriableDicomError, is_retriable_http_status
from adit.core.utils.retry_config import (
    RETRY_CONFIG,
    create_retry_decorator,
    get_retry_config,
    retry_dimse_connect,
    retry_dimse_find,
)


class TestRetryConfig:
    """Test retry configuration retrieval."""

    def test_get_retry_config_valid_operation(self):
        """Test that valid operation types return correct configuration."""
        config = get_retry_config("dimse_find")
        assert config["attempts"] == 8
        assert config["timeout"] == 120.0
        assert config["wait_initial"] == 1.0
        assert config["wait_max"] == 20.0
        assert config["wait_jitter"] == 2.0

    def test_get_retry_config_all_operations(self):
        """Test that all defined operation types have valid configurations."""
        for operation_type in RETRY_CONFIG.keys():
            config = get_retry_config(operation_type)
            assert "attempts" in config
            assert "timeout" in config
            assert "wait_initial" in config
            assert "wait_max" in config
            assert "wait_jitter" in config
            assert config["attempts"] > 0
            assert config["timeout"] > 0

    def test_get_retry_config_invalid_operation(self):
        """Test that invalid operation type raises ValueError."""
        with pytest.raises(ValueError, match="Unknown operation type"):
            get_retry_config("invalid_operation")

    @patch("adit.core.utils.retry_config.settings.ENABLE_DICOM_DEBUG_LOGGER", True)
    def test_get_retry_config_debug_mode(self):
        """Test that debug mode reduces retry attempts."""
        config = get_retry_config("dimse_find")
        # In debug mode, attempts should be limited to 3
        assert config["attempts"] == 3

    @patch("adit.core.utils.retry_config.settings.ENABLE_DICOM_DEBUG_LOGGER", False)
    def test_get_retry_config_normal_mode(self):
        """Test normal mode uses full retry attempts."""
        config = get_retry_config("dimse_find")
        # In normal mode, use configured attempts
        assert config["attempts"] == 8


class TestRetryDecorators:
    """Test retry decorator functionality."""

    @patch("adit.core.utils.retry_config.settings.ENABLE_STAMINA_RETRY", True)
    def test_decorator_retries_on_retriable_error(self):
        """Test that RetriableDicomError triggers retry."""
        call_count = 0

        @retry_dimse_connect
        def failing_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RetriableDicomError("Temporary failure")
            return "success"

        result = failing_function()
        assert result == "success"
        assert call_count == 3

    @patch("adit.core.utils.retry_config.settings.ENABLE_STAMINA_RETRY", True)
    def test_decorator_retries_on_connection_error(self):
        """Test that ConnectionError triggers retry."""
        call_count = 0

        @retry_dimse_connect
        def failing_function():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("Connection refused")
            return "success"

        result = failing_function()
        assert result == "success"
        assert call_count == 2

    @patch("adit.core.utils.retry_config.settings.ENABLE_STAMINA_RETRY", True)
    def test_decorator_no_retry_on_permanent_error(self):
        """Test that DicomError does not trigger retry."""
        call_count = 0

        @retry_dimse_find
        def failing_function():
            nonlocal call_count
            call_count += 1
            raise DicomError("Permanent failure")

        with pytest.raises(DicomError):
            failing_function()

        # Should only be called once (no retries)
        assert call_count == 1

    @patch("adit.core.utils.retry_config.settings.ENABLE_STAMINA_RETRY", False)
    def test_decorator_disabled_when_stamina_disabled(self):
        """Test that decorator is a no-op when stamina is disabled."""
        call_count = 0

        # Need to re-create the decorator with the new setting
        decorator = create_retry_decorator("dimse_connect")

        @decorator
        def failing_function():
            nonlocal call_count
            call_count += 1
            raise RetriableDicomError("Should not retry")

        with pytest.raises(RetriableDicomError):
            failing_function()

        # Should only be called once (stamina disabled)
        assert call_count == 1


class TestRetryConfiguration:
    """Test specific retry configurations for different operations."""

    def test_dimse_connect_config(self):
        """Test DIMSE connection retry configuration."""
        config = get_retry_config("dimse_connect")
        assert config["attempts"] == 5
        assert config["timeout"] == 60.0

    def test_dimse_find_config(self):
        """Test DIMSE find retry configuration."""
        config = get_retry_config("dimse_find")
        assert config["attempts"] == 8
        assert config["timeout"] == 120.0

    def test_dimse_retrieve_config(self):
        """Test DIMSE retrieve (C-GET, C-MOVE) retry configuration."""
        config = get_retry_config("dimse_retrieve")
        assert config["attempts"] == 5
        assert config["timeout"] == 300.0

    def test_dimse_store_config(self):
        """Test DIMSE store retry configuration."""
        config = get_retry_config("dimse_store")
        assert config["attempts"] == 10
        assert config["timeout"] == 180.0

    def test_dicomweb_search_config(self):
        """Test DICOMweb search (QIDO-RS) retry configuration."""
        config = get_retry_config("dicomweb_search")
        assert config["attempts"] == 8
        assert config["timeout"] == 120.0

    def test_dicomweb_retrieve_config(self):
        """Test DICOMweb retrieve (WADO-RS) retry configuration."""
        config = get_retry_config("dicomweb_retrieve")
        assert config["attempts"] == 5
        assert config["timeout"] == 300.0

    def test_dicomweb_store_config(self):
        """Test DICOMweb store (STOW-RS) retry configuration."""
        config = get_retry_config("dicomweb_store")
        assert config["attempts"] == 10
        assert config["timeout"] == 180.0

    def test_dicomweb_decorator_converts_retriable_http_error(self):
        """Test that DICOMweb decorators convert retriable HTTPErrors to RetriableDicomError."""
        decorator = create_retry_decorator("dicomweb_search")

        # Create a mock HTTP 503 error
        response = Response()
        response.status_code = 503
        http_error = HTTPError()
        http_error.response = response

        @decorator
        def failing_dicomweb_operation():
            raise http_error

        # Should convert HTTPError to RetriableDicomError and retry
        with pytest.raises(RetriableDicomError) as exc_info:
            failing_dicomweb_operation()

        # Verify it was converted from HTTPError
        assert exc_info.value.__cause__ == http_error

    def test_dicomweb_decorator_does_not_convert_permanent_http_error(self):
        """Test that DICOMweb decorators don't convert permanent HTTPErrors."""
        decorator = create_retry_decorator("dicomweb_search")

        # Create a mock HTTP 404 error (not retriable)
        response = Response()
        response.status_code = 404
        http_error = HTTPError()
        http_error.response = response

        @decorator
        def failing_dicomweb_operation():
            raise http_error

        # Should not convert, HTTPError should propagate unchanged
        with pytest.raises(HTTPError) as exc_info:
            failing_dicomweb_operation()

        assert exc_info.value == http_error

    def test_dicomweb_decorator_handles_generator_http_errors(self):
        """Test that DICOMweb decorators handle HTTPErrors in generators."""
        decorator = create_retry_decorator("dicomweb_retrieve")

        # Create a mock HTTP 503 error
        response = Response()
        response.status_code = 503
        http_error = HTTPError()
        http_error.response = response

        @decorator
        def failing_generator():
            yield 1
            yield 2
            raise http_error

        # Should convert HTTPError during iteration
        gen = failing_generator()
        assert next(gen) == 1
        assert next(gen) == 2

        with pytest.raises(RetriableDicomError) as exc_info:
            next(gen)

        # Verify it was converted from HTTPError
        assert exc_info.value.__cause__ == http_error

    def test_dimse_decorator_does_not_convert_http_errors(self):
        """Test that DIMSE decorators don't convert HTTPErrors (only DICOMweb does)."""
        decorator = create_retry_decorator("dimse_find")

        # Create a mock HTTP 503 error
        response = Response()
        response.status_code = 503
        http_error = HTTPError()
        http_error.response = response

        @decorator
        def failing_dimse_operation():
            raise http_error

        # DIMSE decorator should not convert HTTPError
        with pytest.raises(HTTPError) as exc_info:
            failing_dimse_operation()

        assert exc_info.value == http_error


class TestHttpStatusRetriability:
    """Test HTTP status code retriability checking."""

    def test_retriable_status_codes(self):
        """Test that retriable HTTP status codes are correctly identified."""
        retriable_codes = [408, 409, 429, 500, 503, 504]
        for code in retriable_codes:
            assert is_retriable_http_status(code), f"Status {code} should be retriable"

    def test_non_retriable_status_codes(self):
        """Test that non-retriable HTTP status codes are correctly identified."""
        non_retriable_codes = [200, 201, 400, 401, 403, 404, 405, 422]
        for code in non_retriable_codes:
            assert not is_retriable_http_status(code), f"Status {code} should not be retriable"
