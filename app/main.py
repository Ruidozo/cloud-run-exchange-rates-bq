import logging
import os
from datetime import date, timedelta
from typing import Any, Dict, List

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException

from app.converter import convert_usd_to_eur_base
from app.oxr import fetch_historical_rates

# Load environment variables from .env file
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Currency Exchange Rates Service")

# Currencies to track (in addition to EUR which is the base)
TRACKED_CURRENCIES = {"USD", "GBP", "JPY", "CHF", "EUR"}


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
async def ingest_exchange_rates():
    """
    Ingest exchange rates for the last 30 days.
    
    Fetches USD-based rates from Open Exchange Rates API,
    converts them to EUR base, and builds records for BigQuery.
    Only includes USD, GBP, JPY, CHF, and EUR.
    """
    try:
        records: List[Dict[str, Any]] = []
        end_date = date.today()
        start_date = end_date - timedelta(days=29)  # 30 days total including today
        
        logger.info("Starting ingestion from %s to %s", start_date, end_date)
        logger.info("Tracking currencies: %s", TRACKED_CURRENCIES)
        
        # Loop through last 30 days
        current_date = start_date
        while current_date <= end_date:
            logger.info("Processing date: %s", current_date)
            
            # Fetch USD-based rates from Open Exchange Rates API
            oxr_data = fetch_historical_rates(current_date)
            
            # Convert to EUR base
            eur_rates = convert_usd_to_eur_base(oxr_data)
            
            # Build records only for tracked currencies
            for currency, rate in eur_rates.items():
                if currency in TRACKED_CURRENCIES:
                    record = {
                        "date": current_date.isoformat(),
                        "currency": currency,
                        "rate_to_eur": rate,
                        "timestamp": oxr_data.get("timestamp"),
                    }
                    records.append(record)
            
            tracked_count = sum(1 for c in eur_rates if c in TRACKED_CURRENCIES)
            logger.info("Processed %d tracked currencies for %s", tracked_count, current_date)
            
            # Move to next day
            current_date += timedelta(days=1)
        
        logger.info("Successfully built %d records for 30 days", len(records))
        
        # TODO: Insert records into BigQuery
        
        return {
            "status": "success",
            "records_count": len(records),
            "tracked_currencies": list(TRACKED_CURRENCIES),
            "date_range": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
            },
            "currencies_per_day": len(TRACKED_CURRENCIES),
            "sample_records": records[:5] if records else [],
        }
        
    except Exception as e:
        logger.error("Ingestion failed: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")