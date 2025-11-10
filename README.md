# Exchange Rates Pipeline - Cloud Run to BigQuery

A serverless data pipeline that fetches daily exchange rates from Open Exchange Rates API, converts them to EUR base currency, and stores them in Google BigQuery using Cloud Run.

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Features](#features)
- [Prerequisites](#prerequisites)
- [Project Structure](#project-structure)
- [Setup & Installation](#setup--installation)
- [Deployment](#deployment)
- [Usage](#usage)
- [API Endpoints](#api-endpoints)
- [Testing](#testing)
- [Design Decisions](#design-decisions)
- [Limitations](#limitations)
- [Future Improvements](#future-improvements)
- [Troubleshooting](#troubleshooting)

---

## Overview

This pipeline automatically ingests historical exchange rate data for tracked currencies (USD, GBP, JPY, CHF) against EUR as the base currency. It fetches data from the Open Exchange Rates API, performs currency conversion, and stores the results in BigQuery for analysis.

**Key Capabilities:**
- Fetches last 30 days of historical exchange rates
- Converts USD-based rates to EUR-based rates
- Idempotent upserts to BigQuery (no duplicates)
- RESTful API with FastAPI
- Containerized deployment on Google Cloud Run
- Comprehensive test coverage

---

## Architecture

```
┌─────────────────┐
│  Cloud Scheduler│ 
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Cloud Run     │
│   (FastAPI)     │
│                 │
│  ┌───────────┐  │
│  │ /ingest   │  │ ──┐
│  └───────────┘  │   │
└─────────────────┘   │
         │            │
         ▼            ▼
┌─────────────────┐  ┌──────────────────┐
│ Open Exchange   │  │   BigQuery       │
│ Rates API       │  │   Dataset:       │
│                 │  │   exchange_rates │
│ USD-based rates │  │                  │
└─────────────────┘  │   Tables:        │
                     │   - rates        │
                     │   - rates_staging│
                     └──────────────────┘
```

**Data Flow:**
1. HTTP POST request triggers `/ingest` endpoint
2. Fetches last 30 days from Open Exchange Rates API (USD base)
3. Converts all rates to EUR base using `converter.py`
4. Loads data to staging table in BigQuery
5. Performs MERGE operation to main table (upsert)
6. Returns summary response with record counts

---

## Features

- **Currency Conversion**: Converts USD-based rates to EUR-based rates
- **Idempotent Operations**: Safe to run multiple times (uses MERGE/upsert)
- **Error Handling**: Comprehensive validation for API responses and edge cases
- **Logging**: Structured logging for monitoring and debugging
- **Type Safety**: Full type hints throughout the codebase
- **Test Coverage**: Unit, integration, and validation tests
- **Containerized**: Docker-based deployment
- **Scalable**: Serverless Cloud Run infrastructure
- **Cost Efficient**: Runs within Google Cloud free tier limits

---

## Prerequisites

### Required Tools
- Python 3.11+
- Google Cloud SDK (`gcloud` CLI)
- Docker (for containerization)
- `bq` command-line tool (BigQuery CLI)

### Required Accounts
- Google Cloud Platform account with billing enabled
- Open Exchange Rates account (free tier)

### Google Cloud Services
- Cloud Run
- BigQuery
- Cloud Build
- Cloud Scheduler (optional, for automation)

---

## Project Structure

```
cloud-run-exchange-rates-bq/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI application
│   ├── oxr.py               # Open Exchange Rates API client
│   ├── converter.py         # Currency conversion logic
│   └── bq.py                # BigQuery operations
├── tests/
│   ├── __init__.py
│   ├── test_converter.py    # Unit tests for converter
│   ├── test_conversion.py   # Conversion calculation tests
│   ├── test_edge_cases.py   # Edge case tests
│   ├── test_payload.py      # Payload structure tests
│   ├── test_bq.py           # BigQuery integration tests
│   └── validation_test.py   # API validation tests
├── Dockerfile               # Container definition
├── requirements.txt         # Python dependencies
├── .dockerignore
├── .gitignore
├── README.md
├── NOTES.md                 # Development notes
└── DEMO.md                  # Demo commands
```

---

## Setup & Installation

### 1. Clone Repository

```bash
git clone [<repository-url>](https://github.com/Ruidozo/cloud-run-exchange-rates-bq)
cd cloud-run-exchange-rates-bq
```

### 2. Set Up Python Environment

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Mac/Linux

# Install dependencies
pip install -r requirements.txt
```

### 3. Configure Environment Variables

```bash
export PROJECT_ID=your-gcp-project-id
export OXR_APP_ID=your-openexchangerates-api-key
```

### 4. Authenticate with Google Cloud

```bash
# Login to Google Cloud
gcloud auth login

# Set default project
gcloud config set project ${PROJECT_ID}

# Set up application default credentials
gcloud auth application-default login
```

### 5. Create BigQuery Dataset and Table

```bash
# Create dataset
bq mk --dataset ${PROJECT_ID}:exchange_rates

# Create main table with date partitioning
bq mk --table \
  --time_partitioning_field date \
  --time_partitioning_type DAY \
  ${PROJECT_ID}:exchange_rates.rates \
  date:DATE,currency:STRING,rate_to_eur:FLOAT64,timestamp:INTEGER
```

Note: The staging table `rates_staging` is created automatically by the application.

---

## Deployment

### Option 1: Deploy from Source (Recommended)

```bash
# Enable required APIs
gcloud services enable run.googleapis.com
gcloud services enable cloudbuild.googleapis.com

# Deploy to Cloud Run
gcloud run deploy exchange-rates-pipeline \
  --source . \
  --region europe-west1 \
  --platform managed \
  --allow-unauthenticated \
  --set-env-vars PROJECT_ID=${PROJECT_ID},OXR_APP_ID=${OXR_APP_ID} \
  --memory 512Mi \
  --timeout 300s \
  --max-instances 1

# Get service URL
SERVICE_URL=$(gcloud run services describe exchange-rates-pipeline \
  --region europe-west1 \
  --format 'value(status.url)')

echo "Service deployed at: $SERVICE_URL"
```

### Option 2: Build and Deploy Docker Image Manually

```bash
# Build Docker image
docker build -t gcr.io/${PROJECT_ID}/exchange-rates-pipeline .

# Push to Google Container Registry
docker push gcr.io/${PROJECT_ID}/exchange-rates-pipeline

# Deploy to Cloud Run
gcloud run deploy exchange-rates-pipeline \
  --image gcr.io/${PROJECT_ID}/exchange-rates-pipeline \
  --region europe-west1 \
  --platform managed \
  --allow-unauthenticated \
  --set-env-vars PROJECT_ID=${PROJECT_ID},OXR_APP_ID=${OXR_APP_ID} \
  --memory 512Mi \
  --timeout 300s \
  --max-instances 1
```

---

## Usage

### Run Locally

```bash
# Start FastAPI server
uvicorn app.main:app --reload --port 8080

# Test endpoints
curl http://localhost:8080/health
curl -X POST http://localhost:8080/ingest
```

### Run with Docker

```bash
# Build image
docker build -t exchange-rates-app .

# Run container
docker run -p 8080:8080 \
  -e PROJECT_ID=${PROJECT_ID} \
  -e OXR_APP_ID=${OXR_APP_ID} \
  -v ~/.config/gcloud/application_default_credentials.json:/tmp/keys/service-account.json:ro \
  -e GOOGLE_APPLICATION_CREDENTIALS=/tmp/keys/service-account.json \
  exchange-rates-app

# Test
curl -X POST http://localhost:8080/ingest
```

### Trigger Deployed Service

```bash
# Get service URL
SERVICE_URL=$(gcloud run services describe exchange-rates-pipeline \
  --region europe-west1 \
  --format 'value(status.url)')

# Trigger ingestion
curl -X POST ${SERVICE_URL}/ingest
```

---

## API Endpoints

### GET `/`
Returns service information and available endpoints.

**Response:**
```json
{
  "service": "Exchange Rates Pipeline",
  "version": "1.0.0",
  "endpoints": {
    "/health": "Health check",
    "/ingest": "POST - Trigger data ingestion"
  }
}
```

### GET `/health`
Health check endpoint.

**Response:**
```json
{
  "status": "ok"
}
```

### POST `/ingest`
Triggers exchange rate data ingestion for the last 30 days.

**Response:**
```json
{
  "status": "success",
  "records_count": 120,
  "tracked_currencies": ["JPY", "USD", "GBP", "CHF"],
  "date_range": {
    "start": "2025-10-12",
    "end": "2025-11-10"
  },
  "currencies_per_day": 4,
  "bigquery_dataset": "exchange_rates",
  "bigquery_table": "rates"
}
```

---

## Testing

### Run All Tests

```bash
# Run all tests with coverage
python -m pytest tests/ -v --cov=app --cov-report=term-missing
```

### Run Specific Test Suites

```bash
# Unit tests - converter logic
python -m pytest tests/test_converter.py -v

# Conversion calculations
python -m pytest tests/test_conversion.py -v

# Edge cases
python -m pytest tests/test_edge_cases.py -v

# Payload structures
python -m pytest tests/test_payload.py -v
```

### Integration Tests

```bash
# BigQuery integration (interactive)
python -m tests.test_bq

# API validation with real data
python -m tests.validation_test
```

### Test Coverage

Current test coverage includes:
- Currency conversion logic
- Edge cases (missing EUR, invalid rates, empty data)
- Data payload structures
- BigQuery upsert operations
- API response validation

---

## Design Decisions

### 1. EUR as Base Currency

**Decision:** Convert USD-based rates to EUR-based rates.

**Rationale:**
- Business requirement to have EUR as the base currency
- Open Exchange Rates provides USD-based rates in free tier
- Conversion formula: `rate_to_eur = rate_to_usd / eur_to_usd`

### 2. BigQuery MERGE for Upserts

**Decision:** Use MERGE statement instead of INSERT or DELETE/INSERT.

**Rationale:**
- Idempotent operations (safe to run multiple times)
- Automatic handling of updates and inserts
- No duplicate records
- Atomic operation

**Implementation:**
```sql
MERGE target T
USING source S
ON T.date = S.date AND T.currency = S.currency
WHEN MATCHED THEN UPDATE
WHEN NOT MATCHED THEN INSERT
```

### 3. Staging Table Pattern

**Decision:** Load data to staging table first, then MERGE to main table.

**Rationale:**
- Validates data before affecting main table
- Allows for data quality checks
- Atomic operations
- Easy rollback if needed

### 4. 30-Day Lookback Window

**Decision:** Fetch last 30 days of historical data on each run.

**Rationale:**
- Captures any missed days if pipeline fails
- Handles rate corrections/updates
- Balances API usage vs. data completeness
- Still within Open Exchange Rates free tier (1,000 requests/month)

### 5. FastAPI Framework

**Decision:** Use FastAPI instead of Flask or Django.

**Rationale:**
- Modern, fast, async support
- Automatic API documentation (Swagger/OpenAPI)
- Type hints and validation with Pydantic
- Lightweight for Cloud Run

### 6. Date Partitioning in BigQuery

**Decision:** Partition the main table by date field.

**Rationale:**
- Improves query performance for date-range queries
- Reduces query costs (scans less data)
- Standard best practice for time-series data
- No additional cost

### 7. Tracked Currencies Selection

**Decision:** Track USD, GBP, JPY, CHF against EUR.

**Rationale:**
- Major global currencies
- Covers different economic regions
- Demonstrates multi-currency handling
- Easily extensible to more currencies

---

## Limitations

### Current Limitations

1. **API Rate Limits**
   - Free tier: 1,000 requests/month
   - Current usage: ~30 requests/month (well within limits)
   - No retry logic for rate limit errors

2. **Currency Coverage**
   - Only tracks 4 currencies (USD, GBP, JPY, CHF)
   - Not dynamically configurable
   - Requires code change to add currencies

3. **Error Recovery**
   - No automatic retry for transient API failures
   - No alerting on pipeline failures
   - Manual intervention required for errors

4. **Data Validation**
   - Basic validation only (non-zero, positive rates)
   - No outlier detection for unusual rate changes
   - No historical rate comparison

5. **Authentication**
   - Cloud Run endpoint is publicly accessible
   - No API key or authentication required
   - Suitable for demo, not production

6. **Monitoring**
   - Basic logging only
   - No dashboards or metrics
   - No SLAs or alerting

7. **Historical Data Depth**
   - Only fetches last 30 days
   - No mechanism to backfill older data
   - Initial load limited to 30 days

8. **Single Region Deployment**
   - Deployed only in europe-west1
   - No multi-region redundancy
   - Single point of failure

---

## Future Improvements

### Short-term Enhancements

1. **Add Authentication**
   ```python
   # Add API key authentication
   - Implement Cloud Run IAM authentication
   - Add API key validation
   - Use Secret Manager for credentials
   ```

2. **Implement Retry Logic**
   ```python
   # Add exponential backoff for API calls
   from tenacity import retry, stop_after_attempt, wait_exponential
   
   @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
   def fetch_with_retry():
       # API call here
   ```

3. **Add More Currencies**
   ```python
   # Make currencies configurable via environment variable
   TRACKED_CURRENCIES = os.getenv("TRACKED_CURRENCIES", "USD,GBP,JPY,CHF").split(",")
   ```

4. **Improve Data Validation**
   ```python
   # Add outlier detection
   def validate_rate_change(current_rate, previous_rate, threshold=0.1):
       change = abs(current_rate - previous_rate) / previous_rate
       if change > threshold:
           logger.warning(f"Unusual rate change detected: {change:.2%}")
   ```

### Medium-term Enhancements

5. **Add Monitoring & Alerting**
   - Integrate Cloud Monitoring
   - Set up error rate alerts
   - Create custom dashboards
   - Track API quota usage

6. **Implement Cloud Scheduler**
   - Automate daily runs
   - Configure retry policies
   - Set up error notifications

7. **Add Data Quality Checks**
   - Validate rate reasonableness
   - Check for missing dates
   - Detect duplicate records
   - Monitor data freshness

8. **Enhance Testing**
   - Add performance tests
   - Implement contract testing
   - Add chaos engineering tests
   - Increase coverage to 95%+

### Long-term Enhancements

9. **Multi-Region Deployment**
   - Deploy to multiple regions
   - Implement failover logic
   - Add load balancing

10. **Data Pipeline Orchestration**
    - Migrate to Cloud Composer (Airflow)
    - Add data quality workflows
    - Implement backfill capabilities
    - Schedule different update frequencies

11. **Advanced Analytics**
    - Add trend analysis
    - Implement forecasting models
    - Create materialized views
    - Build BI dashboards

12. **API Enhancements**
    ```python
    # Add query endpoints
    GET /rates?currency=USD&from=2025-01-01&to=2025-01-31
    GET /rates/latest
    GET /rates/history/{currency}
    ```

---

## Troubleshooting

### Common Issues

#### 1. Authentication Errors

**Error:** `google.auth.exceptions.DefaultCredentialsError`

**Solution:**
```bash
gcloud auth application-default login
```

#### 2. BigQuery Table Not Found

**Error:** `404 Not found: Table`

**Solution:**
```bash
# Create the main table
bq mk --table \
  --time_partitioning_field date \
  ${PROJECT_ID}:exchange_rates.rates \
  date:DATE,currency:STRING,rate_to_eur:FLOAT64,timestamp:INTEGER
```

#### 3. Cloud Run Deployment Fails

**Error:** `ERROR: (gcloud.run.deploy) The user-provided container failed to start`

**Solution:**
```bash
# Check logs
gcloud run services logs read exchange-rates-pipeline --region europe-west1

# Verify environment variables
gcloud run services describe exchange-rates-pipeline --region europe-west1
```

#### 4. Open Exchange Rates API Error

**Error:** `401 Unauthorized` or `Invalid API Key`

**Solution:**
```bash
# Verify API key is set
echo $OXR_APP_ID

# Test API key manually
curl "https://openexchangerates.org/api/latest.json?app_id=${OXR_APP_ID}"
```

#### 5. Tests Fail - Module Not Found

**Error:** `ModuleNotFoundError: No module named 'tests'`

**Solution:**
```bash
# Ensure __init__.py exists
touch tests/__init__.py

# Run with Python path
PYTHONPATH=. python -m pytest tests/
```

### Debug Commands

```bash
# View Cloud Run logs
gcloud run services logs read exchange-rates-pipeline \
  --region europe-west1 \
  --limit 50

# Check BigQuery job history
bq ls -j --max_results=10 ${PROJECT_ID}

# Test local container
docker run -it exchange-rates-app /bin/bash

# Verify BigQuery data
bq query --use_legacy_sql=false \
"SELECT COUNT(*) FROM \`${PROJECT_ID}.exchange_rates.rates\`"
```

---

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

---

## License

This project is for demonstration purposes.

---

## Contact & Support

For questions or issues:
- Create an issue in the repository
- Check existing documentation in `DEMO.md` and `NOTES.md`

---

**Last Updated:** November 10, 2025
