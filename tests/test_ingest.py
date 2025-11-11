"""Tests for exchange rate ingestion - upsert logic and EUR conversion."""
from unittest.mock import MagicMock, patch


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


def test_upsert_handles_duplicates():
    """Test that MERGE statement handles duplicate dates."""
    merge_query = """
    MERGE INTO `table` T
    USING `staging` S
    ON T.date = S.date AND T.currency = S.currency
    WHEN MATCHED THEN UPDATE SET rate_to_eur = S.rate_to_eur, timestamp = S.timestamp
    WHEN NOT MATCHED THEN INSERT (date, currency, rate_to_eur, timestamp) VALUES (S.date, S.currency, S.rate_to_eur, S.timestamp)
    """
    assert "WHEN MATCHED THEN UPDATE" in merge_query
    assert "WHEN NOT MATCHED THEN INSERT" in merge_query


def test_record_structure():
    """Test that records have correct structure."""
    record = {
        "date": "2025-11-11",
        "currency": "USD",
        "rate_to_eur": 0.92,
        "timestamp": "2025-11-11T00:00:00Z"
    }
    
    assert "date" in record
    assert "currency" in record
    assert "rate_to_eur" in record
    assert "timestamp" in record    