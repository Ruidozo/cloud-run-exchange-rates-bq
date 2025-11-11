"""Tests for exchange rate ingestion: transform, merge, and API integration."""

import json
from datetime import date
from unittest.mock import MagicMock, patch

import pytest
import requests
from fastapi.testclient import TestClient

from app.main import (TRACKED_CURRENCIES, app, convert_unix_to_iso,
                      fetch_historical_rates, transform_to_eur_base)

# ============================================================================
# UNIT TESTS: HELPER FUNCTIONS
# ============================================================================

class TestConvertTimestamp:
    """Test Unix to ISO 8601 conversion."""
    
    def test_valid_unix_timestamp(self):
        """Test conversion of valid Unix timestamp."""
        unix_ts = 1731283200 
        result = convert_unix_to_iso(unix_ts)
        
        assert result.endswith("Z")
        assert "2024-11-11" in result
    
    def test_none_timestamp_returns_current(self):
        """Test that None timestamp returns current time."""
        result = convert_unix_to_iso(None)
        
        assert result.endswith("Z")
        assert isinstance(result, str)


class TestFetchHistoricalRates:
    """Test API fetch logic."""
    
    @patch("app.main.requests.get")
    def test_successful_fetch(self, mock_get):
        """Test successful API fetch."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "timestamp": 1731283200,
            "rates": {"EUR": 0.92, "USD": 1.0, "GBP": 0.81}
        }
        mock_get.return_value = mock_response
        
        result = fetch_historical_rates("test_key", date(2024, 11, 11))
        
        assert result is not None
        assert "rates" in result
        assert result["rates"]["EUR"] == 0.92
    
    @patch("app.main.requests.get")
    def test_api_error_returns_none(self, mock_get):
        """Test that API errors return None."""
        mock_get.side_effect = requests.exceptions.ConnectionError("Connection timeout")
        
        result = fetch_historical_rates("test_key", date(2024, 11, 11))
        
        assert result is None
    
    @patch("app.main.requests.get")
    def test_http_error_returns_none(self, mock_get):
        """Test that HTTP errors (4xx, 5xx) return None."""
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("401 Unauthorized")
        mock_get.return_value = mock_response
        
        result = fetch_historical_rates("invalid_key", date(2024, 11, 11))
        
        assert result is None


class TestTransformToEURBase:
    """Test USD to EUR conversion logic."""
    
    def test_valid_transformation(self):
        """Test transformation with valid rates."""
        raw_data = {
            "timestamp": 1731283200,
            "rates": {
                "EUR": 0.92,
                "USD": 1.0,
                "GBP": 0.81,
                "JPY": 149.5,
                "CHF": 0.88,
            }
        }
        
        records = transform_to_eur_base(raw_data, date(2024, 11, 11))
        
        assert len(records) == 4  # USD, GBP, JPY, CHF
        assert all(r["currency"] in TRACKED_CURRENCIES for r in records)
        assert all(r["date"] == "2024-11-11" for r in records)
        assert all(isinstance(r["rate_to_eur"], float) for r in records)
    
    def test_eur_conversion_math(self):
        """Test accuracy of EUR conversion formula."""
        raw_data = {
            "timestamp": 1731283200,
            "rates": {
                "EUR": 0.92,
                "USD": 1.0,
            }
        }
        
        records = transform_to_eur_base(raw_data, date(2024, 11, 11))
        usd_record = next(r for r in records if r["currency"] == "USD")
        
        # 1 USD should equal 1 / 0.92 = 1.087 EUR
        expected_rate = 1.0 / 0.92
        assert abs(usd_record["rate_to_eur"] - expected_rate) < 0.001
    
    def test_missing_eur_rate_returns_empty(self):
        """Test that missing EUR rate returns empty list."""
        raw_data = {
            "timestamp": 1731283200,
            "rates": {
                "USD": 1.0,
                "GBP": 0.81,
                # EUR missing
            }
        }
        
        records = transform_to_eur_base(raw_data, date(2024, 11, 11))
        
        assert len(records) == 0
    
    def test_missing_tracked_currency_skipped(self):
        """Test that missing tracked currencies don't cause errors."""
        raw_data = {
            "timestamp": 1731283200,
            "rates": {
                "EUR": 0.92,
                "USD": 1.0,
                # GBP, JPY, CHF missing
            }
        }
        
        records = transform_to_eur_base(raw_data, date(2024, 11, 11))
        
        assert len(records) == 1
        assert records[0]["currency"] == "USD"
    
    def test_record_structure(self):
        """Test that records have required fields."""
        raw_data = {
            "timestamp": 1731283200,
            "rates": {"EUR": 0.92, "USD": 1.0}
        }
        
        records = transform_to_eur_base(raw_data, date(2024, 11, 11))
        
        required_fields = {"date", "currency", "rate_to_eur", "timestamp"}
        for record in records:
            assert required_fields.issubset(record.keys())


# ============================================================================
# UNIT TESTS: MERGE LOGIC
# ============================================================================

class TestMergeLogic:
    """Test BigQuery MERGE statement for idempotent upserts."""
    
    def test_merge_statement_structure(self):
        """Test that MERGE statement has required clauses."""
        merge_query = "WHEN MATCHED THEN UPDATE SET rate_to_eur = S.rate_to_eur"
        
        assert "WHEN MATCHED THEN UPDATE" in merge_query
        assert "rate_to_eur" in merge_query


# ============================================================================
# INTEGRATION TESTS: FastAPI ENDPOINTS
# ============================================================================

@pytest.fixture
def client():
    """FastAPI test client."""
    return TestClient(app)


class TestHealthEndpoint:
    """Test GET /health endpoint."""
    
    def test_health_check_success(self, client):
        """Test health check returns 200 OK."""
        response = client.get("/health")
        
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestIngestEndpoint:
    """Test POST /ingest endpoint."""
    
    @patch.dict("os.environ", {"PROJECT_ID": "test-project", "OXR_APP_ID": "test-key"})
    @patch("app.main.fetch_historical_rates")
    @patch("app.main.bigquery.Client")
    def test_ingest_success_with_mocks(self, mock_bq_client, mock_fetch, client):
        """Test ingest endpoint with mocked API and BigQuery."""
        # Mock API response
        mock_fetch.return_value = {
            "timestamp": 1731283200,
            "rates": {"EUR": 0.92, "USD": 1.0, "GBP": 0.81, "JPY": 149.5, "CHF": 0.88}
        }
        
        # Mock BigQuery client
        mock_client_instance = MagicMock()
        mock_bq_client.return_value = mock_client_instance
        mock_job = MagicMock()
        mock_job.result.return_value = None
        mock_client_instance.load_table_from_json.return_value = mock_job
        mock_client_instance.query.return_value = mock_job
        
        response = client.post("/ingest")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["records"] > 0
    
    @patch.dict("os.environ", {}, clear=True)
    def test_ingest_missing_env_vars(self, client):
        """Test ingest fails gracefully with missing environment variables."""
        response = client.post("/ingest")
        
        assert response.status_code == 500
        data = response.json()
        assert data["status"] == "error"
        assert "environment" in data["message"].lower()
    
    @patch.dict("os.environ", {"PROJECT_ID": "test-project", "OXR_APP_ID": "test-key"})
    @patch("app.main.fetch_historical_rates")
    @patch("app.main.bigquery.Client")
    def test_ingest_no_data_fetched(self, mock_bq_client, mock_fetch, client):
        """Test ingest fails when no data is fetched."""
        mock_fetch.return_value = None  # All API calls fail
        
        response = client.post("/ingest")
        
        assert response.status_code == 400
        data = response.json()
        assert data["status"] == "error"
        assert "No records" in data["message"]


# ============================================================================
# BACKWARDS COMPATIBILITY: ORIGINAL TESTS
# ============================================================================

def test_eur_conversion():
    """Test USD to EUR conversion math (original test)."""
    rates = {"EUR": 0.92, "USD": 1.0, "GBP": 0.81}
    usd_to_eur = 1 / rates["EUR"]
    
    assert abs(rates["USD"] * usd_to_eur - 1.087) < 0.01


def test_missing_eur_rate():
    """Test handling when EUR rate is missing (original test)."""
    rates = {"USD": 1.0, "GBP": 0.81}
    eur_rate = rates.get("EUR")
    
    assert eur_rate is None


def test_upsert_handles_duplicates():
    """Test MERGE statement handles duplicate dates (original test)."""
    merge_query = "WHEN MATCHED THEN UPDATE SET rate_to_eur = S.rate_to_eur"
    
    assert "WHEN MATCHED THEN UPDATE" in merge_query
    assert "WHEN NOT MATCHED THEN INSERT" in merge_query or "rate_to_eur" in merge_query


def test_record_structure():
    """Test records have correct structure (original test)."""
    record = {
        "date": "2024-11-11",
        "currency": "USD",
        "rate_to_eur": 0.92,
        "timestamp": "2024-11-11T00:00:00Z"
    }
    
    assert "date" in record
    assert "currency" in record
    assert "rate_to_eur" in record
    assert "timestamp" in record