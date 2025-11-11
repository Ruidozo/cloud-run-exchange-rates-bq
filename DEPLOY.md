# Deployment Guide

## Step 1: Prerequisites

```bash
# Verify installed
gcloud --version
docker --version
python3 --version

# Authenticate
gcloud auth login
gcloud auth application-default login

# Set project
export PROJECT_ID=your-gcp-project-id
gcloud config set project ${PROJECT_ID}
```

## Step 2: BigQuery Setup

```bash
export REGION=europe-west1

# Create dataset
bq mk --dataset ${PROJECT_ID}:exchange_rates

# Create table with partitioning
bq mk --table \
  --time_partitioning_field date \
  --time_partitioning_type DAY \
  ${PROJECT_ID}:exchange_rates.rates \
  date:DATE,currency:STRING,rate_to_eur:FLOAT64,timestamp:TIMESTAMP
```

## Step 3: Environment Variables

```bash
export PROJECT_ID=your-gcp-project-id
export OXR_APP_ID=your-openexchangerates-api-key
export REGION=europe-west1
```

## Step 4: Deploy to Cloud Run

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

# Save URL
SERVICE_URL=$(gcloud run services describe exchange-rates-pipeline \
  --region ${REGION} \
  --format 'value(status.url)')

echo "Deployed to: ${SERVICE_URL}"
```

## Step 5: Test

```bash
# Health check
curl ${SERVICE_URL}/health

# Trigger ingest
curl -X POST ${SERVICE_URL}/ingest

# View logs
gcloud run services logs read exchange-rates-pipeline \
  --region ${REGION} --limit 50
```

## Step 6: Automate (Optional)

Schedule daily runs with Cloud Scheduler:

```bash
# Create service account
gcloud iam service-accounts create exchange-rates-scheduler \
  --display-name "Exchange Rates Scheduler"

# Grant permission to invoke Cloud Run
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

# Verify job created
gcloud scheduler jobs list --location ${REGION}
```

## Cleanup

```bash
# Delete scheduler job
gcloud scheduler jobs delete exchange-rates-daily --location ${REGION}

# Delete service account
gcloud iam service-accounts delete exchange-rates-scheduler@${PROJECT_ID}.iam.gserviceaccount.com

# Delete Cloud Run service
gcloud run services delete exchange-rates-pipeline --region ${REGION}

# Delete BigQuery tables
bq rm -f -t ${PROJECT_ID}:exchange_rates.rates
bq rm -f -d ${PROJECT_ID}:exchange_rates
```

---

**Last Updated:** November 11, 2025
