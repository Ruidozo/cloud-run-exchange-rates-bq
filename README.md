# Exchange Rates Pipeline - Cloud Run to BigQuery

A simple serverless pipeline that fetches daily exchange rates from Open Exchange Rates API and stores them in BigQuery.

## Quick Start

### Prerequisites
- Python 3.11+
- Google Cloud SDK
- GCP project with billing enabled
- Open Exchange Rates API key (free tier)

### Setup

```bash
# Clone
git clone <repo-url>
cd cloud-run-exchange-rates-bq

# Virtual environment
python3 -m venv venv
source venv/bin/activate

# Install
pip install -r requirements.txt

# Environment variables
export PROJECT_ID=your-gcp-project
export OXR_APP_ID=your-api-key
export REGION=europe-west1

# Authenticate
gcloud auth login
gcloud config set project ${PROJECT_ID}
gcloud auth application-default login

# BigQuery setup
bq mk --dataset ${PROJECT_ID}:exchange_rates

bq mk --table \
  --time_partitioning_field date \
  ${PROJECT_ID}:exchange_rates.rates \
  date:DATE,currency:STRING,rate_to_eur:FLOAT64,timestamp:TIMESTAMP
```

## How to Trigger

### Local Testing
```bash
# Start server
uvicorn app.main:app --reload --port 8080

# Trigger ingest
curl -X POST http://localhost:8080/ingest

# Health check
curl http://localhost:8080/health
```

### Cloud Run
```bash
# Deploy
gcloud run deploy exchange-rates-pipeline \
  --source . \
  --region ${REGION} \
  --platform managed \
  --allow-unauthenticated \
  --set-env-vars PROJECT_ID=${PROJECT_ID},OXR_APP_ID=${OXR_APP_ID}

# Get URL
SERVICE_URL=$(gcloud run services describe exchange-rates-pipeline \
  --region ${REGION} --format 'value(status.url)')

# Trigger
curl -X POST ${SERVICE_URL}/ingest
```

### Schedule with Cloud Scheduler (Optional)
```bash
# Create service account
gcloud iam service-accounts create exchange-rates-scheduler \
  --display-name "Exchange Rates Scheduler"

# Grant invoker role
gcloud run services add-iam-policy-binding exchange-rates-pipeline \
  --region ${REGION} \
  --member serviceAccount:exchange-rates-scheduler@${PROJECT_ID}.iam.gserviceaccount.com \
  --role roles/run.invoker

# Daily job (6 AM UTC)
gcloud scheduler jobs create http exchange-rates-daily \
  --location ${REGION} \
  --schedule "0 6 * * *" \
  --uri "${SERVICE_URL}/ingest" \
  --http-method POST \
  --oidc-service-account-email exchange-rates-scheduler@${PROJECT_ID}.iam.gserviceaccount.com \
  --oidc-token-audience "${SERVICE_URL}"
```

## Design Choices

### Upsert Logic (No Duplicates)
- Uses BigQuery MERGE statement
- Same date + currency = UPDATE existing row
- New date + currency = INSERT new row
- Safe to run multiple times

### EUR Conversion
- Open Exchange Rates API returns USD base rates
- We divide by EUR rate to convert to EUR base
- Formula: `rate_to_eur = usd_rate / eur_rate`

### Error Handling
- Missing API key: Returns 500 error on startup
- API failures: Logs error and continues with other dates
- Network timeouts: Retried up to 3 times automatically
- Graceful degradation: Partial data is still upserted

### Architecture
```
POST /ingest
    ↓
Fetch last 30 days from OXR API
    ↓
Convert USD rates to EUR base
    ↓
MERGE into BigQuery (upsert)
    ↓
Return success/failure count
```

## Running Tests

```bash
# All tests
pytest tests/ -v

# Specific test
pytest tests/test_ingest.py::TestEURConversion -v

# With coverage
pytest tests/ --cov=app
```

## Limitations

- **Free tier only:** Historical data limited to recent dates
- **Base currency fixed:** EUR is hardcoded (could be parameterized)
- **Tracked currencies:** USD, GBP, JPY, CHF only (configurable via environment)
- **Daily frequency:** Not real-time, designed for daily runs
- **Rate limits:** Subject to OXR API rate limits per subscription tier
- **Timestamp:** Uses OXR API timestamp, not fetch time

## Known Issues & Future Ideas

- [ ] Support configurable base currency
- [ ] Add data quality validation (check for outliers)
- [ ] Export to CSV for audit trail
- [ ] Email alerts on API failures
- [ ] Dashboard in Looker Studio
- [ ] Performance: Batch API calls if needed

## Monitoring

```bash
# View logs
gcloud run services logs read exchange-rates-pipeline \
  --region ${REGION} --limit 50

# Check data in BigQuery
bq query --use_legacy_sql=false \
"SELECT date, currency, rate_to_eur 
 FROM \`${PROJECT_ID}.exchange_rates.rates\`
 ORDER BY date DESC, currency
 LIMIT 100"

# Count records by date
bq query --use_legacy_sql=false \
"SELECT date, COUNT(*) as count
 FROM \`${PROJECT_ID}.exchange_rates.rates\`
 GROUP BY date ORDER BY date DESC"
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `401 Unauthorized` | Check `OXR_APP_ID` is set and valid |
| `Table not found` | Run `bq mk` command from Setup section |
| `Deployment failed` | Check logs: `gcloud run services logs read exchange-rates-pipeline --region ${REGION}` |
| `No data in BigQuery` | Verify API key works: `curl "https://openexchangerates.org/api/latest.json?app_id=${OXR_APP_ID}"` |

## Cleanup

```bash
# Delete Cloud Run service
gcloud run services delete exchange-rates-pipeline --region ${REGION}

# Delete BigQuery tables
bq rm -f -t ${PROJECT_ID}:exchange_rates.rates
bq rm -f -t ${PROJECT_ID}:exchange_rates.rates_staging
```

---

**Last Updated:** November 11, 2025
