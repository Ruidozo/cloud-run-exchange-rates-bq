"""Tests for currency conversion logic."""
import pytest

from app.converter import convert_usd_to_eur_base


class TestConvertUsdToEurBase:
    """Test suite for USD to EUR conversion."""
    
    def test_basic_conversion(self):
        """Test basic conversion with valid data."""
        oxr_data = {
            "base": "USD",
            "rates": {
                "EUR": 0.92,
                "USD": 1.0,
                "GBP": 0.81,
                "JPY": 150.0,
                "CHF": 0.88,
            }
        }
        
        result = convert_usd_to_eur_base(oxr_data)
        
        # EUR should be exactly 1.0 (base currency)
        assert result["EUR"] == 1.0
        
        # USD to EUR calculation: 1.0 / 0.92 = 1.0869565...
        assert abs(result["USD"] - 1.0869565217391304) < 1e-10
        
        # GBP to EUR calculation: 0.81 / 0.92 = 0.8804347...
        assert abs(result["GBP"] - 0.8804347826086956) < 1e-10
        
        # All original currencies should be present
        assert set(result.keys()) == {"EUR", "USD", "GBP", "JPY", "CHF"}
    
    def test_missing_rates_key(self):
        """Test error handling when 'rates' key is missing."""
        invalid_data = {
            "base": "USD",
            "timestamp": 1699660800
        }
        
        with pytest.raises(KeyError) as exc_info:
            convert_usd_to_eur_base(invalid_data)
        
        assert "rates" in str(exc_info.value).lower()
    
    def test_missing_eur_rate(self):
        """Test error handling when EUR rate is missing."""
        invalid_data = {
            "rates": {
                "USD": 1.0,
                "GBP": 0.81,
                "JPY": 150.0
            }
        }
        
        with pytest.raises(ValueError) as exc_info:
            convert_usd_to_eur_base(invalid_data)
        
        assert "EUR" in str(exc_info.value)
    
    def test_zero_eur_rate(self):
        """Test error handling when EUR rate is zero."""
        invalid_data = {
            "rates": {
                "EUR": 0.0,
                "USD": 1.0
            }
        }
        
        with pytest.raises(ValueError) as exc_info:
            convert_usd_to_eur_base(invalid_data)
        
        assert "EUR" in str(exc_info.value) or "zero" in str(exc_info.value).lower()
    
    def test_negative_eur_rate(self):
        """Test error handling when EUR rate is negative."""
        invalid_data = {
            "rates": {
                "EUR": -0.92,
                "USD": 1.0
            }
        }
        
        with pytest.raises(ValueError) as exc_info:
            convert_usd_to_eur_base(invalid_data)
        
        assert "EUR" in str(exc_info.value) or "negative" in str(exc_info.value).lower()
    
    def test_skip_zero_rates(self):
        """Test that currencies with zero rates are skipped."""
        oxr_data = {
            "rates": {
                "EUR": 0.92,
                "USD": 1.0,
                "INVALID": 0.0,  # Should be skipped
                "GBP": 0.81
            }
        }
        
        result = convert_usd_to_eur_base(oxr_data)
        
        # INVALID should not be in result
        assert "INVALID" not in result
        # Valid currencies should be present
        assert "EUR" in result
        assert "USD" in result
        assert "GBP" in result
    
    def test_skip_negative_rates(self):
        """Test that currencies with negative rates are skipped."""
        oxr_data = {
            "rates": {
                "EUR": 0.92,
                "USD": 1.0,
                "INVALID": -5.0,  # Should be skipped
                "GBP": 0.81
            }
        }
        
        result = convert_usd_to_eur_base(oxr_data)
        
        assert "INVALID" not in result
        assert len(result) == 3  # EUR, USD, GBP
    
    def test_empty_rates(self):
        """Test handling of empty rates dictionary."""
        oxr_data = {
            "rates": {}
        }
        
        with pytest.raises(ValueError) as exc_info:
            convert_usd_to_eur_base(oxr_data)
        
        assert "EUR" in str(exc_info.value)
    
    def test_rates_not_dict(self):
        """Test error handling when rates is not a dictionary."""
        invalid_data = {
            "rates": "not a dictionary"
        }
        
        with pytest.raises((TypeError, KeyError, ValueError)):
            convert_usd_to_eur_base(invalid_data)
    
    @pytest.mark.parametrize("eur_rate,usd_rate,expected", [
        (0.92, 1.0, 1.0869565217391304),
        (1.0, 1.0, 1.0),
        (0.85, 1.15, 1.3529411764705883),
        (1.05, 0.95, 0.9047619047619048),
    ])
    def test_conversion_accuracy(self, eur_rate, usd_rate, expected):
        """Test conversion accuracy with various rate combinations."""
        oxr_data = {
            "rates": {
                "EUR": eur_rate,
                "USD": usd_rate
            }
        }
        
        result = convert_usd_to_eur_base(oxr_data)
        
        assert abs(result["USD"] - expected) < 1e-10
    
    def test_large_number_of_currencies(self):
        """Test conversion with many currencies."""
        rates = {"EUR": 0.92}
        
        # Add 50 currencies
        for i in range(50):
            rates[f"CURR{i}"] = 1.0 + (i * 0.1)
        
        oxr_data = {"rates": rates}
        result = convert_usd_to_eur_base(oxr_data)
        
        # All currencies should be converted
        assert len(result) == 51  # EUR + 50 currencies
        
        # Verify EUR is still 1.0
        assert result["EUR"] == 1.0
    
    def test_very_small_rates(self):
        """Test conversion with very small rates (e.g., JPY, KRW)."""
        oxr_data = {
            "rates": {
                "EUR": 0.92,
                "JPY": 0.0067,  # Very small rate
                "KRW": 0.00075  # Even smaller
            }
        }
        
        result = convert_usd_to_eur_base(oxr_data)
        
        # Should handle small numbers without precision issues
        assert "JPY" in result
        assert "KRW" in result
        assert result["JPY"] > 0
        assert result["KRW"] > 0
    
    def test_very_large_rates(self):
        """Test conversion with very large rates."""
        oxr_data = {
            "rates": {
                "EUR": 0.92,
                "LARGE": 10000.0
            }
        }
        
        result = convert_usd_to_eur_base(oxr_data)
        
        assert "LARGE" in result
        expected = 10000.0 / 0.92
        assert abs(result["LARGE"] - expected) < 1e-6


if __name__ == "__main__":
    pytest.main([__file__, "-v"])