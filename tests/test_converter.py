# tests/test_converter.py
# Integration tests for currency conversion from USD to EUR base.
# This script tests the conversion logic defined in app/converter.py.

import logging
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.converter import convert_usd_to_eur_base

logging.basicConfig(level=logging.INFO)


def test_convert_usd_to_eur():
    """Test USD to EUR conversion."""
    # Sample USD-based data from Open Exchange Rates
    usd_data = {
        "base": "USD",
        "rates": {
            "EUR": 0.85,
            "GBP": 0.73,
            "USD": 1.0,
            "JPY": 110.0,
        }
    }
    
    print("\n=== Testing USD to EUR Conversion ===")
    print(f"Input (USD base): {usd_data['rates']}")
    
    eur_rates = convert_usd_to_eur_base(usd_data)
    
    print(f"\nOutput (EUR base): {eur_rates}")
    
    # Assertions
    assert eur_rates["EUR"] == 1.0, "EUR to EUR should be 1.0"
    
    # GBP: 0.73 / 0.85 = 0.858824
    expected_gbp = 0.73 / 0.85
    assert abs(eur_rates["GBP"] - expected_gbp) < 0.0001, f"GBP rate incorrect: {eur_rates['GBP']} != {expected_gbp}"
    
    # USD: 1.0 / 0.85 = 1.176471
    expected_usd = 1.0 / 0.85
    assert abs(eur_rates["USD"] - expected_usd) < 0.0001, f"USD rate incorrect: {eur_rates['USD']} != {expected_usd}"
    
    # JPY: 110.0 / 0.85 = 129.411765
    expected_jpy = 110.0 / 0.85
    assert abs(eur_rates["JPY"] - expected_jpy) < 0.0001, f"JPY rate incorrect: {eur_rates['JPY']} != {expected_jpy}"
    
    print("\n All conversion tests passed!")
    print(f"   EUR = {eur_rates['EUR']:.6f}")
    print(f"   GBP = {eur_rates['GBP']:.6f} (expected {expected_gbp:.6f})")
    print(f"   USD = {eur_rates['USD']:.6f} (expected {expected_usd:.6f})")
    print(f"   JPY = {eur_rates['JPY']:.6f} (expected {expected_jpy:.6f})")


def test_missing_eur():
    """Test error handling when EUR is missing."""
    print("\n=== Testing Missing EUR Error Handling ===")
    
    bad_data = {
        "base": "USD",
        "rates": {
            "GBP": 0.73,
            "USD": 1.0,
        }
    }
    
    try:
        convert_usd_to_eur_base(bad_data)
        print("Should have raised ValueError")
        assert False, "Should have raised ValueError"
    except ValueError as e:
        print(f"Correctly raised ValueError: {e}")


if __name__ == "__main__":
    test_convert_usd_to_eur()
    test_missing_eur()
    print("\nTests completed successfully!")