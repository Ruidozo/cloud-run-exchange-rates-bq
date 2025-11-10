# tests/validation_test.py
# Validation script to check exchange rates fetched from Open Exchange Rates API.
# It can validate today's rates or rates over the last 30 days, showing statistics.


import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.converter import convert_usd_to_eur_base
from app.oxr import fetch_historical_rates

CURRENCIES = ["USD", "GBP", "JPY", "CHF"]


def validate_today():
    """Check today's exchange rates."""
    print("\n=== Today's Exchange Rates ===\n")
    
    today = date.today()
    data = fetch_historical_rates(today)
    eur_rates = convert_usd_to_eur_base(data)
    
    print(f"Date: {today}\n")
    for currency in CURRENCIES:
        rate = eur_rates.get(currency, 0)
        print(f"{currency}: {rate:.6f}")


def validate_30_days():
    """Check exchange rates for last 30 days."""
    print("\n=== Last 30 Days Exchange Rates ===\n")
    
    end_date = date.today()
    start_date = end_date - timedelta(days=29)
    
    # Collect all rates
    all_rates = {currency: [] for currency in CURRENCIES}
    
    total_days = 30
    current_date = start_date
    day_count = 0
    
    print("Fetching rates...\n")
    
    while current_date <= end_date:
        day_count += 1
        
        # Show progress
        progress = int((day_count / total_days) * 20)
        bar = "=" * progress + "-" * (20 - progress)
        print(f"\r[{bar}] {day_count}/{total_days} days", end="", flush=True)
        
        data = fetch_historical_rates(current_date)
        eur_rates = convert_usd_to_eur_base(data)
        
        for currency in CURRENCIES:
            all_rates[currency].append(eur_rates[currency])
        
        current_date += timedelta(days=1)
    
    print("\n\n" + "=" * 40 + "\n")
    
    # Show statistics
    print(f"Period: {start_date} to {end_date}\n")
    
    for currency in CURRENCIES:
        rates = all_rates[currency]
        minimum = min(rates)
        maximum = max(rates)
        average = sum(rates) / len(rates)
        latest = rates[-1]
        
        print(f"{currency}:")
        print(f"  Latest:  {latest:.6f}")
        print(f"  Average: {average:.6f}")
        print(f"  Min:     {minimum:.6f}")
        print(f"  Max:     {maximum:.6f}\n")


if __name__ == "__main__":
    print("\nExchange Rate Validator")
    print("=" * 30)
    print("\n1. Today only")
    print("2. Last 30 days")
    
    choice = input("\nChoice (1 or 2): ").strip()
    
    if choice == "1":
        validate_today()
    elif choice == "2":
        validate_30_days()
    else:
        print("Invalid choice. Use 1 or 2.")