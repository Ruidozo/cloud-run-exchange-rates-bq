# Deployment Guide - Updated Version with INTEGER Timestamp

This guide walks you through redeploying the updated application to Google Cloud Run.

## Prerequisites

Ensure you have:
- Google Cloud SDK installed and authenticated
- Project ID and OXR_APP_ID environment variables set
- Necessary permissions on GCP project

## Step 1: Set Environment Variables

```bash
export PROJECT_ID=rui-case  # Your GCP project ID
export OXR_APP_ID=your-openexchangerates-api-key
export REGION=europe-west1
```

## Step 2: Clean Up Existing BigQuery Tables

The schema uses TIMESTAMP type for the timestamp field:

```bash
# Drop existing staging table (it will be recreated automatically)
bq rm -f -t ${PROJECT_ID}:exchange_rates.rates_staging

# Drop and recreate main table with TIMESTAMP type
bq rm -f -t ${PROJECT_ID}:exchange_rates.rates

# Create main table with TIMESTAMP
bq mk --table \
  --time_partitioning_field date \
  --time_partitioning_type DAY \
  ${PROJECT_ID}:exchange_rates.rates \
  date:DATE,currency:STRING,rate_to_eur:FLOAT64,timestamp:TIMESTAMP
```

## Step 3: Build and Deploy to Cloud Run

### Option A: Deploy from Source (Recommended)

This automatically builds the Docker image using Cloud Build:

```bash
# Navigate to project directory
cd /Users/ruicarvalho/Desktop/projects/use_case_klevie/cloud-run-exchange-rates-bq

# Deploy to Cloud Run
gcloud run deploy exchange-rates-pipeline \
  --source . \
  --region ${REGION} \
  --platform managed \
  --allow-unauthenticated \
  --set-env-vars PROJECT_ID=${PROJECT_ID},OXR_APP_ID=${OXR_APP_ID} \
  --memory 512Mi \
  --timeout 300s \
  --max-instances 1 \
  --project ${PROJECT_ID}
```

### Option B: Build Docker Image Manually

If you prefer more control over the build process:

```bash
# Navigate to project directory
cd /Users/ruicarvalho/Desktop/projects/use_case_klevie/cloud-run-exchange-rates-bq

# Enable required APIs (if not already enabled)
gcloud services enable cloudbuild.googleapis.com
gcloud services enable run.googleapis.com
gcloud services enable containerregistry.googleapis.com

# Build Docker image
docker build -t gcr.io/${PROJECT_ID}/exchange-rates-pipeline:latest .

# Push to Google Container Registry
docker push gcr.io/${PROJECT_ID}/exchange-rates-pipeline:latest

# Deploy to Cloud Run
gcloud run deploy exchange-rates-pipeline \
  --image gcr.io/${PROJECT_ID}/exchange-rates-pipeline:latest \
  --region ${REGION} \
  --platform managed \
  --allow-unauthenticated \
  --set-env-vars PROJECT_ID=${PROJECT_ID},OXR_APP_ID=${OXR_APP_ID} \
  --memory 512Mi \
  --timeout 300s \
  --max-instances 1 \
  --project ${PROJECT_ID}
```

## Step 4: Get Service URL

```bash
SERVICE_URL=$(gcloud run services describe exchange-rates-pipeline \
  --region ${REGION} \
  --platform managed \
  --project ${PROJECT_ID} \
  --format 'value(status.url)')

echo "Service deployed at: $SERVICE_URL"
```

## Step 5: Test the Deployment

### Test Health Endpoint

```bash
curl ${SERVICE_URL}/health
```

Expected response:
```json
{"status":"ok"}
```

### Test Ingest Endpoint

```bash
curl -X POST ${SERVICE_URL}/ingest
```

Expected response:
```json
{
  "status": "success",
  "records_count": 120,
  "date_range": {
    "start": "2025-10-12",
    "end": "2025-11-10"
  }
}
```

## Step 6: Verify Data in BigQuery

```bash
# Check record count
bq query --use_legacy_sql=false \
  "SELECT COUNT(*) as count FROM \`${PROJECT_ID}.exchange_rates.rates\`"

# Check today's data
bq query --use_legacy_sql=false \
  "SELECT * FROM \`${PROJECT_ID}.exchange_rates.rates\` 
   WHERE date = CURRENT_DATE() 
   ORDER BY currency"

# Check timestamp field type
bq show --schema --format=prettyjson \
  ${PROJECT_ID}:exchange_rates.rates | grep -A 2 timestamp
```

Expected schema for timestamp:
```json
{
  "mode": "REQUIRED",
  "name": "timestamp",
  "type": "TIMESTAMP"
}
```

## Step 7: Monitor Logs

```bash
# View recent logs
gcloud run services logs read exchange-rates-pipeline \
  --region ${REGION} \
  --project ${PROJECT_ID} \
  --limit 100

# Tail logs in real-time
gcloud run services logs tail exchange-rates-pipeline \
  --region ${REGION} \
  --project ${PROJECT_ID}
```

## Rollback (if needed)

If you need to rollback to a previous version:

```bash
# List revisions
gcloud run revisions list \
  --service exchange-rates-pipeline \
  --region ${REGION} \
  --project ${PROJECT_ID}

# Rollback to a specific revision
gcloud run services update-traffic exchange-rates-pipeline \
  --to-revisions REVISION_NAME=100 \
  --region ${REGION} \
  --project ${PROJECT_ID}
```

## Troubleshooting

### Issue: Schema mismatch error

If you see errors about schema mismatch:

```bash
# Drop both tables and recreate
bq rm -f -t ${PROJECT_ID}:exchange_rates.rates_staging
bq rm -f -t ${PROJECT_ID}:exchange_rates.rates

# Recreate main table
bq mk --table \
  --time_partitioning_field date \
  --time_partitioning_type DAY \
  ${PROJECT_ID}:exchange_rates.rates \
  date:DATE,currency:STRING,rate_to_eur:FLOAT64,timestamp:TIMESTAMP

# The staging table will be created automatically on first run
```

### Issue: Deployment fails

```bash
# Check Cloud Build logs
gcloud builds list --limit=5 --project ${PROJECT_ID}

# Get detailed build logs
gcloud builds log BUILD_ID --project ${PROJECT_ID}
```

### Issue: Service not responding

```bash
# Check service status
gcloud run services describe exchange-rates-pipeline \
  --region ${REGION} \
  --project ${PROJECT_ID}

# Check container logs for startup errors
gcloud run services logs read exchange-rates-pipeline \
  --region ${REGION} \
  --project ${PROJECT_ID} \
  --limit 50
```

## Post-Deployment Checklist

- [ ] Service is running (check Cloud Run console)
- [ ] Health endpoint returns 200 OK
- [ ] Ingest endpoint successfully processes data
- [ ] BigQuery tables have correct schema (INTEGER timestamp)
- [ ] Data is being inserted correctly
- [ ] No errors in Cloud Run logs
- [ ] Environment variables are set correctly

## Clean Up Old Revisions (Optional)

To save storage costs, you can delete old revisions:

```bash
# List all revisions
gcloud run revisions list \
  --service exchange-rates-pipeline \
  --region ${REGION} \
  --project ${PROJECT_ID}

# Delete a specific revision
gcloud run revisions delete REVISION_NAME \
  --region ${REGION} \
  --project ${PROJECT_ID}
```

---

**Deployment completed!** Your updated application with INTEGER timestamp is now running on Google Cloud Run.
