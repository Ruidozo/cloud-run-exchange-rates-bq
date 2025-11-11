# Exchange Rates Pipeline - Cloud Run to BigQuery

A lightweight serverless pipeline that fetches daily exchange rates from the Open Exchange Rates API and stores them in BigQuery. Designed for automated revenue conversion analysis across multiple currencies.

## Overview

**Problem:** Manual daily process to fetch exchange rates and convert revenue from different countries into EUR.

**Solution:** Automated Cloud Run function that:
- Fetches last 30 days of exchange rates (USD, GBP, JPY, CHF)
- Converts USD base rates to EUR base
- Stores in BigQuery with duplicate handling (upsert logic)
- Runs daily via Cloud Scheduler
- Provides Looker Studio-ready data

**Architecture:**
```
Open Exchange Rates API
        ↓
   Cloud Run (Python)
        ↓
   BigQuery MERGE
        ↓
   Looker Studio
```

## What's Inside

```
app/
├── main.py          # Single module with all logic (~120 lines)
tests/
├── test_ingest.py   # 4 focused tests
Dockerfile           # Cloud Run container
requirements.txt     # Dependencies
DEMO.md             # Full command reference
```

**Code Stats:**
- 🐍 120 lines of Python
- ✅ 4 unit tests
- 📦 7 dependencies
- ⚡ Sub-second health check
- 🔒 Error handling built-in

## Quick Start

### Prerequisites

```bash
# macOS
brew install python@3.13
brew install google-cloud-sdk

# Linux/Windows
# Download from python.org and cloud.google.com
```

### Setup (5 minutes)

```bash
# Clone
git clone <repo-url>
cd cloud-run-exchange-rates-bq

# Create .env file
cat > .env << EOF
PROJECT_ID=your-gcp-project-id
OXR_APP_ID=your-openexchangerates-api-key
REGION=europe-west1
EOF

# Python environment
python3.13 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Authenticate
gcloud auth login
gcloud auth application-default login
gcloud config set project ${PROJECT_ID}

# BigQuery setup
bq mk --dataset ${PROJECT_ID}:exchange_rates

bq mk --table \
  --time_partitioning_field date \
  ${PROJECT_ID}:exchange_rates.rates \
  date:DATE,currency:STRING,rate_to_eur:FLOAT64,timestamp:TIMESTAMP

bq mk --table \
  ${PROJECT_ID}:exchange_rates.rates_staging \
  date:DATE,currency:STRING,rate_to_eur:FLOAT64,timestamp:TIMESTAMP
```

## Local Testing

```bash
# Run tests
pytest tests/test_ingest.py -v

# Start server
uvicorn app.main:app --reload --port 8080

# In another terminal
curl http://localhost:8080/health          # Health check
curl -X POST http://localhost:8080/ingest  # Trigger ingest
```

## Deploy to Cloud Run

```bash
# Set environment
export PROJECT_ID=your-gcp-project-id
export OXR_APP_ID=your-openexchangerates-api-key
export REGION=europe-west1

# Deploy
gcloud run deploy exchange-rates-pipeline \
  --source . \
  --region ${REGION} \
  --platform managed \
  --allow-unauthenticated \
  --set-env-vars PROJECT_ID=${PROJECT_ID},OXR_APP_ID=${OXR_APP_ID} \
  --memory 512Mi \
  --timeout 300s

# Get URL
SERVICE_URL=$(gcloud run services describe exchange-rates-pipeline \
  --region ${REGION} \
  --format 'value(status.url)')

# Test
curl -X POST ${SERVICE_URL}/ingest
```

## Schedule Daily Runs

```bash
# Create service account
gcloud iam service-accounts create exchange-rates-scheduler \
  --display-name "Exchange Rates Scheduler"

# Grant permission
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

## Design Choices

### 1. Duplicate Handling (Upsert Logic)

Uses BigQuery **MERGE** statement:
```sql
MERGE INTO main_table T
USING staging_table S
ON T.date = S.date AND T.currency = S.currency
WHEN MATCHED THEN UPDATE SET ...
WHEN NOT MATCHED THEN INSERT ...
```

**Why?** Safe to run multiple times. Same date + currency updates existing row; new combinations insert.

### 2. EUR Conversion

Open Exchange Rates API returns USD-based rates. We convert to EUR:
```python
usd_to_eur = 1 / eur_rate
rate_to_eur = usd_rate * usd_to_eur
```

**Example:** If EUR rate is 0.92, then 1 USD = 1.087 EUR

### 3. Error Handling

- **Missing API key:** Returns 500 on startup
- **API failures:** Logs error, continues with other dates (graceful degradation)
- **Missing EUR rate:** Skips that date
- **Network timeout:** 10-second timeout per request
- **BigQuery errors:** Logged and returned to caller

### 4. Single File Architecture

All logic in `app/main.py` (120 lines):
- No complex abstractions
- Clear data flow
- Easy to debug
- Fast to deploy

## API Endpoints

### GET `/health`
Health check for Cloud Run.

**Request:**
```bash
curl http://localhost:8080/health
```

**Response:**
```json
{"status":"ok"}
```

---

### POST `/ingest`
Fetch last 30 days of rates and upsert to BigQuery.

**Request:**
```bash
curl -X POST http://localhost:8080/ingest
```

**Response (Success):**
```json
{"status":"success","records":120}
```

**Response (Error):**
```json
{"status":"error","message":"Missing environment variables"}
```

## Query Data

See **DEMO.md** for full command reference. Quick examples:

```bash
# Latest rates
bq query --use_legacy_sql=false \
"SELECT date, currency, rate_to_eur FROM \`${PROJECT_ID}.exchange_rates.rates\`
 WHERE date = CURRENT_DATE() ORDER BY currency"

# Check for duplicates (should return 0)
bq query --use_legacy_sql=false \
"SELECT COUNT(*) FROM (
   SELECT date, currency, COUNT(*) as cnt
   FROM \`${PROJECT_ID}.exchange_rates.rates\`
   GROUP BY date, currency HAVING cnt > 1
)"

# Statistics
bq query --use_legacy_sql=false \
"SELECT 
   MAX(date) as latest, MIN(date) as oldest,
   COUNT(DISTINCT date) as days, COUNT(*) as total_records
 FROM \`${PROJECT_ID}.exchange_rates.rates\`"
```

## Monitoring

```bash
# View logs
gcloud run services logs read exchange-rates-pipeline \
  --region ${REGION} --limit 50

# Check deployment status
gcloud run services describe exchange-rates-pipeline --region ${REGION}

# Monitor scheduler
gcloud scheduler jobs describe exchange-rates-daily --location ${REGION}
```

## Testing

```bash
# Run all tests
pytest tests/test_ingest.py -v

# EUR conversion test
pytest tests/test_ingest.py::test_eur_conversion -v

# With coverage
pytest tests/test_ingest.py --cov=app --cov-report=term-missing
```

**Tests cover:**
- ✅ EUR conversion math
- ✅ Missing EUR rate handling
- ✅ MERGE upsert logic
- ✅ Record structure validation

## Limitations & Future Ideas

### Current Limitations
- Free tier API: Historical data limited to recent dates
- Base currency: EUR is hardcoded (configurable if needed)
- Tracked currencies: USD, GBP, JPY, CHF only
- Daily frequency: Not real-time
- Rate limits: Subject to OXR subscription tier
- Timestamp: From API, not fetch time

### Future Ideas
- [ ] Configurable base currency via environment variable
- [ ] Data quality validation (outlier detection)
- [ ] Email alerts on API failures
- [ ] Looker Studio dashboard template
- [ ] Cost optimization (batch API calls)
- [ ] Additional currency pairs
- [ ] Audit trail with change tracking

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `Missing environment variables` | Set `PROJECT_ID` and `OXR_APP_ID` in `.env` |
| `Table not found` | Run `bq mk` commands from Setup section |
| `401 Unauthorized` | Verify `OXR_APP_ID` is valid at openexchangerates.org |
| `Deployment failed` | Check logs: `gcloud run services logs read exchange-rates-pipeline --region ${REGION}` |
| `No data in BigQuery` | Verify API key works: `curl "https://openexchangerates.org/api/latest.json?app_id=${OXR_APP_ID}"` |

## Project Structure

```
cloud-run-exchange-rates-bq/
├── app/
│   └── main.py              # Core logic (120 lines)
├── tests/
│   ├── __init__.py
│   └── test_ingest.py       # 4 focused tests
├── Dockerfile               # Cloud Run container
├── requirements.txt         # Dependencies
├── README.md               # This file
├── DEPLOY.md              # Step-by-step deployment
├── DEMO.md                # Command reference
└── .env                   # Environment variables (not in git)
```

## Contributing

1. Create feature branch: `git checkout -b feature/name`
2. Make changes with tests
3. Run tests: `pytest tests/ -v`
4. Commit: `git commit -m "feat: description"`
5. Push and create PR

## Security

- Environment variables in `.env` (not in git)
- Cloud Run service publicly accessible (no auth required - adjust if needed)
- BigQuery MERGE prevents duplicates
- Timestamps logged for audit trail
- Error messages don't expose sensitive data

## Performance

- **Cold start:** ~2 seconds
- **Warm start:** <500ms
- **Fetch 30 days:** ~30 seconds (depends on API)
- **BigQuery MERGE:** ~5 seconds
- **Total:** ~45 seconds per run

## Cost Estimate (GCP)

- **Cloud Run:** $0.40/month (1 daily run)
- **BigQuery:** ~$0.01/month (small dataset, 1 query/day)
- **Cloud Scheduler:** Free tier (3 jobs)
- **Storage:** Negligible

**Total:** ~$0.50/month (highly estimate)

## Support

- **API Issues:** Check openexchangerates.org status
- **BigQuery Issues:** See [BigQuery docs](https://cloud.google.com/bigquery/docs)
- **Cloud Run Issues:** See [Cloud Run docs](https://cloud.google.com/run/docs)

## License

MIT

---

**Last Updated:** November 11, 2025  
**Version:** 1.0.0  
**Status:** Production Ready ✅
