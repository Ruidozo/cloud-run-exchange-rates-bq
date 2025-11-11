# app/main.py
# Main FastAPI application for currency exchange rates ingestion service.
# This application fetches exchange rates from Open Exchange Rates API,
# converts them to EUR base, and upserts them into BigQuery using a staging table pattern


import logging
import os
from datetime import date, timedelta
from typing import Any, Dict, List

import requests
from dateutil.rrule import DAILY, rrule
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from google.cloud import bigquery

from app.bq import upsert_exchange_rates
from app.converter import convert_usd_to_eur_base
from app.oxr import fetch_historical_rates

# Load environment variables from .env file
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Currency Exchange Rates Service")

# Currencies to track
TRACKED_CURRENCIES = {"USD", "GBP", "JPY", "CHF" }


@app.get("/health")
def health():
    """Health check endpoint."""
    logger.info("Health check called")
    return {"status": "ok"}


@app.get("/")
def root():
    """Root endpoint."""
    logger.info("Root endpoint called")
    return {
        "message": "Currency Exchange Rates pipeline",
        "project_id": os.getenv("PROJECT_ID", "local-dev"),
    }


@app.post("/ingest")
def ingest_exchange_rates():
    """Fetch and store exchange rates for the last 30 days."""
    logger.info("Starting exchange rate ingestion")
    
    end_date = date.today()
    start_date = end_date - timedelta(days=30)
    
    all_records: List[Dict[str, Any]] = []
    failed_dates: List[Dict[str, str]] = []
    
    # Use rrule for cleaner iteration
    for current_date in rrule(DAILY, dtstart=start_date, until=end_date):
        current_date = current_date.date()
        try:
            logger.info("Processing date: %s", current_date)
            oxr_data = fetch_historical_rates(current_date)
            eur_rates = convert_usd_to_eur_base(oxr_data)
            
            # Use ISO format timestamp string for TIMESTAMP type
            timestamp = datetime.now(timezone.utc).isoformat()
            
            for currency in TRACKED_CURRENCIES:
                if currency in eur_rates:
                    all_records.append({
                        "date": current_date.isoformat(),
                        "currency": currency,
                        "rate_to_eur": eur_rates[currency],
                        "timestamp": timestamp,
                    })
                else:
                    logger.warning(
                        "Currency %s not found in rates for %s",
                        currency, current_date
                    )
        
        except Exception as e:
            logger.error(
                "Failed to process %s: %s",
                current_date, str(e),
                exc_info=True
            )
            failed_dates.append({
                "date": current_date.isoformat(),
                "error": str(e)
            })
    
    # Upsert successful records even if some dates failed
    if all_records:
        try:
            upsert_exchange_rates(all_records)
            logger.info("Successfully upserted %d records", len(all_records))
        except Exception as e:
            logger.error("Failed to upsert records: %s", e, exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Failed to write to BigQuery: {str(e)}"
            )
    
    # Build response
    status = "completed_with_failures" if failed_dates else "success"
    
    response = {
        "status": status,
        "records_count": len(all_records),
        "date_range": {
            "start": start_date.isoformat(),
            "end": end_date.isoformat(),
        },
    }
    
    if failed_dates:
        response["failed_dates"] = failed_dates
        response["failed_count"] = len(failed_dates)
        logger.warning("Completed with %d failed dates", len(failed_dates))
    else:
        logger.info("Ingestion completed successfully")
    
    return response


@app.on_event("startup")
async def validate_environment():
    """Validate required environment variables on startup."""
    required_vars = ["PROJECT_ID", "OXR_APP_ID"]
    missing = [var for var in required_vars if not os.getenv(var)]
    
    if missing:
        error_msg = f"Missing required environment variables: {', '.join(missing)}"
        logger.error(error_msg)
        raise RuntimeError(error_msg)
    
    logger.info("Environment validation successful")


@app.post("/ingest")
def ingest():
    """Fetch exchange rates for last 30 days and upsert to BigQuery."""
    
    # Validate environment
    project_id = os.getenv("PROJECT_ID")
    api_key = os.getenv("OXR_APP_ID")
    
    if not project_id or not api_key:
        logger.error("Missing PROJECT_ID or OXR_APP_ID")
        return {"status": "error", "message": "Missing environment variables"}, 500
    
    try:
        records = []
        end_date = date.today()
        
        # Fetch last 30 days
        for i in range(30):
            current_date = end_date - timedelta(days=i)
            
            try:
                # Fetch from API
                url = f"https://openexchangerates.org/api/historical/{current_date.strftime('%Y-%m-%d')}.json?app_id={api_key}"
                response = requests.get(url, timeout=10)
                response.raise_for_status()
                data = response.json()
                
                if "rates" not in data:
                    logger.warning(f"No rates for {current_date}")
                    continue
                
                # Convert USD to EUR base
                eur_rate = data["rates"].get("EUR")
                if not eur_rate:
                    logger.warning(f"EUR rate missing for {current_date}")
                    continue
                
                usd_to_eur = 1 / eur_rate
                timestamp = data.get("timestamp")
                
                # Extract currencies
                for currency in ["USD", "GBP", "JPY", "CHF"]:
                    if currency in data["rates"]:
                        rate = data["rates"][currency] * usd_to_eur
                        records.append({
                            "date": current_date.isoformat(),
                            "currency": currency,
                            "rate_to_eur": float(rate),
                            "timestamp": timestamp
                        })
                
                logger.info(f"Fetched rates for {current_date}")
                
            except Exception as e:
                logger.error(f"Error fetching {current_date}: {e}")
                continue
        
        if not records:
            logger.warning("No records to upsert")
            return {"status": "error", "message": "No records fetched"}, 400
        
        # Upsert to BigQuery
        client = bigquery.Client(project=project_id)
        table_id = f"{project_id}.exchange_rates.rates"
        staging_table = f"{project_id}.exchange_rates.rates_staging"
        
        # Load to staging
        job_config = bigquery.LoadJobConfig(
            write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE
        )
        load_job = client.load_table_from_json(records, staging_table, job_config=job_config)
        load_job.result()
        
        # Merge staging to main 
        merge_query = f"""
        MERGE INTO `{table_id}` T
        USING `{staging_table}` S
        ON T.date = S.date AND T.currency = S.currency
        WHEN MATCHED THEN
            UPDATE SET rate_to_eur = S.rate_to_eur, timestamp = S.timestamp
        WHEN NOT MATCHED THEN
            INSERT (date, currency, rate_to_eur, timestamp)
            VALUES (S.date, S.currency, S.rate_to_eur, S.timestamp)
        """
        
        merge_job = client.query(merge_query)
        merge_job.result()
        logger.info(f"Upserted {len(records)} records")
        
        return {"status": "success", "records": len(records)}
        
    except Exception as e:
        logger.error(f"Ingest failed: {e}")
        return {"status": "error", "message": str(e)}, 500