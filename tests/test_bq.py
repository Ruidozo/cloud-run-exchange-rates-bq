"""BigQuery integration Test."""

import logging
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.bq import upsert_exchange_rates

logging.basicConfig(level=logging.INFO)


def test_bq_insert():
    """Test inserting sample records into BigQuery."""
    print("\n=== Testing BigQuery Insert ===\n")
    
    # Create sample records
    test_records = [
        {
            "date": date.today().isoformat(),
            "currency": "USD",
            "rate_to_eur": 1.156261,
            "timestamp": 1731196800,
        },
        {
            "date": date.today().isoformat(),
            "currency": "GBP",
            "rate_to_eur": 0.878617,
            "timestamp": 1731196800,
        },
        {
            "date": date.today().isoformat(),
            "currency": "EUR",
            "rate_to_eur": 1.0,
            "timestamp": 1731196800,
        },
        {
            "date": date.today().isoformat(),
            "currency": "JPY",
            "rate_to_eur": 178.253168,
            "timestamp": 1731196800,
        },
        {
            "date": date.today().isoformat(),
            "currency": "CHF",
            "rate_to_eur": 0.932214,
            "timestamp": 1731196800,
        },
    ]
    
    print(f"Inserting {len(test_records)} test records for {date.today()}...")
    print(f"Currencies: {[r['currency'] for r in test_records]}\n")
    
    # Upsert to BigQuery
    upsert_exchange_rates(test_records)
    
    print("\nSuccess! Records inserted into BigQuery.")
    print(f"\nDataset: exchange_rates")
    print(f"Table: rates")
    print(f"\nVerify with:")
    print(f"  bq query --use_legacy_sql=false \\")
    print(f"  'SELECT * FROM `rui-case.exchange_rates.rates` WHERE date = CURRENT_DATE() ORDER BY currency'")


def test_bq_upsert():
    """Test upsert behavior - updating existing records."""
    print("\n=== Testing BigQuery Upsert (Update) ===\n")
    
    # Insert same records with different rates
    updated_records = [
        {
            "date": date.today().isoformat(),
            "currency": "USD",
            "rate_to_eur": 1.160000,  # Updated rate
            "timestamp": 1731200000,
        },
        {
            "date": date.today().isoformat(),
            "currency": "GBP",
            "rate_to_eur": 0.880000,  # Updated rate
            "timestamp": 1731200000,
        },
    ]
    
    print(f"Updating {len(updated_records)} existing records...")
    print("This should UPDATE existing rows, not create duplicates.\n")
    
    upsert_exchange_rates(updated_records)
    
    print("\nSuccess! Records updated.")
    print(f"\nVerify update with:")
    print(f"  bq query --use_legacy_sql=false \\")
    print(f"  'SELECT currency, rate_to_eur, timestamp FROM `rui-case.exchange_rates.rates` WHERE date = CURRENT_DATE() AND currency IN (\"USD\", \"GBP\") ORDER BY currency'")
    print(f"\nExpected:")
    print(f"  USD: 1.160000")
    print(f"  GBP: 0.880000")


if __name__ == "__main__":
    print("\nBigQuery Integration Test")
    print("=" * 40)
    print("\n1. Test insert")
    print("2. Test upsert (update)")
    print("3. Run both")
    
    choice = input("\nChoice (1, 2, or 3): ").strip()
    
    if choice == "1":
        test_bq_insert()
    elif choice == "2":
        test_bq_upsert()
    elif choice == "3":
        test_bq_insert()
        test_bq_upsert()
    else:
        print("Invalid choice. Use 1, 2, or 3.")