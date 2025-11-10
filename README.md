# Exchange Rates Pipeline - Cloud Run

Automated pipeline to fetch exchange rates from Open Exchange Rates API, convert to EUR base, and store in BigQuery.

## Architecture

- **API**: Open Exchange Rates (historical data)
- **Conversion**: USD rates → EUR base rates
- **Storage**: Google BigQuery with staging table pattern
- **Deployment**: Google Cloud Run
- **Tracked Currencies**: USD, GBP, JPY, CHF (against EUR)

## Local Development

### Prerequisites

```bash
# Python 3.11+
python --version

# Google Cloud SDK
gcloud --version
```

### Setup

```bash
# Clone and navigate
cd cloud-run-exchange-rates-bq

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Mac/Linux

# Install dependencies
pip install -r requirements.txt

# Create .env file
cat > .env << EOF
PROJECT_ID=your-project-id
OXR_APP_ID=your-openexchangerates-app-id
PORT=8080
EOF

# Authenticate with Google Cloud
gcloud auth application-default login
gcloud config set project your-project-id
```

### Create BigQuery Resources

```bash
# Create dataset
bq mk --dataset --location=EU ${PROJECT_ID}:exchange_rates

# Create main table
bq mk --table ${PROJECT_ID}:exchange_rates.rates \
  date:DATE,currency:STRING,rate_to_eur:FLOAT64,timestamp:INTEGER
```

### Run Locally

```bash
# Start the server
uvicorn app.main:app --reload --port 8080

# Test endpoints
curl http://localhost:8080/health
curl http://localhost:8080/
curl -X POST http://localhost:8080/ingest
```

### Run with Docker

```bash
# Build image
docker build -t exchange-rates-app .

# Run container
docker run -p 8080:8080 \
  -e PROJECT_ID=your-project-id \
  -e OXR_APP_ID=your-api-key \
  -v ~/.config/gcloud/application_default_credentials.json:/tmp/keys/service-account.json:ro \
  -e GOOGLE_APPLICATION_CREDENTIALS=/tmp/keys/service-account.json \
  exchange-rates-app

# Test
curl -X POST http://localhost:8080/ingest
```

## Testing

```bash
# Run converter tests
python -m pytest tests/test_converter.py -v

# Run BigQuery integration test
python -m tests.test_bq

# Run validation test (today or 30 days)
python -m tests.validation_test
```

## Deploy to Cloud Run

### Prerequisites

```bash
# Set project
export PROJECT_ID=your-project-id
gcloud config set project ${PROJECT_ID}

# Enable required APIs
gcloud services enable run.googleapis.com
gcloud services enable cloudbuild.googleapis.com
gcloud services enable bigquery.googleapis.com
```

### Deploy

```bash
# Build and deploy in one command
gcloud run deploy exchange-rates-pipeline \
  --source . \
  --region europe-west1 \
  --platform managed \
  --allow-unauthenticated \
  --set-env-vars PROJECT_ID=${PROJECT_ID},OXR_APP_ID=your-api-key \
  --memory 512Mi \
  --timeout 300s \
  --max-instances 1

# Get the service URL
gcloud run services describe exchange-rates-pipeline \
  --region europe-west1 \
  --format 'value(status.url)'
```

### Test Deployment

```bash
# Get service URL
SERVICE_URL=$(gcloud run services describe exchange-rates-pipeline \
  --region europe-west1 \
  --format 'value(status.url)')

# Test endpoints
curl ${SERVICE_URL}/health
curl -X POST ${SERVICE_URL}/ingest
```

## Schedule Daily Runs

### Create Cloud Scheduler Job

```bash
# Create service account for scheduler
gcloud iam service-accounts create exchange-rates-scheduler \
  --display-name "Exchange Rates Scheduler"

# Grant permission to invoke Cloud Run
gcloud run services add-iam-policy-binding exchange-rates-pipeline \
  --region europe-west1 \
  --member serviceAccount:exchange-rates-scheduler@${PROJECT_ID}.iam.gserviceaccount.com \
  --role roles/run.invoker

# Create daily schedule (runs at 6 AM UTC)
gcloud scheduler jobs create http exchange-rates-daily \
  --location europe-west1 \
  --schedule "0 6 * * *" \
  --uri "${SERVICE_URL}/ingest" \
  --http-method POST \
  --oidc-service-account-email exchange-rates-scheduler@${PROJECT_ID}.iam.gserviceaccount.com \
  --time-zone "UTC"
```

## Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `PROJECT_ID` | Google Cloud Project ID | `rui-case` |
| `OXR_APP_ID` | Open Exchange Rates API Key | `your-api-key` |
| `PORT` | Server port (local only) | `8080` |

## API Endpoints

- `GET /` - Service info
- `GET /health` - Health check
- `POST /ingest` - Trigger 30-day ingestion

## BigQuery Schema

**Dataset**: `exchange_rates`

**Table**: `rates`
- `date` (DATE) - Exchange rate date
- `currency` (STRING) - Currency code (USD, GBP, JPY, CHF)
- `rate_to_eur` (FLOAT64) - Exchange rate to EUR
- `timestamp` (INTEGER) - Unix timestamp from API

**Staging Table**: `rates_staging` (auto-created)

## Monitoring

```bash
# View logs
gcloud run services logs read exchange-rates-pipeline \
  --region europe-west1 \
  --limit 50

# Query BigQuery
bq query --use_legacy_sql=false \
'SELECT * FROM `${PROJECT_ID}.exchange_rates.rates` 
 WHERE date = CURRENT_DATE() 
 ORDER BY currency'
```

## Cost Estimation

- **Cloud Run**: Free tier (2M requests/month)
- **BigQuery**: Free tier (1 TB queries/month, 10 GB storage)
- **Cloud Scheduler**: $0.10/job/month
- **Estimated total**: < $1/month

## Project Structure

```
.
├── app/
│   ├── main.py          # FastAPI application
│   ├── oxr.py           # Open Exchange Rates client
│   ├── converter.py     # USD to EUR conversion
│   └── bq.py            # BigQuery client
├── tests/
│   ├── test_converter.py    # Unit tests
│   ├── test_bq.py           # BigQuery integration tests
│   └── validation_test.py   # Rate validation
├── Dockerfile
├── requirements.txt
└── .env                 # Local environment (not committed)
```

## License

MIT
