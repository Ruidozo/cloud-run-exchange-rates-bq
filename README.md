# Exchange Rates Pipeline - Cloud Run to BigQuery

A serverless data pipeline that fetches daily exchange rates from Open Exchange Rates API and stores them in Google BigQuery using Cloud Run.

## Quick Start

### Prerequisites
- Python 3.11+
- Google Cloud SDK
- Docker
- GCP account with billing enabled
- Open Exchange Rates API key

### Setup

```bash
# Clone and setup
git clone [<repository-url>](https://github.com/Ruidozo/cloud-run-exchange-rates-bq.git)
cd cloud-run-exchange-rates-bq

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set environment variables
export PROJECT_ID=your-gcp-project-id
export OXR_APP_ID=your-openexchangerates-api-key
export REGION=europe-west1

# Authenticate
gcloud auth login
gcloud config set project ${PROJECT_ID}
gcloud auth application-default login

# Create BigQuery dataset and table
bq mk --dataset ${PROJECT_ID}:exchange_rates

bq mk --table \
  --time_partitioning_field date \
  --time_partitioning_type DAY \
  ${PROJECT_ID}:exchange_rates.rates \
  date:DATE,currency:STRING,rate_to_eur:FLOAT64,timestamp:TIMESTAMP
```

## Deployment

### Deploy to Cloud Run

```bash
# Enable APIs
gcloud services enable run.googleapis.com cloudbuild.googleapis.com

# Deploy from source
gcloud run deploy exchange-rates-pipeline \
  --source . \
  --region ${REGION} \
  --platform managed \
  --allow-unauthenticated \
  --set-env-vars PROJECT_ID=${PROJECT_ID},OXR_APP_ID=${OXR_APP_ID} \
  --memory 512Mi \
  --timeout 300s \
  --max-instances 1

# Get service URL
SERVICE_URL=$(gcloud run services describe exchange-rates-pipeline \
  --region ${REGION} \
  --format 'value(status.url)')

echo "Service deployed at: $SERVICE_URL"
```

## Usage

### Local Development

```bash
# Start server
uvicorn app.main:app --reload --port 8080

# Test endpoints
curl http://localhost:8080/health
curl -X POST http://localhost:8080/ingest
```

### API Endpoints

- `GET /health` - Health check
- `POST /ingest` - Trigger exchange rate ingestion (last 30 days)

**Example Response:**
```json
{
  "status": "success",
  "records_ingested": 120,
  "failed_dates": []
}
```

## Testing

```bash
# Run all tests with coverage
python -m pytest tests/ -v --cov=app --cov-report=term-missing

# Run specific test suite
python -m pytest tests/test_converter.py -v
python -m pytest tests/test_edge_cases.py -v

# Integration tests
python -m tests.test_bq
python -m tests.validation_test
```

## Project Structure

```
cloud-run-exchange-rates-bq/
├── app/
│   ├── main.py              # FastAPI application
│   ├── oxr.py               # Open Exchange Rates API client
│   ├── converter.py         # Currency conversion logic
│   └── bq.py                # BigQuery operations
├── tests/                   # Unit & integration tests
├── Dockerfile
├── requirements.txt
├── README.md
└── DEMO.md                  # Detailed demo commands
```

## Features

- Fetches last 30 days of historical exchange rates
- Converts USD-based rates to EUR-based rates
- Idempotent upserts to BigQuery (no duplicates)
- Comprehensive error handling and logging
- Type-safe Python with full type hints
- Containerized deployment on Cloud Run

## Architecture

```
Cloud Scheduler (optional)
        ↓
  Cloud Run (FastAPI)
        ↓
  Open Exchange Rates API
        ↓
  BigQuery (exchange_rates dataset)
```

**Data Flow:**
1. `/ingest` endpoint triggered
2. Fetch last 30 days from Open Exchange Rates API
3. Convert USD rates to EUR base
4. Load to staging table
5. MERGE to main table (upsert)

## Configuration

### Tracked Currencies
- USD, GBP, JPY, CHF (against EUR)

### Partitioning
- Date-based partitioning for performance

### Environment Variables
```bash
PROJECT_ID          # GCP project ID
OXR_APP_ID          # Open Exchange Rates API key
REGION              # GCP region (default: europe-west1)
```

## Cloud Scheduler (Optional)

Automate daily runs:

```bash
# Create service account
gcloud iam service-accounts create exchange-rates-scheduler \
  --display-name "Exchange Rates Scheduler"

# Grant Cloud Run Invoker role
gcloud run services add-iam-policy-binding exchange-rates-pipeline \
  --region ${REGION} \
  --member serviceAccount:exchange-rates-scheduler@${PROJECT_ID}.iam.gserviceaccount.com \
  --role roles/run.invoker

# Create job (daily at 6 AM UTC)
SERVICE_URL=$(gcloud run services describe exchange-rates-pipeline \
  --region ${REGION} --format 'value(status.url)')

gcloud scheduler jobs create http exchange-rates-daily \
  --location ${REGION} \
  --schedule "0 6 * * *" \
  --uri "${SERVICE_URL}/ingest" \
  --http-method POST \
  --oidc-service-account-email exchange-rates-scheduler@${PROJECT_ID}.iam.gserviceaccount.com \
  --oidc-token-audience "${SERVICE_URL}"
```

## Monitoring

```bash
# View logs
gcloud run services logs read exchange-rates-pipeline \
  --region ${REGION} \
  --limit 50

# List revisions
gcloud run revisions list \
  --service exchange-rates-pipeline \
  --region ${REGION}

# Query BigQuery
bq query --use_legacy_sql=false \
"SELECT currency, COUNT(*) as records \
 FROM \`${PROJECT_ID}.exchange_rates.rates\` \
 GROUP BY currency"
```

## Limitations

- **API Rate Limiting**: Open Exchange Rates API has rate limits based on subscription tier
- **Historical Data**: Free tier limited to recent data; paid plans offer more history
- **Currencies**: Currently tracking USD, GBP, JPY, CHF (configurable)
- **BigQuery Quotas**: Subject to GCP project quotas and billing limits
- **Real-time**: Data updated daily, not real-time
- **Base Currency**: EUR is hardcoded as base currency
- **Timezone**: All timestamps in UTC

## Future Improvements

- [ ] Support for additional base currencies
- [ ] Configurable tracked currencies via environment variables
- [ ] Database connection pooling optimization
- [ ] Advanced metrics and alerting
- [ ] Multi-region deployment support
- [ ] WebSocket support for real-time updates
- [ ] Caching layer for frequently accessed rates
- [ ] Data quality validation checks
- [ ] Historical rate reconciliation
- [ ] Cost optimization analysis

## Troubleshooting

### Authentication Error
```bash
gcloud auth application-default login
```

### BigQuery Table Not Found
```bash
bq mk --table \
  --time_partitioning_field date \
  ${PROJECT_ID}:exchange_rates.rates \
  date:DATE,currency:STRING,rate_to_eur:FLOAT64,timestamp:TIMESTAMP
```

### Cloud Run Deployment Failed
```bash
# Check logs
gcloud run services logs read exchange-rates-pipeline --region ${REGION}

# Verify environment variables
gcloud run services describe exchange-rates-pipeline --region ${REGION}
```

### Invalid API Key
```bash
# Test API key
curl "https://openexchangerates.org/api/latest.json?app_id=${OXR_APP_ID}"
```

## Cleanup

```bash
# Delete Cloud Run service
gcloud run services delete exchange-rates-pipeline --region ${REGION}

# Delete BigQuery tables
bq rm -f -t ${PROJECT_ID}:exchange_rates.rates
bq rm -f -t ${PROJECT_ID}:exchange_rates.rates_staging
```

## More Information

- See `DEMO.md` for detailed demo commands
- See `DEPLOY.md` for deployment guide

---

**Last Updated:** November 11, 2025
