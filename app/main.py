# app/main.py
# Main FastAPI application for currency exchange rates ingestion service.
# This application fetches exchange rates from Open Exchange Rates API,
# converts them to EUR base, and upserts them into BigQuery using a staging table pattern


import logging
import os
from datetime import date, datetime, timedelta
from typing import Any, Dict, List

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException

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
    current_date = start_date
    
    all_records: List[Dict[str, Any]] = []
    failed_dates: List[Dict[str, str]] = []
    
    while current_date <= end_date:
        try:
            logger.info("Processing date: %s", current_date)
            oxr_data = fetch_historical_rates(current_date)
            eur_rates = convert_usd_to_eur_base(oxr_data)
            
            # Use Unix timestamp (integer) instead of ISO string
            timestamp = int(datetime.now().timestamp())
            
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
        
        current_date += timedelta(days=1)
    
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
    required_vars = {
        "PROJECT_ID": "Google Cloud Project ID",
        "OXR_APP_ID": "Open Exchange Rates API Key"
    }
    
    missing = []
    for var, description in required_vars.items():
        value = os.getenv(var)
        if not value:
            missing.append(f"{var} ({description})")
        else:
            logger.info("Environment variable %s is configured", var)
    
    if missing:
        error_msg = f"Missing required environment variables: {', '.join(missing)}"
        logger.error(error_msg)
        raise RuntimeError(error_msg)
    
    logger.info("Environment validation successful")