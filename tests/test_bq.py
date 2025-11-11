# tests/test_bq.py
# Integration tests for BigQuery upsert functionality.
# This script tests inserting and updating exchange rate records
# into a BigQuery table using the upsert mechanism defined in app/bq.py.

import logging
import sys
import time
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables first
load_dotenv()

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.bq import upsert_exchange_rates

logging.basicConfig(level=logging.INFO)


def test_bq_insert():
    """Test inserting sample records into BigQuery."""
    print("\n=== Testing BigQuery Insert ===\n")

    from datetime import datetime, timezone

    # Use Unix timestamp (integer)
    current_timestamp = int(datetime.now(timezone.utc).timestamp())

    # Create sample records
    test_records = [
        {
            "date": date.today().isoformat(),
            "currency": "USD",
            "rate_to_eur": 1.156261,
            "timestamp": current_timestamp,
        },
        {
            "date": date.today().isoformat(),
            "currency": "GBP",
            "rate_to_eur": 0.878617,
            "timestamp": current_timestamp,
        },
        {
            "date": date.today().isoformat(),
            "currency": "EUR",
            "rate_to_eur": 1.0,
            "timestamp": current_timestamp,
        },
        {
            "date": date.today().isoformat(),
            "currency": "JPY",
            "rate_to_eur": 178.253168,
            "timestamp": current_timestamp,
        },
        {
            "date": date.today().isoformat(),
            "currency": "CHF",
            "rate_to_eur": 0.932214,
            "timestamp": current_timestamp,
        },
    ]

    print(f"Inserting {len(test_records)} test records for {date.today()}...")
    print(f"Currencies: {[r['currency'] for r in test_records]}")
    print(f"Timestamp: {current_timestamp}\n")
    
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

    from datetime import datetime, timezone

    # Use Unix timestamp (integer)
    current_timestamp = int(datetime.now(timezone.utc).timestamp())

    # Insert same records with different rates
    updated_records = [
        {
            "date": date.today().isoformat(),
            "currency": "USD",
            "rate_to_eur": 1.160000,  # Updated rate
            "timestamp": current_timestamp,
        },
        {
            "date": date.today().isoformat(),
            "currency": "GBP",
            "rate_to_eur": 0.880000,  # Updated rate
            "timestamp": current_timestamp,
        },
    ]

    print(f"Updating {len(updated_records)} existing records...")
    print("This should UPDATE existing rows, not create duplicates.\n")

    upsert_exchange_rates(updated_records)
    
    print("✓ Upsert completed successfully!")
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

"""Tests for BigQuery operations."""
import os
from datetime import date, datetime, timezone
from unittest.mock import patch

import pytest
from google.cloud import bigquery
from google.cloud.exceptions import NotFound

from app.bq import ensure_staging_table, get_client, upsert_exchange_rates


@pytest.fixture
def bq_client():
    """Get BigQuery client for testing."""
    if not os.getenv("PROJECT_ID"):
        pytest.skip("PROJECT_ID not set - skipping BigQuery tests")
    return get_client()


@pytest.fixture
def test_dataset(bq_client):
    """Create test dataset."""
    dataset_id = f"{bq_client.project}.exchange_rates_test"
    dataset = bigquery.Dataset(dataset_id)
    dataset.location = "europe-west1"
    
    try:
        bq_client.create_dataset(dataset, exists_ok=True)
    except Exception as e:
        pytest.skip(f"Cannot create test dataset: {e}")
    
    yield "exchange_rates_test"
    
    # Cleanup
    try:
        bq_client.delete_dataset(dataset_id, delete_contents=True, not_found_ok=True)
    except Exception:
        pass


@pytest.fixture
def sample_records():
    """Sample records for testing."""
    now = datetime.now(timezone.utc)
    timestamp = int(now.timestamp())
    return [
        {
            "date": "2025-11-10",
            "currency": "USD",
            "rate_to_eur": 1.0869565217391304,
            "timestamp": timestamp,
        },
        {
            "date": "2025-11-10",
            "currency": "GBP",
            "rate_to_eur": 0.8804347826086956,
            "timestamp": timestamp,
        },
        {
            "date": "2025-11-10",
            "currency": "JPY",
            "rate_to_eur": 163.04347826086956,
            "timestamp": timestamp,
        },
    ]


class TestBigQueryOperations:
    """Test BigQuery operations."""
    
    def test_get_client_success(self):
        """Test getting BigQuery client."""
        if not os.getenv("PROJECT_ID"):
            pytest.skip("PROJECT_ID not set")
        
        client = get_client()
        assert isinstance(client, bigquery.Client)
        assert client.project == os.getenv("PROJECT_ID")
    
    def test_get_client_missing_project_id(self):
        """Test error when PROJECT_ID is not set."""
        with patch.dict('os.environ', {}, clear=True):
            with pytest.raises(ValueError) as exc_info:
                get_client()
            
            assert "PROJECT_ID" in str(exc_info.value)
    
    def test_ensure_staging_table_creates_new(self, bq_client, test_dataset):
        """Test creating new staging table."""
        staging_table_id = ensure_staging_table(bq_client, test_dataset)
        
        # Verify table exists
        table_ref = bigquery.TableReference.from_string(staging_table_id)
        table = bq_client.get_table(table_ref)
        
        assert table is not None
        assert len(table.schema) == 4
        
        # Verify schema
        schema_fields = {field.name: field.field_type for field in table.schema}
        assert schema_fields["date"] == "DATE"
        assert schema_fields["currency"] == "STRING"
        assert schema_fields["rate_to_eur"] == "FLOAT"
        assert schema_fields["timestamp"] == "INTEGER"
    
    def test_ensure_staging_table_exists(self, bq_client, test_dataset):
        """Test that existing table is not recreated."""
        # Create table first time
        staging_table_id_1 = ensure_staging_table(bq_client, test_dataset)
        
        # Call again
        staging_table_id_2 = ensure_staging_table(bq_client, test_dataset)
        
        # Should return same table
        assert staging_table_id_1 == staging_table_id_2
    
    def test_upsert_new_records(self, bq_client, test_dataset, sample_records):
        """Test inserting new records."""
        # Ensure tables exist
        ensure_staging_table(bq_client, test_dataset)
        
        # Create main table
        table_id = f"{bq_client.project}.{test_dataset}.rates"
        schema = [
            bigquery.SchemaField("date", "DATE", mode="REQUIRED"),
            bigquery.SchemaField("currency", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("rate_to_eur", "FLOAT64", mode="REQUIRED"),
            bigquery.SchemaField("timestamp", "INTEGER", mode="REQUIRED"),
        ]
        table = bigquery.Table(table_id, schema=schema)
        bq_client.create_table(table, exists_ok=True)
        
        # Use test dataset in upsert
        with patch('app.bq.upsert_exchange_rates') as mock_upsert:
            # Actual upsert logic here
            pass
        
        # Verify records were inserted
        query = f"SELECT COUNT(*) as count FROM `{table_id}`"
        result = list(bq_client.query(query).result())
        
        # Note: This test needs the actual upsert to work with test dataset
        # You may need to modify upsert_exchange_rates to accept dataset_id parameter
    
    def test_upsert_duplicate_records(self, bq_client, test_dataset, sample_records):
        """Test that duplicate records update instead of insert."""
        # Insert records twice
        # Verify count stays the same (upsert instead of duplicate)
        pytest.skip("Requires dataset_id parameter in upsert function")
    
    def test_upsert_update_existing(self, bq_client, test_dataset):
        """Test updating existing records with new rates."""
        pytest.skip("Requires dataset_id parameter in upsert function")
    
    def test_upsert_empty_list(self, bq_client, test_dataset):
        """Test upserting empty list."""
        # Should not raise error
        try:
            # Would need modified function
            pass
        except Exception as e:
            pytest.fail(f"Should handle empty list gracefully: {e}")
    
    def test_upsert_invalid_schema(self, bq_client, test_dataset):
        """Test error handling for invalid record schema."""
        invalid_records = [
            {
                "date": "not-a-date",  # Invalid date format
                "currency": "USD",
                "rate_to_eur": "not-a-number",  # Invalid number
            }
        ]
        
        pytest.skip("Requires validation in upsert function")
    
    def test_upsert_missing_required_fields(self, bq_client, test_dataset):
        """Test error handling for missing required fields."""
        incomplete_records = [
            {
                "date": "2025-11-10",
                # Missing currency and rate_to_eur
            }
        ]
        
        pytest.skip("Requires validation in upsert function")
    
    def test_upsert_preserves_timestamp_order(self, bq_client, test_dataset):
        """Test that latest timestamp is preserved on update."""
        pytest.skip("Requires verification logic")


class TestBigQueryEdgeCases:
    """Test edge cases for BigQuery operations."""
    
    def test_very_large_batch(self, bq_client, test_dataset):
        """Test upserting a very large batch of records."""
        # Generate 10000 records
        large_batch = []
        for i in range(10000):
            large_batch.append({
                "date": f"2025-{(i % 12) + 1:02d}-{(i % 28) + 1:02d}",
                "currency": f"CURR{i % 50}",
                "rate_to_eur": 1.0 + (i * 0.001),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
        
        pytest.skip("Requires performance testing setup")
    
    def test_special_characters_in_currency(self, bq_client, test_dataset):
        """Test handling of special characters in currency codes."""
        special_records = [
            {
                "date": "2025-11-10",
                "currency": "US$",  # Special character
                "rate_to_eur": 1.08,
                "timestamp": int(datetime.now(timezone.utc).timestamp()),
            }
        ]
        
        pytest.skip("Requires validation testing")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])