"""Edge case tests for the exchange rates pipeline."""
from datetime import date, datetime, timezone

import pytest

from app.converter import convert_usd_to_eur_base


class TestEdgeCases:
    """Test edge cases and error conditions."""
    
    def test_malformed_json_structure(self):
        """Test handling of malformed JSON structure."""
        malformed_data = {
            "rates": {
                "EUR": "not a number",  # String instead of float
                "USD": 1.0
            }
        }
        
        with pytest.raises((TypeError, ValueError)):
            convert_usd_to_eur_base(malformed_data)
    
    def test_special_float_values(self):
        """Test handling of special float values."""
        import math

        # Test infinity
        infinite_data = {
            "rates": {
                "EUR": 0.92,
                "INF": math.inf
            }
        }
        
        result = convert_usd_to_eur_base(infinite_data)
        # Should either skip or handle infinity
        assert "INF" not in result or math.isinf(result["INF"])
        
        # Test NaN
        nan_data = {
            "rates": {
                "EUR": 0.92,
                "NAN": math.nan
            }
        }
        
        result = convert_usd_to_eur_base(nan_data)
        # Should skip NaN values
        assert "NAN" not in result
    
    def test_unicode_currency_codes(self):
        """Test handling of unicode or special characters in currency codes."""
        oxr_data = {
            "rates": {
                "EUR": 0.92,
                "USD": 1.0,
                "£GBP": 0.81,  # Invalid code with symbol
                "CNY¥": 7.2    # Invalid code with symbol
            }
        }
        
        result = convert_usd_to_eur_base(oxr_data)
        
        # Should handle or skip invalid codes
        assert "EUR" in result
        assert "USD" in result
    
    def test_extremely_long_currency_code(self):
        """Test handling of unreasonably long currency codes."""
        oxr_data = {
            "rates": {
                "EUR": 0.92,
                "A" * 100: 1.0  # 100-character currency code
            }
        }
        
        result = convert_usd_to_eur_base(oxr_data)
        
        # Should handle long keys
        assert "EUR" in result
    
    def test_duplicate_currency_handling(self):
        """Test that duplicate currencies are handled correctly."""
        # This is more about validating dict behavior
        oxr_data = {
            "rates": {
                "EUR": 0.92,
                "USD": 1.0,
                "USD": 1.01  # Duplicate (will override)
            }
        }
        
        result = convert_usd_to_eur_base(oxr_data)
        
        # Last value should win in Python dicts
        assert "USD" in result
    
    def test_case_sensitivity(self):
        """Test currency code case sensitivity."""
        oxr_data = {
            "rates": {
                "EUR": 0.92,
                "usd": 1.0,  # Lowercase
                "USD": 1.01  # Uppercase
            }
        }
        
        result = convert_usd_to_eur_base(oxr_data)
        
        # Should handle case-sensitive keys
        assert "EUR" in result
    
    def test_numerical_precision_boundaries(self):
        """Test numerical precision at boundaries."""
        oxr_data = {
            "rates": {
                "EUR": 0.9234567890123456789,  # Many decimal places
                "USD": 1.0000000000000001,
                "TINY": 1e-10,  # Very small
                "HUGE": 1e10    # Very large
            }
        }
        
        result = convert_usd_to_eur_base(oxr_data)
        
        # Should handle precision
        assert "EUR" in result
        assert result["EUR"] == 1.0
        
        # Very small rates might be skipped or handled
        if "TINY" in result:
            assert result["TINY"] > 0
    
    def test_rate_equals_eur_rate(self):
        """Test when a currency rate equals the EUR rate."""
        oxr_data = {
            "rates": {
                "EUR": 0.92,
                "SAME": 0.92,  # Same as EUR
                "USD": 1.0
            }
        }
        
        result = convert_usd_to_eur_base(oxr_data)
        
        # SAME should convert to 1.0 (same as EUR)
        assert abs(result["SAME"] - 1.0) < 1e-10
    
    def test_only_eur_in_rates(self):
        """Test when only EUR is present in rates."""
        oxr_data = {
            "rates": {
                "EUR": 0.92
            }
        }
        
        result = convert_usd_to_eur_base(oxr_data)
        
        # Should return at least EUR
        assert "EUR" in result
        assert result["EUR"] == 1.0
    
    def test_mixed_valid_invalid_rates(self):
        """Test mix of valid and invalid rates."""
        oxr_data = {
            "rates": {
                "EUR": 0.92,
                "USD": 1.0,
                "ZERO": 0.0,      # Invalid
                "NEG": -1.5,      # Invalid
                "GBP": 0.81,      # Valid
                "NONE": None,     # Invalid
                "CHF": 0.88       # Valid
            }
        }
        
        result = convert_usd_to_eur_base(oxr_data)
        
        # Only valid currencies should be in result
        assert "EUR" in result
        assert "USD" in result
        assert "GBP" in result
        assert "CHF" in result
        
        # Invalid ones should be skipped
        assert "ZERO" not in result
        assert "NEG" not in result
        assert "NONE" not in result
    
    def test_nested_data_structure(self):
        """Test deeply nested or complex data structures."""
        complex_data = {
            "rates": {
                "EUR": 0.92,
                "USD": 1.0,
                "NESTED": {"value": 1.5}  # Nested dict instead of float
            }
        }
        
        # Should either skip or raise error for nested values
        try:
            result = convert_usd_to_eur_base(complex_data)
            # If it doesn't raise, NESTED should be skipped
            assert "NESTED" not in result
        except (TypeError, ValueError):
            # Acceptable to raise error
            pass
    
    def test_extra_keys_in_response(self):
        """Test that extra keys in response don't break conversion."""
        oxr_data = {
            "disclaimer": "Usage subject to terms",
            "license": "https://openexchangerates.org/license",
            "timestamp": 1699660800,
            "base": "USD",
            "rates": {
                "EUR": 0.92,
                "USD": 1.0
            },
            "extra_field": "should be ignored"
        }
        
        result = convert_usd_to_eur_base(oxr_data)
        
        # Should ignore extra fields and process rates
        assert "EUR" in result
        assert "USD" in result
    
    def test_empty_string_currency_code(self):
        """Test handling of empty string as currency code."""
        oxr_data = {
            "rates": {
                "EUR": 0.92,
                "": 1.0  # Empty string key
            }
        }
        
        result = convert_usd_to_eur_base(oxr_data)
        
        # Should handle or skip empty string
        assert "EUR" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])