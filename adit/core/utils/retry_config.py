"""Stamina retry configuration for DICOM network operations.

This module provides retry strategies for network-level operations only.
Higher-level operations (Operator, Processor) do not retry and let errors
propagate to the Procrastinate task retry mechanism.

Architecture:
-----------
ADIT uses a single-layer retry strategy:

1. Network Layer (Stamina): Fast retries for transient failures
   - DIMSE operations (C-FIND, C-GET, C-MOVE, C-STORE)
   - DICOMweb operations (QIDO-RS, WADO-RS, STOW-RS)
   - Retries: 5-10 attempts with exponential backoff + jitter
   - Timeout: 60-300 seconds depending on operation

2. Task Layer (Procrastinate): Slow retries for complete failures
   - Retries entire transfer task if network layer exhausted
   - Retries: 3 attempts with exponential backoff
   - Wait: 60 seconds base (1min → 2min → 4min)

Why single-layer?
----------------
- Avoids retry multiplication (8 network × 3 task = 24 total)
- Predictable execution time
- Clear separation: transient (stamina) vs permanent (procrastinate)
- Simple debugging

Retry Decision Tree:
------------------
Network error occurs
  ↓
Is it retriable? (ConnectionError, RetriableDicomError, HTTP 503, etc.)
  ├─ YES → Stamina retries (fast, exponential backoff)
  │   ├─ Success → Continue
  │   └─ Exhausted → Raise to Procrastinate
  │       ├─ Procrastinate retry (wait 60s+)
  │       └─ Still failing → Task FAILURE
  └─ NO → Raise immediately (DicomError)
      → Task FAILURE (no retries)
"""

from typing import Any

import stamina
from django.conf import settings

from ..errors import RetriableDicomError

# Retry configuration for different operation types
RETRY_CONFIG = {
    # DIMSE operations
    "dimse_connect": {
        "attempts": 5,
        "timeout": 60.0,
        "wait_initial": 1.0,
        "wait_max": 10.0,
        "wait_jitter": 1.0,
    },
    "dimse_find": {
        "attempts": 8,
        "timeout": 120.0,
        "wait_initial": 1.0,
        "wait_max": 20.0,
        "wait_jitter": 2.0,
    },
    "dimse_retrieve": {  # C-GET, C-MOVE
        "attempts": 5,
        "timeout": 300.0,
        "wait_initial": 2.0,
        "wait_max": 30.0,
        "wait_jitter": 3.0,
    },
    "dimse_store": {
        "attempts": 10,
        "timeout": 180.0,
        "wait_initial": 1.0,
        "wait_max": 25.0,
        "wait_jitter": 2.5,
    },
    # DICOMweb operations
    "dicomweb_search": {  # QIDO-RS
        "attempts": 8,
        "timeout": 120.0,
        "wait_initial": 1.0,
        "wait_max": 20.0,
        "wait_jitter": 2.0,
    },
    "dicomweb_retrieve": {  # WADO-RS
        "attempts": 5,
        "timeout": 300.0,
        "wait_initial": 2.0,
        "wait_max": 30.0,
        "wait_jitter": 3.0,
    },
    "dicomweb_store": {  # STOW-RS
        "attempts": 10,
        "timeout": 180.0,
        "wait_initial": 1.0,
        "wait_max": 25.0,
        "wait_jitter": 2.5,
    },
}


def get_retry_config(operation_type: str) -> dict[str, Any]:
    """Get retry configuration for a specific operation type.

    Args:
        operation_type: One of the keys in RETRY_CONFIG

    Returns:
        Dictionary with retry parameters
    """
    if operation_type not in RETRY_CONFIG:
        raise ValueError(f"Unknown operation type: {operation_type}")

    config = RETRY_CONFIG[operation_type].copy()

    # Allow environment-based overrides for testing
    if settings.ENABLE_DICOM_DEBUG_LOGGER:
        # Reduce attempts in debug mode for faster feedback
        config["attempts"] = min(config["attempts"], 3)

    return config


def create_retry_decorator(operation_type: str):
    """Create a stamina retry decorator for a specific operation type.

    Args:
        operation_type: One of the keys in RETRY_CONFIG

    Returns:
        Configured stamina.retry decorator
    """
    # Check if stamina retry is enabled
    if not getattr(settings, "ENABLE_STAMINA_RETRY", True):
        # Return a no-op decorator
        def noop_decorator(func):
            return func

        return noop_decorator

    config = get_retry_config(operation_type)

    return stamina.retry(
        on=(ConnectionError, RetriableDicomError, TimeoutError),
        attempts=config["attempts"],
        timeout=config["timeout"],
        wait_initial=config["wait_initial"],
        wait_max=config["wait_max"],
        wait_jitter=config["wait_jitter"],
    )


# Pre-configured decorators for common operations
retry_dimse_connect = create_retry_decorator("dimse_connect")
retry_dimse_find = create_retry_decorator("dimse_find")
retry_dimse_retrieve = create_retry_decorator("dimse_retrieve")
retry_dimse_store = create_retry_decorator("dimse_store")
retry_dicomweb_search = create_retry_decorator("dicomweb_search")
retry_dicomweb_retrieve = create_retry_decorator("dicomweb_retrieve")
retry_dicomweb_store = create_retry_decorator("dicomweb_store")
