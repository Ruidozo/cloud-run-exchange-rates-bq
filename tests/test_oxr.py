# tests/test_oxr.py
# Integration tests for Open Exchange Rates API.
# This script tests fetching historical exchange rates
# using the function defined in app/oxr.py.


import logging
import sys
from datetime import date, timedelta
from pathlib import Path

# Add parent directory to path so we can import from app
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.oxr import fetch_historical_rates

# Configure logging to see the debug output
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

if __name__ == "__main__":
    # Test with today's date
    today = date.today()
    print(f"\n=== Testing with today's date: {today} ===")
    
    try:
        rates = fetch_historical_rates(today)
        print(f"Success!")
        print(f"Base currency: {rates.get('base')}")
        print(f"Timestamp: {rates.get('timestamp')}")
        print(f"Number of rates: {len(rates.get('rates', {}))}")
        print(f"Sample rates:")
        print(f"  EUR: {rates.get('rates', {}).get('EUR')}")
        print(f"  GBP: {rates.get('rates', {}).get('GBP')}")
        print(f"  JPY: {rates.get('rates', {}).get('JPY')}")
    except Exception as e:
        print(f"Error: {e}")
    
    # Test with a past date
    past_date = date.today() - timedelta(days=7)
    print(f"\n=== Testing with past date: {past_date} ===")
    
    try:
        rates = fetch_historical_rates(past_date)
        print(f"Success!")
        print(f"EUR rate: {rates.get('rates', {}).get('EUR')}")
    except Exception as e:
        print(f"Error: {e}")