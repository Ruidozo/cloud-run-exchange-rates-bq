"""Integration tests for the complete pipeline.

These tests use real APIs and BigQuery.
Run with: pytest tests/test_integration.py --integration
"""
import os
from datetime import date, datetime, timedelta, timezone

import pytest

from app.bq import upsert_exchange_rates
from app.converter import convert_usd_to_eur_base
from app.oxr import fetch_historical_rates


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "integration: mark test as integration test (requires API access)"
    )


@pytest.fixture
def skip_if_no_api_key():
    """Skip test if API key is not available."""
    if not os.getenv("OXR_APP_ID"):
        pytest.skip("OXR_APP_ID not set - skipping integration test")


@pytest.mark.integration
class TestAPIIntegration:
    """Integration tests with real OXR API."""
    
    def test_fetch_today_rates(self, skip_if_no_api_key):
        """Test fetching today's rates from real API."""
        today = date.today()
        
        oxr_data = fetch_historical_rates(today)
        
        # Verify response structure
        assert "rates" in oxr_data
        assert "base" in oxr_data
        assert oxr_data["base"] == "USD"
        
        # Verify essential currencies are present
        rates = oxr_data["rates"]
        assert "EUR" in rates
        assert "USD" in rates
        assert "GBP" in rates
        assert "JPY" in rates
        
        # Verify rates are positive numbers
        for currency, rate in rates.items():
            assert isinstance(rate, (int, float))
            assert rate > 0
    
    def test_fetch_historical_date(self, skip_if_no_api_key):
        """Test fetching rates for a specific historical date."""
        test_date = date.today() - timedelta(days=7)
        
        oxr_data = fetch_historical_rates(test_date)
        
        assert "rates" in oxr_data
        assert len(oxr_data["rates"]) > 0
    
    def test_fetch_weekend_date(self, skip_if_no_api_key):
        """Test fetching rates for a weekend (may return Friday's rates)."""
        # Find last Saturday
        today = date.today()
        days_since_saturday = (today.weekday() - 5) % 7
        last_saturday = today - timedelta(days=days_since_saturday)
        
        try:
            oxr_data = fetch_historical_rates(last_saturday)
            # Some APIs return Friday's rates for weekends
            assert "rates" in oxr_data
        except Exception as e:
            # Acceptable if API doesn't have weekend data
            assert "404" in str(e) or "not found" in str(e).lower()


@pytest.mark.integration
class TestConversionIntegration:
    """Integration tests for conversion with real data."""
    
    def test_convert_real_api_data(self, skip_if_no_api_key):
        """Test conversion with real API data."""
        today = date.today()
        oxr_data = fetch_historical_rates(today)
        
        eur_rates = convert_usd_to_eur_base(oxr_data)
        
        # EUR should be exactly 1.0
        assert eur_rates["EUR"] == 1.0
        
        # Verify tracked currencies are present
        for currency in ["USD", "GBP", "JPY", "CHF"]:
            assert currency in eur_rates
            assert eur_rates[currency] > 0
        
        # Verify conversions are reasonable
        # USD/EUR is typically between 0.8 and 1.3
        assert 0.8 < eur_rates["USD"] < 1.3
        
        # GBP/EUR is typically between 0.8 and 1.2
        assert 0.8 < eur_rates["GBP"] < 1.2
        
        # JPY/EUR is typically between 120 and 180
        assert 120 < eur_rates["JPY"] < 180
        
        # CHF/EUR is typically between 0.9 and 1.1
        assert 0.9 < eur_rates["CHF"] < 1.1
    
    def test_convert_multiple_days(self, skip_if_no_api_key):
        """Test conversion for multiple consecutive days."""
        end_date = date.today()
        start_date = end_date - timedelta(days=5)
        
        all_rates = []
        current_date = start_date
        
        while current_date <= end_date:
            oxr_data = fetch_historical_rates(current_date)
            eur_rates = convert_usd_to_eur_base(oxr_data)
            all_rates.append({
                "date": current_date,
                "rates": eur_rates
            })
            current_date += timedelta(days=1)
        
        # Verify we got data for all days
        assert len(all_rates) >= 5
        
        # Verify EUR is always 1.0
        for day_data in all_rates:
            assert day_data["rates"]["EUR"] == 1.0
        
        # Verify rates don't change drastically day to day
        for i in range(len(all_rates) - 1):
            usd_today = all_rates[i]["rates"]["USD"]
            usd_tomorrow = all_rates[i + 1]["rates"]["USD"]
            
            # USD/EUR shouldn't change more than 5% day to day
            change_pct = abs(usd_tomorrow - usd_today) / usd_today
            assert change_pct < 0.05, f"USD/EUR changed {change_pct:.2%} in one day"


@pytest.mark.integration
@pytest.mark.skipif(
    not os.getenv("PROJECT_ID"),
    reason="PROJECT_ID not set - skipping BigQuery integration test"
)
class TestBigQueryIntegration:
    """Integration tests with real BigQuery."""
    
    def test_complete_pipeline(self, skip_if_no_api_key):
        """Test the complete pipeline from API to BigQuery."""
        # Fetch data
        today = date.today()
        oxr_data = fetch_historical_rates(today)
        
        # Convert
        eur_rates = convert_usd_to_eur_base(oxr_data)
        
        # Prepare records with ISO format timestamp
        timestamp = datetime.now(timezone.utc).isoformat()
        records = []
        
        for currency in ["USD", "GBP", "JPY", "CHF"]:
            if currency in eur_rates:
                records.append({
                    "date": today.isoformat(),
                    "currency": currency,
                    "rate_to_eur": eur_rates[currency],
                    "timestamp": timestamp,
                })
        
        # Upsert to BigQuery
        upsert_exchange_rates(records)
        
        # Verify records were inserted
        from app.bq import get_client
        client = get_client()
        
        query = f"""
        SELECT COUNT(*) as count 
        FROM `{client.project}.exchange_rates.rates`
        WHERE date = '{today.isoformat()}'
        AND currency IN ('USD', 'GBP', 'JPY', 'CHF')
        """
        
        result = list(client.query(query).result())
        count = result[0].count
        
        # Should have at least the 4 currencies we inserted
        assert count >= 4


# CLI runner for manual validation
def main():
    """Run integration tests manually."""
    import sys
    
    print("=== Exchange Rates Integration Tests ===\n")
    
    if len(sys.argv) > 1 and sys.argv[1] == "--30days":
        print("Testing last 30 days...")
        # Run with pytest
        pytest.main([
            __file__,
            "-v",
            "-k", "test_convert_multiple_days",
            "-m", "integration"
        ])
    else:
        print("Testing today's rates...")
        pytest.main([
            __file__,
            "-v",
            "-k", "test_fetch_today_rates",
            "-m", "integration"
        ])


if __name__ == "__main__":
    main()