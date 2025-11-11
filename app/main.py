import logging
import os
from datetime import date, timedelta

import requests
from fastapi import FastAPI
from google.cloud import bigquery

app = FastAPI()
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/ingest")
def ingest():
    """Fetch exchange rates for last 30 days and upsert to BigQuery."""
    
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
                
                # Extract currencies: USD, GBP, JPY, CHF
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
        
        # Upsert to BigQuery using MERGE
        client = bigquery.Client(project=project_id)
        table_id = f"{project_id}.exchange_rates.rates"
        staging_table = f"{project_id}.exchange_rates.rates_staging"
        
        # Load to staging table
        job_config = bigquery.LoadJobConfig(
            write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE
        )
        load_job = client.load_table_from_json(records, staging_table, job_config=job_config)
        load_job.result()
        logger.info(f"Loaded {len(records)} records to staging")
        
        # MERGE: Update existing dates, insert new ones (handles duplicates)
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
