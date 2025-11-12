"""Exchange rates ingestion service for BigQuery.

Fetches historical exchange rates from Open Exchange Rates API,
converts to EUR base, and upserts to BigQuery with duplicate handling.
"""

import json
import logging
import os
from datetime import date, datetime, timedelta
from typing import Optional

import requests
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from google.cloud import bigquery
from google.cloud.exceptions import NotFound

# Configuration
load_dotenv()
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

# Constants
API_BASE_URL = "https://openexchangerates.org/api/historical"
LOOKBACK_DAYS = 30
TRACKED_CURRENCIES = ["USD", "GBP", "JPY", "CHF"]
REQUEST_TIMEOUT_SECONDS = 10

app = FastAPI(
    title="Exchange Rates Pipeline",
    description="Fetch and ingest exchange rates to BigQuery",
    version="1.0.0"
)


# ============================================================================
# HELPERS
# ============================================================================

def convert_unix_to_iso(unix_timestamp: Optional[int]) -> str:
    """Convert Unix timestamp to ISO 8601 format.
    
    Args:
        unix_timestamp: Unix epoch seconds, or None.
        
    Returns:
        ISO 8601 string with Z suffix (UTC).
    """
    if unix_timestamp:
        return datetime.utcfromtimestamp(unix_timestamp).isoformat() + "Z"
    return datetime.utcnow().isoformat() + "Z"


def fetch_historical_rates(api_key: str, target_date: date) -> Optional[dict]:
    """Fetch exchange rates for a specific date from API.
    
    Args:
        api_key: OpenExchangeRates API key.
        target_date: Date to fetch rates for.
        
    Returns:
        Parsed JSON response, or None if request fails.
    """
    url = f"{API_BASE_URL}/{target_date.strftime('%Y-%m-%d')}.json?app_id={api_key}"
    
    try:
        response = requests.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"API error for {target_date}: {e}")
        return None


def transform_to_eur_base(raw_data: dict, target_date: date) -> list[dict]:
    """Transform API response to EUR-based exchange rates.
    
    Converts USD-based rates (from API) to EUR-based rates.
    Formula: rate_eur = rate_usd * (1 / eur_usd_rate)
    
    Args:
        raw_data: Raw API response with 'rates' and 'timestamp' keys.
        target_date: Date for record.
        
    Returns:
        List of record dicts with keys: date, currency, rate_to_eur, timestamp.
        Empty list if EUR rate is missing.
    """
    records = []
    
    rates = raw_data.get("rates", {})
    eur_rate = rates.get("EUR")
    
    if not eur_rate:
        logger.warning(f"EUR rate missing for {target_date}, skipping")
        return records
    
    # Calculate conversion factor
    usd_to_eur = 1 / eur_rate
    timestamp = convert_unix_to_iso(raw_data.get("timestamp"))
    
    # Transform each tracked currency
    for currency in TRACKED_CURRENCIES:
        if currency in rates:
            rate = rates[currency] * usd_to_eur
            records.append({
                "date": target_date.isoformat(),
                "currency": currency,
                "rate_to_eur": float(rate),
                "timestamp": timestamp
            })
    
    return records


def log_structured(level: str, message: str, **kwargs):
    """Log structured JSON for Cloud Logging.
    
    Cloud Logging automatically parses this format.
    """
    log_entry = {
        "severity": level.upper(),
        "message": message,
        **kwargs
    }
    logger_func = getattr(logger, level.lower(), logger.info)
    logger_func(json.dumps(log_entry))


def ensure_staging_table_exists(client, staging_table: str):
    """Create staging table if it doesn't exist."""
    try:
        client.get_table(staging_table)
        logger.info(f"Staging table exists: {staging_table}")
    except NotFound:
        schema = [
            bigquery.SchemaField("date", "DATE"),
            bigquery.SchemaField("currency", "STRING"),
            bigquery.SchemaField("rate_to_eur", "FLOAT64"),
            bigquery.SchemaField("timestamp", "TIMESTAMP"),
        ]
        table = bigquery.Table(staging_table, schema=schema)
        client.create_table(table)
        logger.info(f"Created staging table: {staging_table}")


# ============================================================================
# ENDPOINTS
# ============================================================================

@app.get("/health")
async def health():
    """Health check endpoint for Cloud Run liveness probe."""
    return {"status": "ok"}


@app.post("/ingest")
async def ingest():
    """Fetch and ingest exchange rates for the last 30 days.
    
    Returns:
        - success: {"status": "success", "records": <count>}
        - error: {"status": "error", "message": <reason>}
    """
    # Validate environment
    project_id = os.getenv("PROJECT_ID")
    api_key = os.getenv("OXR_APP_ID")
    
    if not project_id or not api_key:
        msg = "Missing required environment variables: PROJECT_ID, OXR_APP_ID"
        logger.error(msg)
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": msg}
        )
    
    try:
        # ====================================================================
        # PHASE 1: FETCH
        # ====================================================================
        logger.info(f"Starting ingest: fetching {LOOKBACK_DAYS} days of rates")
        all_records = []
        end_date = date.today()
        
        logger.info(json.dumps({
            "severity": "INFO",
            "message": "Ingest started",
            "lookback_days": LOOKBACK_DAYS,
            "tracked_currencies": TRACKED_CURRENCIES
        }))
        
        for i in range(LOOKBACK_DAYS):
            current_date = end_date - timedelta(days=i)
            
            # Fetch API data
            api_data = fetch_historical_rates(api_key, current_date)
            if not api_data:
                continue
            
            # Transform to EUR base
            records = transform_to_eur_base(api_data, current_date)
            all_records.extend(records)
            logger.info(f"Fetched {len(records)} records for {current_date}")
        
        if not all_records:
            msg = "No records fetched from API (all dates failed or missing EUR rate)"
            logger.warning(msg)
            return JSONResponse(
                status_code=400,
                content={"status": "error", "message": msg}
            )
        
        logger.info(json.dumps({
            "severity": "INFO",
            "message": "Fetch phase complete",
            "records_fetched": len(all_records),
            "phase": "FETCH"
        }))
        
        # ====================================================================
        # PHASE 2: LOAD TO STAGING
        # ====================================================================
        client = bigquery.Client(project=project_id)
        staging_table = f"{project_id}.exchange_rates.rates_staging"
        
        # Ensure staging table exists
        ensure_staging_table_exists(client, staging_table)
        
        try:
            job_config = bigquery.LoadJobConfig(
                write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE
            )
            load_job = client.load_table_from_json(all_records, staging_table, job_config=job_config)
            load_job.result()
            logger.info(f"Loaded {len(all_records)} records to staging table")
        except Exception as e:
            logger.error(f"Failed to load staging table: {e}")
            raise
        
        # ====================================================================
        # PHASE 3: MERGE (UPSERT)
        # ====================================================================
        main_table = f"{project_id}.exchange_rates.rates"
        
        merge_query = f"""
        MERGE INTO `{main_table}` T
        USING `{staging_table}` S
        ON T.date = S.date AND T.currency = S.currency
        WHEN MATCHED THEN
            UPDATE SET rate_to_eur = S.rate_to_eur, timestamp = S.timestamp
        WHEN NOT MATCHED THEN
            INSERT (date, currency, rate_to_eur, timestamp)
            VALUES (S.date, S.currency, S.rate_to_eur, S.timestamp)
        """
        
        try:
            merge_job = client.query(merge_query)
            merge_job.result()
            logger.info(f"Successfully upserted {len(all_records)} records to main table")
        except Exception as e:
            logger.error(f"MERGE operation failed: {e}")
            raise
        
        return {"status": "success", "records": len(all_records)}
        
    except Exception as e:
        logger.error(f"Ingest pipeline failed: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": f"Pipeline error: {str(e)}"}
        )
