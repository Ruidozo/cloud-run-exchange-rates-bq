# app/bq.py
# BigQuery interaction module for upserting exchange rates using a staging table pattern.
# This module provides functions to ensure the staging table exists,
# truncate it, load new data, and merge it into the main table.

import logging
import os
from typing import Any, Dict, List

from google.cloud import bigquery
from google.cloud.exceptions import NotFound

logger = logging.getLogger(__name__)

def get_client() -> bigquery.Client:
    """Get authenticated BigQuery client."""
    project_id = os.getenv("PROJECT_ID")
    if not project_id:
        raise ValueError("PROJECT_ID environment variable not set")
    return bigquery.Client(project=project_id)

def ensure_staging_table(
    client: bigquery.Client,
    dataset_id: str = "exchange_rates",
    staging_table_id: str = "rates_staging",
) -> str:
    """
    Ensure staging table exists with correct schema.
    
    Args:
        client: BigQuery client
        dataset_id: Dataset ID
        staging_table_id: Staging table ID
        
    Returns:
        Full table ID string (project.dataset.table)
    """
    table_id = f"{client.project}.{dataset_id}.{staging_table_id}"
    
    schema = [
        bigquery.SchemaField("date", "DATE", mode="REQUIRED"),
        bigquery.SchemaField("currency", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("rate_to_eur", "FLOAT64", mode="REQUIRED"),
        bigquery.SchemaField("timestamp", "TIMESTAMP", mode="REQUIRED"),
    ]
    
    table = bigquery.Table(table_id, schema=schema)
    
    try:
        # Try to get existing table first
        existing_table = client.get_table(table_id)
        logger.info(f"Staging table {table_id} already exists")
        
        # Check if schema matches, if not, drop and recreate
        existing_schema = {field.name: field.field_type for field in existing_table.schema}
        if existing_schema.get("timestamp") not in ["TIMESTAMP", "INTEGER"]:
            logger.warning(f"Schema mismatch for timestamp field, dropping and recreating table")
            client.delete_table(table_id)
            client.create_table(table)
            logger.info(f"Recreated staging table {table_id} with correct schema")
    except Exception:
        # Table doesn't exist, create it
        client.create_table(table, exists_ok=True)
        logger.info(f"Created staging table {table_id}")
    
    return table_id


def truncate_staging_table(client: bigquery.Client, dataset_id: str, staging_table_id: str) -> None:
    """
    Truncate staging table before loading new data.
    
    Args:
        client: BigQuery client
        dataset_id: Dataset ID
        staging_table_id: Staging table ID
    """
    project_id = client.project
    truncate_query = f"TRUNCATE TABLE `{project_id}.{dataset_id}.{staging_table_id}`"
    
    job = client.query(truncate_query)
    job.result()
    
    logger.info("Truncated staging table %s", staging_table_id)


def load_to_staging(client: bigquery.Client, table_ref: str, records: List[Dict[str, Any]]) -> None:
    """
    Load records into staging table.
    
    Args:
        client: BigQuery client
        table_ref: Full table reference
        records: List of records to load
    """
    job_config = bigquery.LoadJobConfig(
        schema=[
            bigquery.SchemaField("date", "DATE", mode="REQUIRED"),
            bigquery.SchemaField("currency", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("rate_to_eur", "FLOAT64", mode="REQUIRED"),
            bigquery.SchemaField("timestamp", "TIMESTAMP", mode="REQUIRED"),
        ],
        write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
    )
    
    job = client.load_table_from_json(records, table_ref, job_config=job_config)
    job.result()
    
    logger.info("Loaded %d records into staging table", len(records))


def merge_staging_to_main(
    client: bigquery.Client,
    dataset_id: str,
    main_table_id: str,
    staging_table_id: str
) -> None:
    """
    Merge staging table into main table (idempotent upsert).
    
    Args:
        client: BigQuery client
        dataset_id: Dataset ID
        main_table_id: Main table ID
        staging_table_id: Staging table ID
    """
    project_id = client.project
    
    merge_query = f"""
    MERGE `{project_id}.{dataset_id}.{main_table_id}` AS target
    USING `{project_id}.{dataset_id}.{staging_table_id}` AS source
    ON target.date = source.date AND target.currency = source.currency
    WHEN MATCHED THEN
        UPDATE SET
            rate_to_eur = source.rate_to_eur,
            timestamp = source.timestamp
    WHEN NOT MATCHED THEN
        INSERT (date, currency, rate_to_eur, timestamp)
        VALUES (source.date, source.currency, source.rate_to_eur, source.timestamp)
    """
    
    job = client.query(merge_query)
    result = job.result()
    
    # Get DML stats
    num_rows = result.num_dml_affected_rows if hasattr(result, 'num_dml_affected_rows') else 0
    logger.info("Merged staging to main table %s (%d rows affected)", main_table_id, num_rows)


def upsert_exchange_rates(
    records: List[Dict[str, Any]],
    dataset_id: str = "exchange_rates",
    main_table_id: str = "rates",
    staging_table_id: str = "rates_staging",
) -> None:
    """
    Upsert exchange rates into BigQuery using staging table pattern.
    
    Process:
    1. Ensure staging table exists
    2. Truncate staging table
    3. Load new records into staging
    4. Merge staging into main table
    
    Args:
        records: List of exchange rate records
        dataset_id: BigQuery dataset ID
        main_table_id: Main table ID
        staging_table_id: Staging table ID
    """
    if not records:
        logger.warning("No records to upsert")
        return
    
    client = get_client()
    
    try:
        # Ensure staging table exists
        staging_table_id_full = ensure_staging_table(client, dataset_id, staging_table_id)
        
        # Truncate staging table
        truncate_query = f"TRUNCATE TABLE `{staging_table_id_full}`"
        client.query(truncate_query).result()
        logger.info(f"Truncated staging table: {staging_table_id_full}")
        
        # Load records into staging - use TIMESTAMP type
        job_config = bigquery.LoadJobConfig(
            schema=[
                bigquery.SchemaField("date", "DATE", mode="REQUIRED"),
                bigquery.SchemaField("currency", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("rate_to_eur", "FLOAT64", mode="REQUIRED"),
                bigquery.SchemaField("timestamp", "TIMESTAMP", mode="REQUIRED"),
            ],
            write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
        )
        
        load_job = client.load_table_from_json(
            records, staging_table_id_full, job_config=job_config
        )
        load_job.result()
        logger.info("Loaded %d records into staging table", len(records))
        
        # Merge staging into main
        merge_staging_to_main(client, dataset_id, main_table_id, staging_table_id)
        
        logger.info("Successfully upserted %d records", len(records))
        
    except Exception as e:
        logger.error("Failed to upsert records: %s", e)
        raise