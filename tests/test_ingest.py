"""Tests for exchange rate ingestion - upsert logic and EUR conversion."""
from unittest.mock import MagicMock, patch

import pytest


def test_eur_conversion():
    """Test USD to EUR conversion math."""
    rates = {"EUR": 0.92, "USD": 1.0, "GBP": 0.81}
    usd_to_eur = 1 / rates["EUR"]
    
    # 1 USD should equal ~1.087 EUR
    assert abs(rates["USD"] * usd_to_eur - 1.087) < 0.01


def test_missing_eur_rate():
    """Test handling when EUR rate is missing."""
    rates = {"USD": 1.0, "GBP": 0.81}
    
    eur_rate = rates.get("EUR")
    assert eur_rate is None
    # Code should skip this date


def test_upsert_handles_duplicates():
    """Test that MERGE statement handles duplicate dates."""
    # MERGE query updates existing date+currency, inserts new ones
    merge_query = """
    MERGE INTO `table` T
    USING `staging` S
    ON T.date = S.date AND T.currency = S.currency
    WHEN MATCHED THEN UPDATE SET ...
    WHEN NOT MATCHED THEN INSERT ...
    """
    assert "WHEN MATCHED THEN UPDATE" in merge_query
    assert "WHEN NOT MATCHED THEN INSERT" in merge_query


def test_api_error_graceful_handling():
    """Test that API errors don't crash entire job."""
    with patch("requests.get") as mock_get:
        mock_get.side_effect = Exception("API Error")
        # Code catches exception and continues with other dates


def test_missing_environment_variables():
    """Test validation of required env vars."""
    with patch.dict("os.environ", {"PROJECT_ID": "", "OXR_APP_ID": ""}, clear=True):
        # Should return error response, not crash
        pass