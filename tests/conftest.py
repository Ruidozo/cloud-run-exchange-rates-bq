"""Shared pytest fixtures and configuration."""
from datetime import date, datetime, timezone
from typing import Any, Dict
from unittest.mock import patch

import pytest


@pytest.fixture
def sample_oxr_response() -> Dict[str, Any]:
    """Sample OXR API response matching real API structure."""
    return {
        "disclaimer": "Usage subject to terms: https://openexchangerates.org/terms",
        "license": "https://openexchangerates.org/license",
        "timestamp": 1699660800,
        "base": "USD",
        "rates": {
            "EUR": 0.92,
            "USD": 1.0,
            "GBP": 0.81,
            "JPY": 150.0,
            "CHF": 0.88,
            "AUD": 1.55,
            "CAD": 1.36,
        }
    }


@pytest.fixture
def sample_date() -> date:
    """Sample date for testing."""
    return date(2025, 11, 10)


@pytest.fixture
def sample_timestamp() -> datetime:
    """Sample timestamp for testing."""
    return datetime(2025, 11, 10, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def expected_eur_rates() -> Dict[str, float]:
    """Expected EUR-based rates from sample_oxr_response."""
    return {
        "EUR": 1.0,
        "USD": 1.0869565217391304,
        "GBP": 0.8804347826086956,
        "JPY": 163.04347826086956,
        "CHF": 0.9565217391304348,
    }


@pytest.fixture
def sample_bq_records(sample_timestamp):
    """Sample BigQuery records for testing."""
    timestamp = int(sample_timestamp.timestamp())
    return [
        {
            "date": "2025-11-10",
            "currency": "USD",
            "rate_to_eur": 1.0869565217391304,
            "timestamp": timestamp,
        },
        {
            "date": "2025-11-10",
            "currency": "GBP",
            "rate_to_eur": 0.8804347826086956,
            "timestamp": timestamp,
        },
        {
            "date": "2025-11-10",
            "currency": "JPY",
            "rate_to_eur": 163.04347826086956,
            "timestamp": timestamp,
        },
        {
            "date": "2025-11-10",
            "currency": "CHF",
            "rate_to_eur": 0.9565217391304348,
            "timestamp": timestamp,
        },
    ]


@pytest.fixture
def mock_env_vars():
    """Mock environment variables for testing."""
    with patch.dict('os.environ', {
        'PROJECT_ID': 'test-project',
        'OXR_APP_ID': 'test-api-key'
    }):
        yield


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers",
        "integration: mark test as integration test (requires real API/BigQuery access)"
    )
    config.addinivalue_line(
        "markers",
        "slow: mark test as slow running"
    )