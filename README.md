# Exchange Rates Pipeline - Cloud Run to BigQuery

A serverless pipeline that fetches daily exchange rates from the Open Exchange Rates API, converts to EUR base, and stores in BigQuery with idempotent upsert logic.

## Overview

**Problem:** Manual daily process to fetch exchange rates and convert revenue across currencies.

**Solution:** Automated Cloud Run service that fetches 30 days of exchange rates (USD, GBP, JPY, CHF), converts to EUR base, and upserts to BigQuery.

## Architecture

```
Cloud Scheduler (Daily 6 AM UTC)
           |
           v
Cloud Run (Python + FastAPI)
  - Fetch 30 days from API
  - Transform USD to EUR
  - MERGE to BigQuery
           |
           v
BigQuery
  - rates_staging (temp)
  - rates (main table, partitioned by date)
```

## How It Works

### 1. Fetch Phase
- Loop through last 30 days
- Call OXR API for each date
- Skip dates that fail, continue with others
- Fail only if no data is fetched

### 2. Transform Phase
- Extract EUR rate from API response
- Calculate: `usd_to_eur = 1 / eur_rate`
- For each currency (USD, GBP, JPY, CHF):
  - `rate_eur = api_rate * usd_to_eur`
- Result: ~120 records (30 days × 4 currencies)

### 3. Load & Merge Phase
- Load records to staging table
- MERGE into main table using composite key: (date, currency)
- Idempotent: safe to run multiple times

```sql
MERGE INTO rates T
USING rates_staging S
ON T.date = S.date AND T.currency = S.currency
WHEN MATCHED THEN
    UPDATE SET rate_to_eur = S.rate_to_eur, timestamp = S.timestamp
WHEN NOT MATCHED THEN
    INSERT (date, currency, rate_to_eur, timestamp) VALUES (...)
```

## Setup

### Prerequisites
```bash
gcloud --version
docker --version
python3.11 --version
```

### Initial Setup
```bash
git clone <repo-url> && cd cloud-run-exchange-rates-bq

# Create .env file
cat > .env << EOF
PROJECT_ID=your-gcp-project
OXR_APP_ID=your-openexchangerates-api-key
REGION=europe-west1
EOF

# Python environment
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Authenticate with GCP
gcloud auth login
gcloud auth application-default login
gcloud config set project $(grep PROJECT_ID .env | cut -d= -f2)

# BigQuery setup
export PROJECT_ID=$(grep PROJECT_ID .env | cut -d= -f2)
bq mk --dataset ${PROJECT_ID}:exchange_rates

bq mk --table \
  --time_partitioning_field date \
  ${PROJECT_ID}:exchange_rates.rates \
  date:DATE,currency:STRING,rate_to_eur:FLOAT64,timestamp:TIMESTAMP

bq mk --table ${PROJECT_ID}:exchange_rates.rates_staging \
  date:DATE,currency:STRING,rate_to_eur:FLOAT64,timestamp:TIMESTAMP
```

## Local Testing

```bash
# Run tests
pytest tests/test_ingest.py -v --cov=app

# Start server
uvicorn app.main:app --reload --port 8080

# In another terminal
curl http://localhost:8080/health          # Health check
curl -X POST http://localhost:8080/ingest  # Trigger ingest
```

## Deploy to Cloud Run

```bash
export PROJECT_ID=your-project-id
export OXR_APP_ID=$(grep OXR_APP_ID .env | cut -d= -f2)
export REGION=europe-west1

gcloud run deploy exchange-rates-pipeline \
  --source . \
  --region ${REGION} \
  --platform managed \
  --allow-unauthenticated \
  --set-env-vars PROJECT_ID=${PROJECT_ID},OXR_APP_ID=${OXR_APP_ID} \
  --memory 512Mi \
  --timeout 300s

# Get URL and test
SERVICE_URL=$(gcloud run services describe exchange-rates-pipeline \
  --region ${REGION} --format 'value(status.url)')

curl ${SERVICE_URL}/health
curl -X POST ${SERVICE_URL}/ingest
```

## Schedule Daily Runs

```bash
# Create service account
gcloud iam service-accounts create exchange-rates-scheduler \
  --display-name="Exchange Rates Scheduler"

# Grant permissions
gcloud run services add-iam-policy-binding exchange-rates-pipeline \
  --region ${REGION} \
  --member serviceAccount:exchange-rates-scheduler@${PROJECT_ID}.iam.gserviceaccount.com \
  --role roles/run.invoker

# Create daily job (6 AM UTC)
gcloud scheduler jobs create http exchange-rates-daily \
  --location ${REGION} \
  --schedule "0 6 * * *" \
  --uri "${SERVICE_URL}/ingest" \
  --http-method POST \
  --oidc-service-account-email exchange-rates-scheduler@${PROJECT_ID}.iam.gserviceaccount.com \
  --oidc-token-audience "${SERVICE_URL}"
```

## API Endpoints

### GET /health
```bash
curl http://localhost:8080/health
# Response: {"status": "ok"}
```

### POST /ingest
```bash
curl -X POST http://localhost:8080/ingest
# Success: {"status": "success", "records": 120}
# Error: {"status": "error", "message": "No records fetched from API"}
```

## Query Data

```bash
# Latest rates for today
bq query --use_legacy_sql=false \
"SELECT date, currency, rate_to_eur FROM \`${PROJECT_ID}.exchange_rates.rates\`
 WHERE date = CURRENT_DATE() ORDER BY currency"

# Check for duplicates
bq query --use_legacy_sql=false \
"SELECT COUNT(*) as duplicates FROM (
  SELECT date, currency, COUNT(*) as cnt
  FROM \`${PROJECT_ID}.exchange_rates.rates\`
  GROUP BY date, currency HAVING cnt > 1
)"
```

## Monitoring

```bash
# View logs
gcloud run services logs read exchange-rates-pipeline --region ${REGION} --limit 50

# Check service status
gcloud run services describe exchange-rates-pipeline --region ${REGION}

# Trigger scheduled job manually
gcloud scheduler jobs run exchange-rates-daily --location ${REGION}
```

## Design Decisions

1. **Single File** - Clear linear flow, easy to understand and deploy
2. **Staging + MERGE** - Atomic, idempotent, handles INSERT and UPDATE
3. **EUR Conversion** - Normalized all currencies to EUR base
4. **30-Day Lookback** - Covers billing cycles, cost-efficient
5. **Partition by Date** - Optimized queries and cost savings

## Performance

- Cold start: 2 seconds
- Fetch 30 days: 20 seconds
- Transform: 1 second
- BigQuery operations: 8 seconds
- Total: ~30 seconds per run

## Cost

All components use free tier:
- Cloud Run: up to 2M invocations/month
- BigQuery: up to 1 TB scan/month
- Cloud Scheduler: up to 3 jobs
- **Total: $0.00/month**

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Missing environment variables | Ensure `.env` has PROJECT_ID and OXR_APP_ID |
| Table not found | Run BigQuery setup commands from Setup section |
| 401 Unauthorized | Verify OXR_APP_ID is valid |
| No data in BigQuery | Check logs: `gcloud run services logs read...` |
| Deployment failed | View error: `gcloud run deploy ... --log-http` |

## References

- [OpenExchangeRates API Docs](https://openexchangerates.org/documentation)
- [BigQuery MERGE Statement](https://cloud.google.com/bigquery/docs/reference/standard-sql/dml-syntax#merge-statement)
- [Cloud Run Documentation](https://cloud.google.com/run/docs)
- [Cloud Scheduler Documentation](https://cloud.google.com/scheduler/docs)

---

Last Updated: November 12, 2025
Version: 2.1.0
